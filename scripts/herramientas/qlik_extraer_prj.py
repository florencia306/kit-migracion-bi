"""
Extrae las expresiones de un proyecto de QlikView (-prj) a un CSV compacto.

En vez de que el agente lea decenas de XML (muchos tokens), lee un solo CSV:
  objeto;tipo;titulo;etiqueta;expresion

Uso:
  python scripts/extraer_qlik.py tableros/<tablero>/qlik/<Tablero>-prj tableros/<tablero>/qlik/expresiones.csv

Nota: la estructura de los XML varía entre versiones de QlikView. El script
busca de forma genérica los nodos de expresión ("Definition") y de variables.
Si en tu versión algo no aparece, revisá un XML de ejemplo y ajustá TAGS_*.
"""
import csv
import glob
import os
import sys
import xml.etree.ElementTree as ET

TAGS_EXPR = {"Definition"}                    # texto de la expresión
TAGS_LABEL = ("Label", "Name", "Title")        # etiqueta de la expresión (hermanos)
TAGS_TITLE = ("Caption", "Title", "Text")      # título del objeto
TAGS_TYPE = ("ObjectType", "Type")


def text(node, tags):
    for t in tags:
        el = node.find(f".//{t}")
        if el is not None and (el.text or "").strip():
            return el.text.strip()
    return ""


def parse(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    obj = os.path.splitext(os.path.basename(path))[0]
    title = text(root, TAGS_TITLE)
    otype = text(root, TAGS_TYPE)
    parent = {c: p for p in root.iter() for c in p}
    rows = []
    for el in root.iter():
        if el.tag in TAGS_EXPR and (el.text or "").strip():
            p = parent.get(el, root)
            label = ""
            for t in TAGS_LABEL:
                s = p.find(t)
                if s is not None and (s.text or "").strip():
                    label = s.text.strip()
                    break
            expr = " ".join(el.text.split())  # una sola línea
            rows.append([obj, otype, title, label, expr])
        # variables del documento
        if el.tag == "Variable" or el.tag.endswith("VariableProperties"):
            name = text(el, ("Name",))
            val = text(el, ("RawValue", "Value", "Definition"))
            if name:
                rows.append(["VARIABLE", "variable", "", name, " ".join(val.split())])
    return rows


def main(prj, out):
    rows, seen = [], set()
    for path in sorted(glob.glob(os.path.join(prj, "*.xml"))):
        for r in parse(path):
            key = (r[0], r[3], r[4])
            if r[4] and key not in seen:
                seen.add(key)
                rows.append(r)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["objeto", "tipo", "titulo", "etiqueta", "expresion"])
        w.writerows(rows)
    n_var = sum(1 for r in rows if r[0] == "VARIABLE")
    print(f"{len(rows) - n_var} expresiones y {n_var} variables -> {out}")
    script = os.path.join(prj, "LoadScript.txt")
    if os.path.exists(script):
        print(f"Script de carga: {script}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
