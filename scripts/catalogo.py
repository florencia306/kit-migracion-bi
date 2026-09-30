"""
Catálogo de métricas: agrupa las expresiones de la herramienta de origen en métricas
de negocio y las cruza con las medidas del modelo de destino.

Uso:
  python scripts/catalogo.py <export_origen> <modelo_destino> <carpeta_salida> [--origen qlik] [--destino powerbi]

Por defecto origen y destino salen de migracion.yaml. Las reglas están en docs/reglas/<origen>.yaml.
Salida: catalogo.json, catalogo-metricas.csv y sin-clasificar.csv.
"""
import collections
import csv
import glob
import json
import os
import re
import sys

import argparse

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import conectores  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")



# ------------------------------------------------------------------ clasificación
def cortes(e, cfg):
    found = [c for c in cfg["cortes"] if re.search(c["patron"], e)]
    ids = {c["id"] for c in found}
    if "stock" in ids:
        found = [c for c in found if c["id"] != "mes"]
    return [c["nombre"] for c in found] or [cfg["sin_corte"]["nombre"]]


def regla(e, hojas, cfg, objetos=""):
    for r in cfg["reglas"]:
        if r.get("solo_hojas") and not set(hojas) <= set(r["solo_hojas"]):
            continue
        if r.get("objeto") and not re.search(r["objeto"], objetos):
            continue
        if all(re.search(p, e) for p in r.get("patrones", [])):
            return r
    return None


def main(src_path, model_dir, out_dir, origen, destino):
    org, dst = conectores.cargar_origen(origen), conectores.cargar_destino(destino)
    cfg = yaml.safe_load(open(os.path.join(RAIZ, "docs", "reglas", f"{origen}.yaml"), encoding="utf-8"))
    medidas = dst.medidas(model_dir) if model_dir and os.path.isdir(model_dir) else {}
    recs = org.leer(src_path)

    unicas = collections.OrderedDict()
    for hoja, oid, obj, expr in recs:
        n = org.normalizar(expr)
        if n:
            unicas.setdefault(n, []).append((hoja, oid, obj))

    info = {}   # por id de métrica: datos de la primera regla con revisión
    for r in cfg["reglas"]:
        d = info.setdefault(r["id"], {"area": r["area"], "metrica": r["metrica"], "medidas": [], "estado": r.get("estado"),
                                      "revision": "", "observacion": ""})
        d["medidas"] += [m for m in (r.get("medidas_destino") or r.get("medidas_pbi") or []) if m not in d["medidas"]]
        d["revision"] = d["revision"] or r.get("revision", "")
        d["observacion"] = d["observacion"] or r.get("observacion", "")

    met = collections.OrderedDict()
    sin = []
    por_objeto = []  # (hoja, objeto_id, objeto, metrica_id) -> lo usa mapeo_objetos.py
    for e, occ in unicas.items():
        hojas = sorted({o[0] for o in occ if o[0]})
        r = regla(e, hojas, cfg, " | ".join(sorted({o[2] for o in occ})))
        for o in occ:
            por_objeto.append((o[0], o[1], o[2], r["id"] if r else ""))
        if not r:
            sin.append((e, hojas, sorted({o[1] for o in occ})))
            continue
        base = info[r["id"]]
        m = met.setdefault(r["id"], {"id": r["id"], "area": base["area"], "metrica": base["metrica"], "n": 0, "ocurrencias": 0,
                                     "hojas": collections.Counter(), "cortes": collections.Counter(),
                                     "aggr": 0, "total": 0, "sin_distinct": 0, "ejemplos": []})
        m["n"] += 1
        m["ocurrencias"] += len(occ)
        for h in hojas:
            m["hojas"][h] += 1
        for c in cortes(e, cfg):
            m["cortes"][c] += 1
        if re.search(r"(?i)\baggr\s*\(|Dimensionality|\bAbove\s*\(", e):
            m["aggr"] += 1
        if re.search(r"(?i)\btotal\b", e) and "/" in e:
            m["total"] += 1
        if re.search(r"(?i)count\s*\(\s*\{", e) and "DISTINCT" not in e.upper():
            m["sin_distinct"] += 1
        if len(m["ejemplos"]) < 3:
            m["ejemplos"].append(e[:400])

    salida = []
    for k, m in met.items():
        base = info[k]
        existentes = [x for x in base["medidas"] if x in medidas] if medidas else base["medidas"]
        estado = base["estado"] or ("migrada" if existentes else "sin_medida")
        extra = []
        if m["aggr"]:
            extra.append(f"{m['aggr']} expresión(es) con Aggr/Above/Dimensionality: sin equivalente directo en {dst.LENGUAJE}.")
        if m["total"]:
            extra.append(f"{m['total']} expresión(es) de % sobre TOTAL: en el destino, '% del total' del visual o una medida sobre el total seleccionado.")
        salida.append({
            "id": k, "area": m["area"], "metrica": m["metrica"], "estado": estado,
            "medidas_destino": existentes, "expr_destino": {x: medidas.get(x, "") for x in existentes}, "medidas_faltantes": [x for x in base["medidas"] if medidas and x not in medidas],
            "expresiones": m["n"], "ocurrencias": m["ocurrencias"],
            "hojas": dict(m["hojas"].most_common()), "cortes": dict(m["cortes"].most_common()),
            "revision": base["revision"] if estado in ("migrada", "sin_medida") else "",
            "observacion": base["observacion"], "alertas": extra, "ejemplos": m["ejemplos"],
        })
    orden = {"migrada": 0, "sin_medida": 1, "fuera": 2, "tecnico": 3}
    sev = {"alta": 0, "media": 1, "baja": 2, "": 3}
    salida.sort(key=lambda x: (orden.get(x["estado"], 9), sev.get(x["revision"], 3), x["area"]))

    total_cortes = collections.Counter()
    for e in unicas:
        for c in cortes(e, cfg):
            total_cortes[c] += 1
    stats = {"expresiones": len(recs), "unicas": len(unicas), "hojas": len({r[0] for r in recs if r[0]}),
             "objetos": len({r[1] for r in recs}), "metricas": len(salida), "sin_clasificar": len(sin),
             "cortes": dict(total_cortes.most_common()), "medidas_modelo": len(medidas)}

    os.makedirs(out_dir, exist_ok=True)
    json.dump({"origen": org.NOMBRE, "destino": dst.NOMBRE, "lenguaje_destino": dst.LENGUAJE, "stats": stats, "cortes_cfg": cfg["cortes"] + [cfg["sin_corte"]], "metricas": salida},
              open(os.path.join(out_dir, "catalogo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "catalogo-metricas.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "area", "metrica", "estado", "medidas_destino", "expresiones_origen", "cortes_origen", "revision", "observacion"])
        for x in salida:
            w.writerow([x["id"], x["area"], x["metrica"], x["estado"], " | ".join(x["medidas_destino"]), x["expresiones"],
                        ", ".join(f"{k}:{v}" for k, v in x["cortes"].items()), x["revision"],
                        " ".join([x["observacion"]] + x["alertas"]).strip()])
    with open(os.path.join(out_dir, "objetos-origen.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["hoja", "objeto_id", "objeto", "metrica_id"])
        w.writerows(sorted(set(por_objeto)))
    with open(os.path.join(out_dir, "sin-clasificar.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["hojas", "objetos", "expresion"])
        for e, h, o in sin:
            w.writerow([", ".join(h), ", ".join(o), e[:500]])

    # resumen corto para el agente
    est = collections.Counter(x["estado"] for x in salida)
    alta = [x["metrica"] for x in salida if x["revision"] == "alta"]
    print(f"{stats['expresiones']} expresiones | {stats['unicas']} únicas | {stats['metricas']} métricas | "
          + " | ".join(f"{k}: {v}" for k, v in est.items()) + f" | sin clasificar: {len(sin)}")
    if alta:
        print("Revisión alta: " + "; ".join(alta))
    faltan = sorted({m for x in salida for m in x["medidas_faltantes"]})
    if faltan:
        print("Medidas de las reglas que no existen en el modelo: " + "; ".join(faltan))
    print(f"-> {out_dir}")


if __name__ == "__main__":
    cfg_mig = yaml.safe_load(open(os.path.join(RAIZ, "migracion.yaml"), encoding="utf-8"))
    ap = argparse.ArgumentParser()
    ap.add_argument("export_origen")
    ap.add_argument("modelo_destino")
    ap.add_argument("salida")
    ap.add_argument("--origen", default=cfg_mig["origen"])
    ap.add_argument("--destino", default=cfg_mig["destino"])
    a = ap.parse_args()
    main(a.export_origen, a.modelo_destino, a.salida, a.origen, a.destino)
