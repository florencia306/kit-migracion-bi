"""Origen Tableau (BETA): campos calculados de un libro .twb o .twbx."""
import re
import xml.etree.ElementTree as ET
import zipfile

NOMBRE = "Tableau"


def _xml(ruta):
    if ruta.lower().endswith(".twbx"):
        with zipfile.ZipFile(ruta) as z:
            twb = next(n for n in z.namelist() if n.lower().endswith(".twb"))
            return ET.fromstring(z.read(twb))
    return ET.parse(ruta).getroot()


def leer(ruta):
    root, out = _xml(ruta), []
    for ds in root.iter("datasource"):
        fuente = ds.get("caption") or ds.get("name", "")
        for col in ds.iter("column"):
            calc = col.find("calculation")
            if calc is not None and calc.get("formula"):
                nombre = col.get("caption") or col.get("name", "").strip("[]")
                out.append((fuente, col.get("name", ""), nombre, calc.get("formula")))
    return out


def normalizar(expr):
    e = re.sub(r"//[^\n]*", "", expr)
    return re.sub(r"\s+", " ", e).strip()
