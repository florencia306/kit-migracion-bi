"""Origen QlikView: expresiones.csv de qlik_vivo.py (recomendado), export de expresiones (.tab) o qlik_extraer_prj.py."""
import csv
import io
import re

NOMBRE = "QlikView"


def leer(ruta):
    text = open(ruta, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n")
    lines = text.split("\n")
    if ";" in lines[0] and "\t" not in lines[0]:  # expresiones.csv (qlik_vivo.py o qlik_extraer_prj.py)
        filas = list(csv.DictReader(io.StringIO(text), delimiter=";"))
        if filas and "hoja" in filas[0]:   # qlik_vivo.py: hoja;objeto;tipo;titulo;etiqueta;expresion
            return [(r["hoja"], r["objeto"], r["titulo"] or r["etiqueta"], r["expresion"]) for r in filas if r.get("expresion")]
        return [("", r[0], r[2], r[4]) for r in csv.reader(lines[1:], delimiter=";") if len(r) >= 5]
    recs = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 5 and parts[1] and parts[3]:
            recs.append([parts[0], parts[1], parts[2], "\t".join(parts[4:])])
        elif recs:
            recs[-1][3] += "\n" + line
    return [tuple(r) for r in recs]


def normalizar(expr):
    e = re.sub(r"//[^\n]*", "", expr)
    e = re.sub(r"\s+", " ", e).strip().lstrip("=").strip()
    m = re.match(r"(?is)^num\s*\((.*),\s*'[^']*'\s*\)$", e)
    return m.group(1).strip() if m else e
