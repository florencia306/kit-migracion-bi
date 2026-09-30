"""
Reporte visual de migración (HTML autocontenido).

Junta el catálogo de métricas (catalogo.py) con la última corrida del
validador (validar.py) y calcula el desvío % contra el origen por métrica.

Uso:
  python scripts/reporte.py validacion/resultados/<tablero> [--titulo "Métricas Gerencia Individual"]

Lee:   <carpeta>/catalogo.json y el resumen_<fecha>.csv más reciente de <carpeta>
Crea:  <carpeta>/reporte-migracion.html  (abrir con doble clic)
"""
import argparse
import csv
import glob
import json
import os
from datetime import date

PLANTILLA = os.path.join(os.path.dirname(__file__), "plantillas", "reporte-migracion.html")


def num(v):
    v = (v or "").strip()
    if not v:
        return None
    if "," in v and v.rsplit(",", 1)[-1].isdigit():
        v = v.replace(".", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def desvios(carpeta, metricas):
    resumenes = sorted(glob.glob(os.path.join(carpeta, "resumen_*.csv")))
    if not resumenes:
        return {}, None, 0
    ultimo = resumenes[-1]
    medida_a_metrica = {m.lower(): x["id"] for x in metricas for m in x["medidas_destino"]}
    out, sin_match = {}, 0
    with open(ultimo, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            mid = medida_a_metrica.get((r.get("medida") or "").strip().lower())
            if not mid:
                sin_match += 1
                continue
            p, q = num(r.get("total_destino", r.get("total_pbi"))), num(r.get("total_origen", r.get("total_qlik")))
            d = (p - q) / q * 100 if p is not None and q not in (None, 0) else None
            cur = out.setdefault(mid, {"desvio": None, "estado": "OK", "casos": []})
            cur["casos"].append(r.get("caso", ""))
            if r.get("estado") != "OK":
                cur["estado"] = r.get("estado") or "DIFERENCIA"
            if d is not None and (cur["desvio"] is None or abs(d) > abs(cur["desvio"])):
                cur["desvio"] = round(d, 4)
                cur["total_destino"], cur["total_origen"] = p, q
            cur.setdefault("total_destino", p)
            cur.setdefault("total_origen", q)
    fecha = os.path.basename(ultimo)[len("resumen_"):-4]
    return out, fecha, sin_match


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--titulo", default=None)
    a = ap.parse_args()

    cat = json.load(open(os.path.join(a.carpeta, "catalogo.json"), encoding="utf-8"))
    dev, fecha, sin_match = desvios(a.carpeta, cat["metricas"])
    tablero = os.path.basename(os.path.normpath(a.carpeta)).replace("-", " ").title()
    titulo = a.titulo or f"Métricas {tablero}"
    data = dict(cat, desvios=dev, validacion=fecha, generado=date.today().isoformat())
    html = open(PLANTILLA, encoding="utf-8").read()
    html = (html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__TITULO__", titulo).replace("__TABLERO__", tablero)
                .replace("__ORIGEN__", cat.get("origen", "Origen")).replace("__DESTINO__", cat.get("destino", "Destino")))
    out = os.path.join(a.carpeta, "reporte-migracion.html")
    open(out, "w", encoding="utf-8").write(html)

    mig = [x for x in cat["metricas"] if x["estado"] == "migrada"]
    con_dif = [x["metrica"] for x in mig if x["id"] in dev and dev[x["id"]]["estado"] != "OK"]
    print(f"Reporte: {out}")
    print(f"Validadas: {sum(1 for x in mig if x['id'] in dev)}/{len(mig)} | con diferencias: {len(con_dif)}"
          + (f" ({'; '.join(con_dif)})" if con_dif else "")
          + (f" | {sin_match} caso(s) del validador sin métrica en el catálogo" if sin_match else ""))


if __name__ == "__main__":
    main()
