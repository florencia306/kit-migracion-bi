"""
Modelo de datos del origen QlikView a partir del script de carga y de los QVD (sin leer datos).

Lee el script (script.qvs extraído con qlik_vivo.py, o la carpeta source/ con .qvs/.txt e
includes) y la cabecera XML de cada QVD (campos y cantidad de filas; nunca los datos).
Sirve para armar docs/mapeo.md (campo Qlik -> columna del modelo destino) y para encontrar
filtros y transformaciones que hay que replicar.

Uso:
  python scripts/herramientas/qlik_script.py tableros/<t>/origen/script.qvs tableros/<t>/origen [--qvd tableros/<t>/qlik/qvd]
  python scripts/herramientas/qlik_script.py tableros/<t>/origen/scripts tableros/<t>/qlik/Resources tableros/<t>/origen --qvd tableros/<t>/qlik

Salida:
  modelo-origen.csv  tabla;campo;expresion;archivo_script
  tablas-origen.csv  tabla;tipo_carga;fuente;filtro;guarda_en;generado_por;archivo_script

Tableros que leen QVD de otro (p. ej. Cartera): --base cartera=tableros/cartera/origen/scripts agrega
en "generado_por" qué tabla y script de Cartera arma cada QVD (y su filtro), para seguir la lógica hasta el origen.
  qvd-campos.csv     qvd;campo;filas   (si se pasa --qvd)
"""
import argparse
import collections
import csv
import glob
import os
import re

EXT = (".qvs", ".txt", ".qvw.log")


# ------------------------------------------------------------------ lectura del script
def leer_script(rutas):
    """Devuelve [(archivo, texto)] de uno o varios archivos/carpetas, resolviendo $(Include=...).
    Si la ruta del include no existe (rutas absolutas o con variables), lo busca por nombre en las carpetas dadas."""
    rutas = [rutas] if isinstance(rutas, str) else rutas
    archivos, indice = [], {}
    for r in rutas:
        if os.path.isdir(r):
            todos = sorted(p for p in glob.glob(os.path.join(r, "**", "*"), recursive=True) if p.lower().endswith(EXT))
            archivos += todos
            for p in todos:
                indice.setdefault(os.path.basename(p).lower(), p)
        elif os.path.exists(r):
            archivos.append(r)
    out, vistos = [], set()

    def cargar(p):
        p = os.path.normpath(p)
        if p in vistos or not os.path.exists(p):
            return
        vistos.add(p)
        txt = open(p, encoding="utf-8-sig", errors="replace").read()
        out.append((os.path.basename(p), txt))
        for inc in re.findall(r"(?i)\$\((?:must_)?include\s*=\s*([^)]+)\)", txt):
            inc = inc.strip().strip("'\"[]")
            directo = os.path.join(os.path.dirname(p), inc)
            nombre = re.split(r"[\\/]", inc)[-1].lower()
            cargar(directo if os.path.exists(directo) else indice.get(nombre, directo))

    for a in archivos:
        cargar(a)
    return out


def sin_comentarios(t):
    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
    t = re.sub(r"(?m)(^|[^:])//[^\n]*", r"\1", t)     # no corta "lib://" ni "http://"
    return re.sub(r"(?im)^\s*REM\b[^;]*;", " ", t)


def partir(texto, sep=","):
    """Divide por sep respetando paréntesis, corchetes y comillas."""
    partes, nivel, buf, q = [], 0, [], None
    for ch in texto:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch in "([":
            nivel += 1
        elif ch in ")]":
            nivel -= 1
        if ch == sep and nivel == 0:
            partes.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        partes.append("".join(buf))
    return [p.strip() for p in partes if p.strip()]


def campo(expr):
    """'expr as Alias' -> (Alias, expr). Sin alias: el propio campo."""
    m = re.match(r"(?is)^(.*)\s+as\s+(\[[^\]]+\]|\"[^\"]+\"|\w+)$", expr.strip())
    if m:
        return m.group(2).strip("[]\""), re.sub(r"\s+", " ", m.group(1)).strip()
    e = re.sub(r"\s+", " ", expr).strip()
    return e.strip("[]\""), e


FUENTE = r"(?is)\b(FROM|RESIDENT)\s+(\[[^\]]+\]|'[^']+'|\S+)|\b(INLINE|AUTOGENERATE)\b"


def campos_de(st):
    m = re.match(r"(?is)^(?:LOAD|SQL\s+SELECT|SELECT)\s+(?:DISTINCT\s+)?(.*?)(?:\bFROM\b|\bRESIDENT\b|\bINLINE\b|\bAUTOGENERATE\b|$)", st)
    return partir(m.group(1)) if m else []


def analizar(archivos):
    """Tablas y campos del script. Resuelve preceding loads (LOAD sin FROM que toma de la carga siguiente)."""
    tablas, campos = [], []
    for arch, txt in archivos:
        txt = sin_comentarios(txt)
        etiqueta, pend = None, []   # pend: preceding loads acumulados [(prefijo, campos)]
        for st in partir(txt, ";"):
            st = st.strip()
            m = re.match(r"(?is)^(\[[^\]]+\]|[\w ]+?)\s*:\s*(.*)$", st)
            if m and not re.match(r"(?i)^(lib|http|https|[a-z])$", m.group(1).strip()):
                etiqueta, st = m.group(1).strip("[] "), m.group(2).strip()
            store = re.match(r"(?is)^STORE\s+(.+?)\s+INTO\s+(.+?)(\s*\(\s*\w+\s*\))?$", st)
            if store:
                for t in tablas[::-1]:
                    if t["tabla"].lower() == store.group(1).strip("[] ").lower():
                        t["guarda_en"] = store.group(2).strip("[]'\" ")
                        break
                continue
            prefijo = re.match(r"(?is)^((?:NOCONCATENATE|CONCATENATE|LEFT|RIGHT|INNER|OUTER|JOIN|KEEP|MAPPING|BUFFER|DISTINCT)"
                               r"(?:\s*\([^)]*\))?\s*)*", st).group(0)
            cuerpo = st[len(prefijo):]
            if not re.match(r"(?is)^(LOAD|SELECT|SQL\s+SELECT)\b", cuerpo):
                if re.match(r"(?i)^drop\b", st):
                    etiqueta = None
                continue
            if re.match(r"(?is)^LOAD\b", cuerpo) and not re.search(FUENTE, cuerpo):
                pend.append((prefijo, campos_de(cuerpo)))    # preceding load
                continue
            if pend:                                        # el primero de la cadena es el que define la tabla
                prefijo = pend[0][0] or prefijo
                lista = []
                for _, cs in pend + [(None, campos_de(cuerpo))]:
                    lista += [c for c in cs if c != "*"]
                    if "*" not in cs:
                        break
                todos = [cuerpo] + [" ".join(c) for _, c in pend]
            else:
                lista, todos = campos_de(cuerpo), [cuerpo]
            pl = prefijo.lower()
            tipo = " ".join(x for x, ok in (("MAPPING", "mapping" in pl), ("JOIN", "join" in pl), ("KEEP", "keep" in pl),
                                            ("CONCATENATE", re.search(r"(?<!no)concatenate", pl))) if ok) or "LOAD"
            f = re.search(FUENTE, cuerpo)
            fuente = (f"{f.group(1).upper()} {f.group(2).strip('[]')}" if f.group(1) else f.group(3).upper()) if f else ""
            filtro = " / ".join(re.sub(r"\s+", " ", w).strip() for x in todos
                                for w in re.findall(r"(?is)\bWHERE\b(.*?)(?:\bGROUP BY\b|\bORDER BY\b|$)", x))
            destino = re.search(r"\(([^)]+)\)", prefijo)
            nombre = etiqueta or (destino.group(1).strip("[] ") if destino else None) or \
                (tablas[-1]["tabla"] if tipo != "LOAD" and tablas else f"(sin nombre {len(tablas) + 1})")
            tablas.append({"tabla": nombre, "tipo_carga": tipo, "fuente": fuente,
                           "filtro": filtro[:300], "guarda_en": "", "archivo_script": arch})
            for c in lista:
                n, e = campo(c)
                campos.append([nombre, n, e[:300], arch])
            etiqueta, pend = None, []
    return tablas, campos


def nombre_qvd(ruta):
    """'FROM $(vRuta)..\\Store\\Polizas.qvd' -> 'polizas.qvd'"""
    r = re.sub(r"(?i)^(FROM|RESIDENT)\s+", "", ruta.strip())
    return re.split(r"[\\/)]", r)[-1].strip("[]'\" ").lower()


# ------------------------------------------------------------------ QVD (solo cabecera)
def cabecera_qvd(ruta):
    with open(ruta, "rb") as f:
        buf = b""
        while b"</QvdTableHeader>" not in buf:
            trozo = f.read(65536)
            if not trozo:
                break
            buf += trozo
            if len(buf) > 20_000_000:
                break
    xml = buf.split(b"</QvdTableHeader>")[0].decode("utf-8", "replace")
    campos = re.findall(r"<FieldName>(.*?)</FieldName>", xml)
    filas = re.search(r"<NoOfRecords>(\d+)</NoOfRecords>", xml)
    return campos, int(filas.group(1)) if filas else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="+", help="uno o más: script.qvs, carpeta de scripts extraídos, carpeta Resources con includes")
    ap.add_argument("salida")
    ap.add_argument("--qvd", action="append", help="carpeta con QVD (solo cabecera); se puede repetir")
    ap.add_argument("--base", action="append", default=[],
                    help="nombre=carpeta de scripts de un tablero que genera QVD compartidos (ej. cartera=tableros/cartera/origen/scripts)")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    archivos = leer_script(a.script)
    tablas, campos = analizar(archivos)

    # linaje: qué script genera (STORE) cada QVD que se lee, propio o de un tablero base
    genera = {}
    for t in tablas:
        if t["guarda_en"]:
            genera.setdefault(nombre_qvd(t["guarda_en"]), f"propio: {t['tabla']} ({t['archivo_script']})")
    for b in a.base:
        nom, _, ruta = b.partition("=")
        rutas = [x for x in (ruta, os.path.join(os.path.dirname(os.path.dirname(ruta)), "qlik", "Resources")) if os.path.exists(x)]
        for t in analizar(leer_script(rutas))[0]:
            if t["guarda_en"]:
                genera.setdefault(nombre_qvd(t["guarda_en"]), f"{nom}: {t['tabla']} ({t['archivo_script']})" + (f" · filtro: {t['filtro'][:80]}" if t["filtro"] else ""))
    for t in tablas:
        q = nombre_qvd(t["fuente"]) if t["fuente"].lower().endswith(".qvd") else ""
        t["generado_por"] = genera.get(q, "no encontrado") if q else ""

    def escribir(nombre, cab, rows):
        with open(os.path.join(a.salida, nombre), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cab)
            w.writerows(rows)

    escribir("modelo-origen.csv", ["tabla", "campo", "expresion", "archivo_script"], campos)
    cols = ["tabla", "tipo_carga", "fuente", "filtro", "guarda_en", "generado_por", "archivo_script"]
    escribir("tablas-origen.csv", cols, [[t[k] for k in cols] for t in tablas])
    msg = f"Script: {len(archivos)} archivo(s) | tablas/cargas: {len(tablas)} | campos: {len(campos)} | con filtro: {sum(1 for t in tablas if t['filtro'])}"
    lee_qvd = [t for t in tablas if t["generado_por"]]
    if lee_qvd:
        orig = collections.Counter(t["generado_por"].split(":")[0] for t in lee_qvd)
        msg += " | lee QVD de: " + ", ".join(f"{k} ({v})" for k, v in orig.most_common())
    if a.qvd:
        filas = []
        for p in sorted({x for d in a.qvd for x in glob.glob(os.path.join(d, "**", "*.qvd"), recursive=True)}):
            cs, n = cabecera_qvd(p)
            filas += [[os.path.basename(p), c, n] for c in cs]
        escribir("qvd-campos.csv", ["qvd", "campo", "filas"], filas)
        msg += f" | QVD: {len({f[0] for f in filas})} con {len(filas)} campos"
    print(msg)
    print(f"-> {a.salida}")


if __name__ == "__main__":
    main()
