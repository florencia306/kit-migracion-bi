"""
Mapa de objetos origen ↔ destino (trazabilidad de la migración).

Empareja cada objeto del origen (gráfico, tabla, tarjeta de Qlik) con los visuales del
destino (Power BI) que muestran las mismas métricas. La migración no es 1:1, así que
el script propone y la persona (o el agente) confirma en mapa-objetos.yaml.

Entradas:
  - <resultados>/catalogo.json y objetos-origen.csv   (de catalogo.py)
  - inventario de visuales del destino                  (de herramientas/powerbi_inventario.py)
  - modelo del destino (opcional)                       (para seguir medidas que usan otras medidas)
  - tableros/<t>/mapa-objetos.yaml (opcional)           (decisiones confirmadas)

Uso:
  python scripts/mapeo_objetos.py validacion/resultados/<t> <inventario_visuales.csv> \
      [--modelo "tableros/<t>/<T>.SemanticModel"] [--confirmado tableros/<t>/mapa-objetos.yaml] \
      [--excluir-hojas "Queries,Reload,TEMP"]

Salida en <resultados>: mapa-objetos-propuesto.csv, destino-sin-origen.csv, mapa-objetos.json
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import conectores  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def leer_csv(ruta):
    with open(ruta, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def medida_a_metricas(catalogo, dax):
    """Medida del destino -> ids de métrica. Sigue referencias [Medida] dentro del DAX."""
    directo = collections.defaultdict(set)
    for m in catalogo["metricas"]:
        for med in m["medidas_destino"]:
            directo[med].add(m["id"])

    cache = {}

    def resolver(med, prof=0):
        if med in cache:
            return cache[med]
        res = set(directo.get(med, set()))
        if not res and prof < 4 and med in dax:
            for ref in set(re.findall(r"\[([^\]]+)\]", dax[med])):
                if ref != med and ref in dax:
                    res |= resolver(ref, prof + 1)
        cache[med] = res
        return res

    return resolver


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resultados")
    ap.add_argument("inventario")
    ap.add_argument("--modelo")
    ap.add_argument("--confirmado")
    ap.add_argument("--excluir-hojas", default="")
    a = ap.parse_args()

    mig = yaml.safe_load(open(os.path.join(RAIZ, "migracion.yaml"), encoding="utf-8"))
    cat = json.load(open(os.path.join(a.resultados, "catalogo.json"), encoding="utf-8"))
    estado_met = {m["id"]: m["estado"] for m in cat["metricas"]}
    nombre_met = {m["id"]: m["metrica"] for m in cat["metricas"]}
    dax = conectores.cargar_destino(mig["destino"]).medidas(a.modelo) if a.modelo else {}
    resolver = medida_a_metricas(cat, dax)
    excluir = {h.strip() for h in a.excluir_hojas.split(",") if h.strip()}
    conf = yaml.safe_load(open(a.confirmado, encoding="utf-8")) if a.confirmado and os.path.exists(a.confirmado) else {}
    conf_por_origen = {c["origen"]: c for c in (conf or {}).get("objetos", [])}

    # --- objetos del origen
    origen = collections.OrderedDict()
    for r in leer_csv(os.path.join(a.resultados, "objetos-origen.csv")):
        if r["hoja"] in excluir:
            continue
        o = origen.setdefault(r["objeto_id"], {"hoja": set(), "objeto": r["objeto"], "metricas": set(), "sin_clasificar": 0})
        o["hoja"].add(r["hoja"])
        if r["metrica_id"]:
            o["metricas"].add(r["metrica_id"])
        else:
            o["sin_clasificar"] += 1

    # --- visuales del destino
    destino = collections.OrderedDict()
    for r in leer_csv(a.inventario):
        if r.get("tipo_campo") != "Measure":
            continue
        v = destino.setdefault(r["visual_id"], {"pagina": r["pagina"], "tipo": r["tipo_visual"], "titulo": r.get("titulo", ""),
                                                "medidas": set(), "metricas": set()})
        v["medidas"].add(r["campo"])
        v["metricas"] |= resolver(r["campo"])

    # --- candidatos por objeto del origen
    filas, usados, vistos = [], collections.defaultdict(list), set()
    for oid, o in origen.items():
        mets = o["metricas"]
        en_alcance = {m for m in mets if estado_met.get(m) in ("migrada", "sin_medida")}
        cands = []
        for vid, v in destino.items():
            inter = en_alcance & v["metricas"]
            if inter:
                score = len(inter) / len(en_alcance | v["metricas"])
                cands.append((round(score, 2), vid, inter))
        cands.sort(key=lambda x: -x[0])
        vistos |= {c[1] for c in cands}
        top = cands[:3]
        cubiertas = set().union(*[c[2] for c in cands]) if cands else set()
        cobertura = len(cubiertas) / len(en_alcance) if en_alcance else None

        if not mets and o["sin_clasificar"]:
            estado, relacion = "revisar", "sin clasificar"
        elif not en_alcance:
            estado, relacion = "fuera de alcance", "técnico / hoja sin página"
        elif cobertura == 0:
            sin_med = all(estado_met.get(m) == "sin_medida" for m in en_alcance)
            estado, relacion = "no migrado", "sin medida en destino" if sin_med else "sin visual equivalente"
        else:
            estado = "migrado" if cobertura == 1 else "parcial"
            buenos = [c for c in cands if c[0] >= 0.5]
            relacion = "1:N (dividido)" if len({c[1] for c in buenos}) > 1 and all(c[0] < 1 for c in buenos) and \
                len(set().union(*[c[2] for c in buenos])) > max(len(c[2]) for c in buenos) else "1:1"
        confianza = "alta" if top and top[0][0] >= 0.8 else ("media" if top and top[0][0] >= 0.4 else "baja")
        if top:
            usados[top[0][1]].append(oid)

        c = conf_por_origen.get(oid)
        filas.append({
            "hoja": ", ".join(sorted(o["hoja"])), "objeto_id": oid, "objeto": o["objeto"],
            "metricas": " | ".join(nombre_met.get(m, m) for m in sorted(mets)),
            "estado": c.get("estado", estado) if c else estado,
            "relacion": c.get("relacion", relacion) if c else relacion,
            "cobertura": "" if cobertura is None else f"{cobertura:.0%}",
            "candidatos": " || ".join(f"{destino[v]['pagina']}/{destino[v]['tipo']}/{v} ({s})" for s, v, _ in top),
            "confianza": "confirmado" if c else ("—" if estado == "fuera de alcance" else confianza),
            "nota": c.get("nota", "") if c else "",
        })

    # N:1 -> varios objetos del origen cuyo mejor candidato es el mismo visual
    for vid, oids in usados.items():
        if len(oids) > 1:
            for f in filas:
                if f["objeto_id"] in oids and f["relacion"] == "1:1" and f["confianza"] != "confirmado":
                    f["relacion"] = f"N:1 (unificado con {len(oids) - 1} más)"

    sin_origen = [{"pagina": v["pagina"], "visual_id": vid, "tipo": v["tipo"], "medidas": " | ".join(sorted(v["medidas"]))}
                  for vid, v in destino.items() if vid not in vistos]

    campos = ["hoja", "objeto_id", "objeto", "metricas", "estado", "relacion", "cobertura", "candidatos", "confianza", "nota"]
    with open(os.path.join(a.resultados, "mapa-objetos-propuesto.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(filas)
    with open(os.path.join(a.resultados, "destino-sin-origen.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["pagina", "visual_id", "tipo", "medidas"], delimiter=";")
        w.writeheader()
        w.writerows(sin_origen)

    est = collections.Counter(f["estado"] for f in filas)
    en_alc = sum(v for k, v in est.items() if k not in ("fuera de alcance",))
    json.dump({"resumen": dict(est), "en_alcance": en_alc, "visuales_destino": len(destino), "visuales_sin_origen": len(sin_origen),
               "a_revisar": sum(1 for f in filas if f["confianza"] in ("baja", "media") and f["estado"] not in ("fuera de alcance",)),
               "objetos": filas}, open(os.path.join(a.resultados, "mapa-objetos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    migr = est.get("migrado", 0)
    print(f"Objetos del origen: {len(filas)} | en alcance: {en_alc} | " + " | ".join(f"{k}: {v}" for k, v in est.most_common()))
    if en_alc:
        print(f"Avance por objetos: {migr}/{en_alc} migrados ({migr / en_alc:.0%}) | parciales: {est.get('parcial', 0)}")
    print(f"Visuales del destino: {len(destino)} | sin objeto de origen (posible alcance nuevo): {len(sin_origen)}")
    rev = [f for f in filas if f["confianza"] in ("baja", "media") and f["estado"] not in ("fuera de alcance",)]
    print(f"Para revisar (confianza media/baja): {len(rev)} -> {os.path.join(a.resultados, 'mapa-objetos-propuesto.csv')}")


if __name__ == "__main__":
    main()
