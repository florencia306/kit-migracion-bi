"""
QlikView en vivo (automatización COM de QlikView Desktop). Solo Windows, con QlikView Desktop instalado.

Reemplaza los exports manuales: extrae todo del .qvw y lee los valores de cualquier objeto
con el período y las selecciones que se pidan. Por defecto usa el documento que ya está
abierto en QlikView; si no hay ninguno, abre el .qvw indicado (sin recargar datos).

Uso:
  # 1) Extraer hojas, objetos, expresiones, variables y script (una vez por tablero)
  #    Con la carpeta Frontend toma todos sus .qvw. Uno solo: IDs como CH05. Varios: Documento/CH05.
  python scripts/herramientas/qlik_vivo.py extraer tableros/<t>/qlik/Frontend tableros/<t>/origen

  # 1b) Scripts de carga de TODOS los .qvw de la carpeta de QlikView (Descargar, Store, Frontend...)
  python scripts/herramientas/qlik_vivo.py scripts tableros/<t>/qlik tableros/<t>/origen/scripts

  # 2) Ver qué devuelve un objeto con un período (solo muestra un resumen; no imprime datos)
  python scripts/herramientas/qlik_vivo.py datos tableros/<t>/qlik/Frontend CH05 --var vPeriodoReporte=202608 --sel "Año=2025,2026"

Salida de "extraer" en la carpeta indicada:
  expresiones.csv  hoja;objeto;tipo;titulo;etiqueta;expresion   (lo lee catalogo.py)
  objetos.csv      hoja;objeto;tipo;titulo;dimensiones;expresiones
  variables.csv    nombre;valor   (con varios Frontend: documento;nombre;valor)
  script.qvs       script de carga, con credenciales ocultas (varios: script_<Documento>.qvs)

Requisito: pip install pywin32
Nota: la API COM de QlikView cambia poco entre versiones, pero si algún dato no aparece,
el script sigue con el resto y lo informa al final.
"""
import argparse
import csv
import glob
import os
import re
import sys
import tempfile
import time

PREFIJOS = {"CH": "grafico", "TX": "texto", "LB": "lista", "TB": "tabla simple", "MB": "multibox",
            "BU": "boton", "IB": "input", "CS": "selecciones", "CT": "contenedor", "SO": "busqueda", "SL": "slider"}
_avisos = []


def _v(x):
    """Los textos de la API vienen a veces como objeto con .v"""
    try:
        return x.v
    except AttributeError:
        return "" if x is None else str(x)


def _try(f, defecto=None, aviso=None):
    try:
        return f()
    except Exception as e:  # la API COM falla distinto según el tipo de objeto
        if aviso:
            _avisos.append(f"{aviso}: {str(e)[:80]}")
        return defecto


# ------------------------------------------------------------------ conexión
def conectar(qvw=None):
    """Devuelve (app, doc, abierto_por_nosotros)."""
    try:
        import win32com.client
    except ImportError:
        sys.exit("Falta pywin32: pip install pywin32 (y QlikView Desktop instalado).")
    app = None
    try:
        app = win32com.client.GetActiveObject("QlikTech.QlikView")
    except Exception:
        pass
    if app is not None:
        doc = _try(lambda: app.ActiveDocument)
        if doc is not None and (not qvw or os.path.basename(_v(doc.GetPathName())).lower() == os.path.basename(qvw).lower()):
            return app, doc, False
    if not qvw:
        sys.exit("No hay un documento abierto en QlikView. Indicá la ruta del .qvw.")
    app = app or win32com.client.Dispatch("QlikTech.QlikView")
    doc = app.OpenDoc(os.path.abspath(qvw), "", "")
    esperar(doc)
    return app, doc, True


def esperar(doc):
    _try(lambda: doc.GetApplication().WaitForIdle())
    time.sleep(0.2)


# ------------------------------------------------------------------ extracción
def tipo_objeto(oid):
    corto = oid.split("\\")[-1]
    return PREFIJOS.get(corto[:2].upper(), "otro")


def expresiones_de(obj):
    """[(etiqueta, definicion)] de un gráfico o tabla."""
    out = []
    p = _try(lambda: obj.GetProperties())
    if p is None:
        return out
    exprs = _try(lambda: p.Expressions)
    n = _try(lambda: exprs.Count, 0) if exprs is not None else 0
    for i in range(n):
        e = _try(lambda: exprs.Item(i).Item(0).Data)
        if e is None:
            continue
        d = _v(_try(lambda: e.ExpressionData.Definition, ""))
        lab = _v(_try(lambda: e.ExpressionVisual.Label, ""))
        if d.strip():
            out.append((lab, d))
    return out


def dimensiones_de(obj):
    p = _try(lambda: obj.GetProperties())
    dims = _try(lambda: p.Dimensions) if p is not None else None
    n = _try(lambda: dims.Count, 0) if dims is not None else 0
    return [_v(_try(lambda: dims.Item(i).PseudoDef.Definition, "")) for i in range(n)]


def texto_de(obj):
    return _v(_try(lambda: obj.GetProperties().Layout.Text, ""))


def titulo_de(obj):
    return _v(_try(lambda: obj.GetCaption().Name, "")).replace("\n", " ").strip()


def ocultar_credenciales(script):
    """Oculta líneas CONNECT y usuarios/contraseñas antes de guardar el script."""
    script = re.sub(r"(?im)^[ \t]*(ODBC|OLEDB|CUSTOM|LIB)?[ \t]*CONNECT(32|64)?\b.*$", "// [conexión oculta]", script)
    script = re.sub(r"(?i)\b(XUserId|XPassword|UserId|Password)\s+is\s+\S+?(?=[,)\s])", r"\1 is [oculto]", script)
    return re.sub(r"(?i)\b(pwd|password|xpassword|user id|uid)\s*=\s*[^;\"\]]*", r"\1=[oculto]", script)


def recolectar(doc, prefijo=""):
    """Objetos, expresiones, variables y script de un documento. Con prefijo (varios Frontend),
    los IDs quedan 'Documento/CH05' y las hojas 'Documento · Hoja' para que no choquen."""
    filas, objetos = [], []
    n_hojas = _try(lambda: doc.NoOfSheets(), 0)
    for i in range(n_hojas):
        sh = doc.GetSheet(i)
        hoja = _v(_try(lambda: sh.GetProperties().Name, f"Hoja{i + 1}"))
        hoja_p = f"{prefijo} · {hoja}" if prefijo else hoja
        for obj in _try(lambda: sh.GetSheetObjects(), [], f"objetos de {hoja}") or []:
            oid = _v(_try(lambda: obj.GetObjectId(), "")).split("\\")[-1]
            tipo, titulo = tipo_objeto(oid), titulo_de(obj)
            oid_p = f"{prefijo}/{oid}" if prefijo else oid
            exprs = expresiones_de(obj) if tipo in ("grafico", "tabla simple") else []
            if tipo == "texto":
                t = texto_de(obj)
                if t.strip().startswith("="):
                    exprs = [("texto", t)]
            dims = dimensiones_de(obj) if tipo == "grafico" else []
            for lab, d in exprs:
                filas.append([hoja_p, oid_p, tipo, titulo, lab, d])
            objetos.append([hoja_p, oid_p, tipo, titulo, " | ".join(dims), len(exprs)])
    vars_ = []
    vd = _try(lambda: doc.GetVariableDescriptions(), None, "variables")
    for i in range(_try(lambda: vd.Count, 0) if vd is not None else 0):
        nom = _try(lambda: vd.Item(i).Name, "")
        vars_.append(([prefijo] if prefijo else []) + [nom, _try(lambda: doc.Variables(nom).GetRawContent(), "")])
    script = _try(lambda: doc.GetScript(), "", "script")
    return filas, objetos, vars_, script


def documentos(fuentes):
    """Rutas .qvw a partir de archivos y/o carpetas (p. ej. qlik/Frontend). Vacío = documento abierto."""
    out = []
    for f in fuentes or []:
        if os.path.isdir(f):
            out += sorted(glob.glob(os.path.join(f, "**", "*.qvw"), recursive=True))
        else:
            out.append(f)
    return out


def separar(objeto):
    """'RealBudget/CH05' -> ('RealBudget', 'CH05');  'CH05' -> (None, 'CH05')"""
    doc, _, oid = objeto.rpartition("/")
    return (doc or None), oid


def resolver_qvw(fuente, nombre_doc):
    """Con varios Frontend: el .qvw cuyo nombre coincide con el prefijo del objeto."""
    qvws = documentos([fuente]) if fuente else []
    if not nombre_doc:
        if len(qvws) > 1:
            raise ValueError(f"Hay {len(qvws)} documentos en {fuente}: escribí el objeto como <Documento>/<ID>")
        return qvws[0] if qvws else fuente
    for q in qvws:
        if os.path.splitext(os.path.basename(q))[0].lower() == nombre_doc.lower():
            return q
    raise ValueError(f"No encontré {nombre_doc}.qvw en {fuente}")


def extraer(fuentes, salida):
    os.makedirs(salida, exist_ok=True)
    qvws = documentos(fuentes)
    multi = len(qvws) > 1
    filas, objetos, vars_, scripts = [], [], [], {}
    for q in (qvws or [None]):
        app, doc, propio = conectar(q)
        nombre = os.path.splitext(os.path.basename(q or _v(doc.GetPathName())))[0]
        try:
            f, o, v, sc = recolectar(doc, nombre if multi else "")
        finally:
            if propio:
                _try(lambda: doc.CloseDoc())
        filas += f
        objetos += o
        vars_ += v
        if sc:
            scripts[nombre] = sc
        if multi:
            print(f"  {nombre}: objetos {len(o)} | expresiones {len(f)}")

    def escribir(nombre, cab, rows):
        with open(os.path.join(salida, nombre), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(cab)
            w.writerows(rows)

    escribir("expresiones.csv", ["hoja", "objeto", "tipo", "titulo", "etiqueta", "expresion"], filas)
    escribir("objetos.csv", ["hoja", "objeto", "tipo", "titulo", "dimensiones", "expresiones"], objetos)
    escribir("variables.csv", (["documento"] if multi else []) + ["nombre", "valor"], vars_)
    for nombre, sc in scripts.items():
        archivo = f"script_{nombre}.qvs" if multi else "script.qvs"
        open(os.path.join(salida, archivo), "w", encoding="utf-8").write(ocultar_credenciales(sc))

    hojas = len({f[0] for f in objetos})
    docs = f"documentos: {len(qvws)} | " if multi else ""
    print(f"{docs}Hojas: {hojas} | objetos: {len(objetos)} | expresiones: {len(filas)} | variables: {len(vars_)} | script: {'sí' if scripts else 'no'}")
    print(f"-> {salida}")


# ------------------------------------------------------------------ datos de un objeto
def aplicar_contexto(doc, variables=None, selecciones=None, limpiar=True):
    """Fija variables y selecciones. Devuelve los valores originales de las variables para restaurarlos."""
    originales = {}
    if limpiar:
        doc.ClearAll(False)
    for k, v in (variables or {}).items():
        var = doc.Variables(k)
        if var is None:
            raise ValueError(f"La variable {k} no existe en el documento")
        originales[k] = var.GetRawContent()
        var.SetContent(str(v), True)
    for campo, valores in (selecciones or {}).items():
        valores = valores if isinstance(valores, (list, tuple)) else [valores]
        f = doc.Fields(campo)
        if f is None:
            raise ValueError(f"El campo {campo} no existe en el documento")
        f.Select(str(valores[0]))
        for x in valores[1:]:
            f.ToggleSelect(str(x))
    esperar(doc)
    return originales


def restaurar(doc, originales):
    for k, v in originales.items():
        _try(lambda: doc.Variables(k).SetContent(v, True))
    esperar(doc)


def _numero(celda):
    n = _try(lambda: celda.Number)
    if isinstance(n, float) and n == n and abs(n) < 1e300:
        return n
    return _try(lambda: celda.Text, "")


def datos_objeto(doc, objeto):
    """DataFrame con las columnas del objeto (dimensiones como texto, expresiones como número).
    Soporta gráficos y tablas simples; una tarjeta de texto devuelve una sola fila con columna 'valor'."""
    import pandas as pd
    obj = doc.GetSheetObject(objeto)
    if obj is None:
        raise ValueError(f"No existe el objeto {objeto}")
    if tipo_objeto(objeto) == "texto":
        t = _try(lambda: obj.GetText(), "") or texto_de(obj)
        return pd.DataFrame({"valor": [t]})
    try:
        nr, nc, nd = obj.GetRowCount(), obj.GetColumnCount(), len(dimensiones_de(obj))
        cab = [obj.GetCell(0, c).Text for c in range(nc)]
        filas = [[obj.GetCell(r, c).Text if c < nd else _numero(obj.GetCell(r, c))
                  for c in range(nc)] for r in range(1, nr)]
        return pd.DataFrame(filas, columns=cab)
    except Exception:
        # alternativa: exportar a un archivo temporal y borrarlo
        tmp = os.path.join(tempfile.gettempdir(), f"qv_{objeto}.csv")
        obj.Export(tmp, ";")
        try:
            return pd.read_csv(tmp, sep=";", dtype=str, encoding="utf-8-sig")
        finally:
            _try(lambda: os.remove(tmp))


def scripts_de_carpeta(carpeta, salida, excluir=("TempDesarrollo",)):
    """Script de carga de cada .qvw de la carpeta (Descargar, Store, Frontend...), abriéndolos SIN datos."""
    import win32com.client
    app = None
    try:
        app = win32com.client.GetActiveObject("QlikTech.QlikView")
    except Exception:
        app = win32com.client.Dispatch("QlikTech.QlikView")
    qvws = [p for p in sorted(glob.glob(os.path.join(carpeta, "**", "*.qvw"), recursive=True))
            if not any(x.lower() in p.lower().split(os.sep) for x in (e.lower() for e in excluir))]
    ok = 0
    for p in qvws:
        rel = os.path.splitext(os.path.relpath(p, carpeta))[0] + ".qvs"
        doc = _try(lambda: app.OpenDocEx(os.path.abspath(p), 0, True, "", "", "", True))   # solo lectura, sin datos
        doc = doc or _try(lambda: app.OpenDoc(os.path.abspath(p), "", ""), None, f"no se pudo abrir {os.path.basename(p)}")
        if doc is None:
            continue
        script = _try(lambda: doc.GetScript(), "", f"script de {os.path.basename(p)}")
        _try(lambda: doc.CloseDoc())
        if script:
            destino = os.path.join(salida, rel)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            open(destino, "w", encoding="utf-8").write(ocultar_credenciales(script))
            ok += 1
    print(f"QVW encontrados: {len(qvws)} | scripts extraídos: {ok} (excluidas: {', '.join(excluir)})")
    print(f"-> {salida}")


def _kv(pares, lista=False):
    out = {}
    for p in pares or []:
        k, _, v = p.partition("=")
        out[k.strip()] = [x.strip() for x in v.split(",")] if lista else v.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extraer")
    e.add_argument("fuentes", nargs="*", help=".qvw o carpeta Frontend (todos sus .qvw). Vacío = documento abierto")
    e.add_argument("salida")
    d = sub.add_parser("datos")
    d.add_argument("qvw", help=".qvw o carpeta Frontend")
    d.add_argument("objeto", help="CH05, o Documento/CH05 si hay varios Frontend")
    d.add_argument("--var", action="append")
    d.add_argument("--sel", action="append")
    d.add_argument("--guardar", help="CSV local (fuera del repo) con el resultado")
    sc = sub.add_parser("scripts", help="scripts de carga de todos los .qvw de una carpeta (sin abrir datos)")
    sc.add_argument("carpeta")
    sc.add_argument("salida")
    sc.add_argument("--excluir", default="TempDesarrollo", help="subcarpetas a ignorar, separadas por coma")
    a = ap.parse_args()

    if a.cmd == "scripts":
        scripts_de_carpeta(a.carpeta, a.salida, [x.strip() for x in a.excluir.split(",") if x.strip()])
        if _avisos:
            print(f"Avisos ({len(_avisos)}): " + " · ".join(_avisos[:5]))
        return
    if a.cmd == "extraer":
        extraer(a.fuentes, a.salida)
        if _avisos:
            print(f"Avisos ({len(_avisos)}): " + " · ".join(_avisos[:5]))
        return
    nombre_doc, oid = separar(a.objeto)
    app, doc, propio = conectar(resolver_qvw(a.qvw, nombre_doc))
    try:
        orig = aplicar_contexto(doc, _kv(a.var), _kv(a.sel, lista=True))
        try:
            df = datos_objeto(doc, oid)
        finally:
            restaurar(doc, orig)
        print(f"{a.objeto}: {len(df)} filas | columnas: {', '.join(map(str, df.columns))}")
        if a.guardar:
            df.to_csv(a.guardar, sep=";", index=False, encoding="utf-8-sig")
            print(f"-> {a.guardar}")
    finally:
        if propio:
            _try(lambda: doc.CloseDoc())
    if _avisos:
        print(f"Avisos ({len(_avisos)}): " + " · ".join(_avisos[:5]))


if __name__ == "__main__":
    main()
