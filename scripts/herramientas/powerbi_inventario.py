"""
Inventario de un reporte Power BI en formato PBIP/PBIR.

Recorre <Nombre>.Report/definition/pages y lista, por página y visual,
qué medidas y columnas usa. Si se indica la carpeta del modelo semántico,
cruza contra las medidas definidas en el TMDL para detectar:
  - medidas usadas en visuales que no existen en el modelo
  - medidas definidas que ningún visual usa (candidatas a revisar/ocultar)

Solo lee metadatos (JSON/TMDL). No accede a datos.

Uso:
  python scripts/herramientas/powerbi_inventario.py "Gerencia Individual.Report" "Gerencia Individual.SemanticModel" validacion/inventario
"""
import csv
import glob
import json
import os
import re
import sys


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def title_of(visual):
    """Intenta obtener el título visible del visual."""
    for key in ("visualContainerObjects", "objects"):
        objs = visual.get("visual", {}).get(key, {}) if key == "objects" else visual.get(key, {})
        for t in objs.get("title", []):
            try:
                return t["properties"]["text"]["expr"]["Literal"]["Value"].strip("'")
            except (KeyError, TypeError):
                continue
    return ""


def field_ref(field):
    """Devuelve (tipo, tabla, nombre) de una proyección."""
    for kind in ("Measure", "Column", "Aggregation", "HierarchyLevel"):
        if kind in field:
            node = field[kind]
            if kind == "Aggregation":
                node = node.get("Expression", {}).get("Column", {})
                kind = "Column (agregada)"
            if kind == "HierarchyLevel":
                lvl = node.get("Level", "")
                node = node.get("Expression", {}).get("Hierarchy", {}).get("Expression", {})
                ent = node.get("SourceRef", {}).get("Entity", "")
                return kind, ent, lvl
            ent = node.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
            return kind, ent, node.get("Property", "")
    return "Otro", "", ""


def model_measures(model_dir):
    measures = {}
    for path in glob.glob(os.path.join(model_dir, "definition", "tables", "*.tmdl")):
        table = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                m = re.match(r"^\s*measure\s+('([^']+)'|([^\s=]+))", line)
                if m:
                    measures[m.group(2) or m.group(3)] = table
    return measures


def main(report_dir, model_dir=None, out_dir="validacion/inventario"):
    os.makedirs(out_dir, exist_ok=True)
    pages_dir = os.path.join(report_dir, "definition", "pages")
    rows = []
    for page_json in glob.glob(os.path.join(pages_dir, "*", "page.json")):
        page = load_json(page_json)
        page_name = page.get("displayName", page.get("name"))
        hidden = page.get("visibility") == "HiddenInViewMode"
        for vpath in glob.glob(os.path.join(os.path.dirname(page_json), "visuals", "*", "visual.json")):
            v = load_json(vpath)
            vtype = v.get("visual", {}).get("visualType", "")
            qstate = v.get("visual", {}).get("query", {}).get("queryState", {})
            for role, content in qstate.items():
                for proj in content.get("projections", []):
                    kind, table, name = field_ref(proj.get("field", {}))
                    rows.append({
                        "pagina": page_name,
                        "pagina_oculta": hidden,
                        "visual_id": v.get("name", ""),
                        "tipo_visual": vtype,
                        "titulo": title_of(v),
                        "rol": role,
                        "tipo_campo": kind,
                        "tabla": table,
                        "campo": name,
                    })

    inv_path = os.path.join(out_dir, "inventario_visuales.csv")
    with open(inv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["pagina"], delimiter=";")
        w.writeheader()
        w.writerows(rows)

    used = {r["campo"] for r in rows if r["tipo_campo"] == "Measure"}
    print(f"Páginas: {len({r['pagina'] for r in rows})} | Visuales con datos: {len({r['visual_id'] for r in rows})} | Medidas distintas usadas: {len(used)}")
    print(f"-> {inv_path}")

    if model_dir:
        defined = model_measures(model_dir)
        missing = sorted(used - set(defined))
        all_tmdl = "".join(
            open(pth, encoding="utf-8-sig").read()
            for pth in glob.glob(os.path.join(model_dir, "definition", "tables", "*.tmdl"))
        )
        not_in_visuals = set(defined) - used
        # usada dentro de otra medida: aparece como [Nombre] en el TMDL
        indirect = {m for m in not_in_visuals if all_tmdl.count(f"[{m}]") > 0}
        unused = sorted(not_in_visuals - indirect)
        chk_path = os.path.join(out_dir, "chequeo_medidas.csv")
        with open(chk_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["medida", "tabla", "estado"])
            for m in sorted(used & set(defined)):
                w.writerow([m, defined[m], "USADA"])
            for m in sorted(indirect):
                w.writerow([m, defined[m], "USADA DENTRO DE OTRA MEDIDA"])
            for m in unused:
                w.writerow([m, defined[m], "SIN USO (revisar)"])
            for m in missing:
                w.writerow([m, "", "USADA PERO NO EXISTE EN EL MODELO"])
        print(f"Medidas definidas: {len(defined)} | usadas en visuales: {len(used & set(defined))} | solo dentro de otras medidas: {len(indirect)} | sin uso: {len(unused)} | faltantes: {len(missing)}")
        print(f"-> {chk_path}")
        print("Nota: 'sin uso' puede incluir medidas usadas en filtros, formato condicional o bookmarks: revisar antes de borrar.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:4])
