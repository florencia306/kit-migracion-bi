"""
Validador de migración: compara cada medida del destino contra el valor de referencia del origen.

Lee casos (YAML), ejecuta la consulta en la herramienta de destino (conector), obtiene la
referencia (QlikView en vivo, CSV exportado, QVD local o SQL) y compara con tolerancia. Todo corre
localmente: los datos no pasan por el chat. La consola muestra solo un resumen corto.

Uso:
  python scripts/validar.py tableros/<t>/tests/casos.yaml
  python scripts/validar.py casos.yaml --solo <id>      # un caso
  python scripts/validar.py casos.yaml --dry-run        # muestra las consultas sin ejecutar

El destino sale de casos.yaml (clave "destino") o de migracion.yaml.
Power BI: pip install pandas pyyaml pythonnet pyqvd pyodbc, con Power BI Desktop abierto.
"""
import argparse
import os
import sys
from datetime import date

import pandas as pd
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import conectores  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def short(col):
    return col.split("[")[-1].rstrip("]")


# ---------------------------------------------------------------- referencias
def to_number(s, formato="ar"):
    if pd.api.types.is_numeric_dtype(s):
        return s
    s = s.astype(str).str.strip().str.replace("%", "", regex=False).str.replace("$", "", regex=False)
    if formato == "ar":   # 1.234,56 -> 1234.56
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:                 # 1,234.56 -> 1234.56
        s = s.str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce")


def detect_sep(path, encoding):
    header = open(path, encoding=encoding).readline()
    return max([";", "\t", ","], key=header.count) if any(c in header for c in ";\t,") else ";"


def ref_csv(ref, base_dir, keys):
    path = os.path.join(base_dir, ref["archivo"])
    enc = ref.get("encoding", "utf-8-sig")
    df = pd.read_csv(path, sep=ref.get("separador") or detect_sep(path, enc), encoding=enc, dtype=str)
    rename = ref.get("renombrar", {})  # columna Qlik -> nombre de la clave en Power BI
    df = df.rename(columns=rename)
    df = df[[*keys, ref["columna"]]].rename(columns={ref["columna"]: "valor"})
    df["valor"] = to_number(df["valor"], ref.get("formato_numero", "ar"))
    return df


def ref_qvd(ref, base_dir, keys):
    from pyqvd import QvdTable
    df = QvdTable.from_qvd(os.path.join(base_dir, ref["archivo"])).to_pandas()
    for col, values in (ref.get("filtros") or {}).items():
        df = df[df[col].isin(values)]
    df = df.rename(columns=ref.get("renombrar", {}))
    agg = ref.get("agregacion", "count_distinct")
    col = ref["columna"]
    func = {"count_distinct": "nunique", "sum": "sum", "count": "count"}[agg]
    out = df.groupby(keys)[col].agg(func).reset_index() if keys else pd.DataFrame({col: [getattr(df[col], func)()]})
    return out.rename(columns={col: "valor"})


def ref_sql(ref, base_dir, keys):
    import pyodbc
    conn_str = os.environ.get(ref.get("conexion_env", "SYNAPSE_CONN"))
    if not conn_str:
        sys.exit("Definí la variable de entorno SYNAPSE_CONN con la cadena de conexión.")
    with pyodbc.connect(conn_str) as cn:
        return pd.read_sql(ref["consulta"], cn)


_QLIK = {}


def ref_qlik(ref, base_dir, keys):
    """Valor leído en vivo de un objeto de QlikView, con variables y selecciones del caso."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "herramientas"))
    import qlik_vivo
    if "doc" not in _QLIK:
        qvw = ref.get("documento")
        _QLIK["app"], _QLIK["doc"], _QLIK["propio"] = qlik_vivo.conectar(os.path.join(base_dir, qvw) if qvw else None)
    doc = _QLIK["doc"]
    orig = qlik_vivo.aplicar_contexto(doc, ref.get("variables"), ref.get("selecciones"))
    try:
        df = qlik_vivo.datos_objeto(doc, ref["objeto"])
    finally:
        qlik_vivo.restaurar(doc, orig)
    df = df.rename(columns=ref.get("renombrar", {}))
    col = ref.get("columna", "valor")
    df = df[[*keys, col]].rename(columns={col: "valor"})
    df = df[~df[keys[0]].astype(str).str.strip().isin(["", "-", "Total"])] if keys else df.head(1)  # sin fila de totales
    df["valor"] = to_number(df["valor"], ref.get("formato_numero", "ar")) if df["valor"].dtype == object else df["valor"]
    return df


def cerrar_qlik():
    if _QLIK.get("propio"):
        try:
            _QLIK["doc"].CloseDoc()
        except Exception:
            pass


REF = {"csv": ref_csv, "qvd": ref_qvd, "sql": ref_sql, "qlik": ref_qlik}


# ---------------------------------------------------------------- comparación
def compare(dst, ref, keys, tol_abs, tol_pct):
    for df in (dst, ref):
        for k in keys:
            df[k] = df[k].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    if keys:
        ref = ref.groupby(keys, as_index=False)["valor"].sum()
        m = dst.merge(ref, on=keys, how="outer", suffixes=("_destino", "_origen"))
    else:
        m = pd.DataFrame({"valor_destino": [dst["valor"].iloc[0]], "valor_origen": [ref["valor"].iloc[0]]})
    m["valor_destino"] = pd.to_numeric(m["valor_destino"], errors="coerce").fillna(0)
    m["valor_origen"] = pd.to_numeric(m["valor_origen"], errors="coerce").fillna(0)
    m["dif"] = m["valor_destino"] - m["valor_origen"]
    m["dif_pct"] = (m["dif"] / m["valor_origen"].where(m["valor_origen"] != 0)).abs() * 100
    ok = m["dif"].abs() <= tol_abs
    if tol_pct is not None:
        ok = ok | (m["dif_pct"].fillna(0) <= tol_pct)
    m["estado"] = ok.map({True: "OK", False: "DIFERENCIA"})
    return m


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("casos")
    ap.add_argument("--solo")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--puerto", type=int)
    ap.add_argument("--adomd")
    ap.add_argument("--salida")
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.casos, encoding="utf-8"))
    mig = yaml.safe_load(open(os.path.join(RAIZ, "migracion.yaml"), encoding="utf-8"))
    dst = conectores.cargar_destino(cfg.get("destino", mig["destino"]))
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(a.casos)))
    tablero = cfg.get("tablero", os.path.basename(base_dir))
    casos = [c for c in cfg["casos"] if not a.solo or c["id"] == a.solo]

    if a.dry_run:
        for c in casos:
            print(f"-- {c['id']}\n{dst.armar_consulta(c)}\n")
        return

    cliente = dst.Cliente({"puerto": a.puerto, "adomd": a.adomd})
    out_dir = a.salida or os.path.join("validacion", "resultados", tablero)
    os.makedirs(out_dir, exist_ok=True)

    resumen, detalle = [], []
    for c in casos:
        keys = [short(g) for g in c.get("agrupar_por", [])]
        try:
            res = dst.normalizar_resultado(cliente.ejecutar(dst.armar_consulta(c)))
            r = dict(cfg.get("qlik") or {}, **c["referencia"]) if c["referencia"]["tipo"] == "qlik" else c["referencia"]
            if r["tipo"] == "qlik":  # variables/selecciones comunes (bloque qlik:) + las del caso
                for k in ("variables", "selecciones"):
                    r[k] = {**((cfg.get("qlik") or {}).get(k) or {}), **(c["referencia"].get(k) or {})}
            ref = REF[r["tipo"]](r, base_dir, keys)
            m = compare(res, ref, keys, c.get("tolerancia", 0), c.get("tolerancia_pct"))
            n_bad = int((m["estado"] != "OK").sum())
            m.insert(0, "caso", c["id"])
            detalle.append(m)
            resumen.append([c["id"], c["medida"], "OK" if n_bad == 0 else "DIFERENCIA", len(m), n_bad,
                            round(m["valor_destino"].sum(), 2), round(m["valor_origen"].sum(), 2)])
        except Exception as e:  # un caso roto no frena al resto
            resumen.append([c["id"], c.get("medida", ""), "ERROR", 0, 0, None, str(e)[:120]])

    cerrar_qlik()
    hoy = date.today().isoformat()
    res = pd.DataFrame(resumen, columns=["caso", "medida", "estado", "filas", "filas_con_dif", "total_destino", "total_origen"])
    res.to_csv(os.path.join(out_dir, f"resumen_{hoy}.csv"), sep=";", index=False, encoding="utf-8-sig")
    if detalle:
        pd.concat(detalle).to_csv(os.path.join(out_dir, f"detalle_{hoy}.csv"), sep=";", index=False, encoding="utf-8-sig")

    cnt = res["estado"].value_counts().to_dict()
    print(f"{tablero}: {len(res)} casos | " + " | ".join(f"{k}: {v}" for k, v in cnt.items()))
    bad = res[res["estado"] != "OK"]
    if len(bad):
        print(bad.to_string(index=False))
    print(f"Detalle: {out_dir}")


if __name__ == "__main__":
    main()
