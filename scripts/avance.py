"""
Avance del proyecto de migración: cruza Azure DevOps con los resultados del kit.

- Asigna cada work item a un tablero y gerencia (ID en tableros.yaml > jerarquía > alias > similitud).
- Clasifica el trabajo: migracion | alcance-nuevo | deuda-tecnica (tags > palabras > confirmado).
- Calcula avance por tablero (US, puntos, etapas, objetos migrados y métricas validadas),
  el peso del alcance nuevo y una proyección de fin por velocidad.

Uso:
  python scripts/avance.py                      # lee Azure DevOps (AZDO_PAT)
  python scripts/avance.py --desde-csv export.csv
  python scripts/avance.py --propuesta          # además: propuesta de reorganización en Features por gerencia

Salida en validacion/avance/: avance.json, avance-proyecto.html, pendientes.csv, propuesta-reorganizacion.csv
"""
import argparse
import collections
import csv
import difflib
import glob
import json
import os
import re
import statistics
import sys
import unicodedata
from datetime import date, datetime, timedelta

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conectores.gestion import azdo  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")
GESTION = os.path.join(RAIZ, "gestion")
PLANTILLA = os.path.join(os.path.dirname(__file__), "plantillas", "avance-proyecto.html")
US_TIPOS = {"User Story", "Product Backlog Item", "Historia de usuario", "Elemento de trabajo pendiente del producto"}
RUIDO = r"\b(tablero|dashboard|reporte|informe|migracion|migrar|qlik|qlikview|power ?bi|pbi|de|del|la|el)\b"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(RUIDO, " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def cargar_yaml(nombre, defecto):
    p = os.path.join(GESTION, nombre)
    return (yaml.safe_load(open(p, encoding="utf-8")) or defecto) if os.path.exists(p) else defecto


def num(v):
    try:
        return float(str(v).replace(",", ".")) if str(v).strip() else 0.0
    except ValueError:
        return 0.0


def fecha(v):
    if not v:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(v)[:19] if "T" in str(v) else str(v), fmt).date()
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------ asignación
class Asignador:
    def __init__(self, cat, conf, items):
        self.tab = {t["id"]: t for t in cat.get("tableros", [])}
        self.ger = {g["id"]: g for g in cat.get("gerencias", [])}
        self.conf = conf
        self.items = items
        self.alias = [(t["id"], norm(a)) for t in cat.get("tableros", []) for a in [t["id"].replace("-", " ")] + t.get("alias", []) if norm(a)]
        self.alias_ger = [(g["id"], norm(a)) for g in cat.get("gerencias", []) for a in [g.get("nombre", "")] + g.get("alias", []) if norm(a)]
        self.us_a_tab = {str(t["azdo_us"]): t["id"] for t in cat.get("tableros", []) if t.get("azdo_us")}
        self.feat_a_ger = {str(g["azdo_feature"]): g["id"] for g in cat.get("gerencias", []) if g.get("azdo_feature")}

    def ancestros(self, wi):
        vistos, p = [], str(wi.get("parent") or "")
        while p and p in self.items and p not in vistos:
            vistos.append(p)
            p = str(self.items[p].get("parent") or "")
        return vistos

    def candidatos(self, titulo):
        t = norm(titulo)
        punt = collections.defaultdict(float)
        for tid, a in self.alias:
            s = difflib.SequenceMatcher(None, a, t).ratio()
            # similitud contra cada ventana de palabras del título del mismo largo que el alias
            w, n = t.split(), len(a.split())
            for i in range(max(1, len(w) - n + 1)):
                s = max(s, difflib.SequenceMatcher(None, a, " ".join(w[i:i + n])).ratio())
            punt[tid] = max(punt[tid], s)
        return sorted(punt.items(), key=lambda x: -x[1])[:3]

    def tablero(self, wi):
        """Devuelve (tablero_id | None, capa, candidatos)."""
        c = self.conf.get(str(wi["id"]), {})
        if c.get("tablero"):
            return c["tablero"], "confirmado", []
        for i in [str(wi["id"])] + self.ancestros(wi):
            if i in self.us_a_tab:
                return self.us_a_tab[i], "id en tableros.yaml", []
        if wi["tipo_wi"] not in US_TIPOS and wi["tipo_wi"] not in ("Epic", "Feature"):
            for p in self.ancestros(wi):  # Tasks/Bugs heredan de su US
                if self.items[p]["tipo_wi"] in US_TIPOS:
                    t, capa, cand = self.tablero(self.items[p])
                    return t, f"heredado de {p}" if t else capa, cand
        t = norm(wi["titulo"])
        for tid, a in sorted(self.alias, key=lambda x: -len(x[1])):
            if re.search(rf"\b{re.escape(a)}\b", t):
                return tid, "alias", []
        cand = self.candidatos(wi["titulo"])
        if cand and cand[0][1] >= 0.85:
            return cand[0][0], f"similitud {cand[0][1]:.2f}", cand
        return None, "pendiente", cand

    def gerencia(self, wi, tablero):
        c = self.conf.get(str(wi["id"]), {})
        if c.get("gerencia"):
            return c["gerencia"]
        if tablero and self.tab.get(tablero, {}).get("gerencia"):
            return self.tab[tablero]["gerencia"]
        for p in [str(wi["id"])] + self.ancestros(wi):
            if p in self.feat_a_ger:
                return self.feat_a_ger[p]
            if self.items.get(p, {}).get("tipo_wi") == "Feature":
                ft = norm(self.items[p]["titulo"])
                for gid, a in self.alias_ger:
                    if re.search(rf"\b{re.escape(a)}\b", ft):
                        return gid
        return None


def tipo_trabajo(wi, cfg, conf, items):
    c = conf.get(str(wi["id"]), {})
    if c.get("tipo"):
        return c["tipo"], "confirmado"
    tags = {norm(t) for t in re.split(r"[;,]", wi.get("tags") or "") if t.strip()}
    for tipo, r in cfg["tipos_trabajo"].items():
        if tags & {norm(x) for x in r.get("tags", [])}:
            return tipo, "tag"
    tit = unicodedata.normalize("NFKD", wi["titulo"]).encode("ascii", "ignore").decode().lower()
    for tipo in ("alcance-nuevo", "deuda-tecnica", "migracion"):
        r = cfg["tipos_trabajo"].get(tipo, {})
        if any(unicodedata.normalize("NFKD", p).encode("ascii", "ignore").decode().lower() in tit for p in r.get("palabras", [])):
            return tipo, "palabras del título"
    p = str(wi.get("parent") or "")
    if p in items and items[p]["tipo_wi"] in US_TIPOS:
        return tipo_trabajo(items[p], cfg, conf, items)[0], "heredado"
    return None, "pendiente"


# ------------------------------------------------------------------ resultados del kit
def estado_kit(tablero):
    d = os.path.join(RAIZ, "validacion", "resultados", tablero)
    out = {}
    mp = os.path.join(d, "mapa-objetos.json")
    if os.path.exists(mp):
        m = json.load(open(mp, encoding="utf-8"))
        out["objetos_en_alcance"] = m.get("en_alcance", 0)
        out["objetos_migrados"] = m.get("resumen", {}).get("migrado", 0)
        out["visuales_sin_origen"] = m.get("visuales_sin_origen", 0)
    cp = os.path.join(d, "catalogo.json")
    if os.path.exists(cp):
        cat = json.load(open(cp, encoding="utf-8"))
        mig = [x for x in cat["metricas"] if x["estado"] == "migrada"]
        out["metricas_migradas"] = len(mig)
        res = sorted(glob.glob(os.path.join(d, "resumen_*.csv")))
        if res:
            med = {m.lower() for x in mig for m in x["medidas_destino"]}
            with open(res[-1], encoding="utf-8-sig") as f:
                filas = list(csv.DictReader(f, delimiter=";"))
            ok_med = {r["medida"].lower() for r in filas if r.get("estado") == "OK"}
            out["metricas_validadas"] = sum(1 for x in mig if {m.lower() for m in x["medidas_destino"]} & ok_med)
            out["casos_con_diferencia"] = sum(1 for r in filas if r.get("estado") != "OK" and r["medida"].lower() in med)
    return out


# ------------------------------------------------------------------ proyección
def proyeccion(us, cfg, bucket):
    semanas = cfg.get("semanas_velocidad", 8)
    hoy = date.today()
    ini = hoy - timedelta(weeks=semanas)
    por_semana = [0.0] * semanas
    for u in us:
        if u["tipo_trabajo"] != "migracion" or bucket(u) != "cerrado":
            continue
        f = fecha(u.get("cerrado"))
        if f and f >= ini:
            por_semana[min(semanas - 1, (f - ini).days // 7)] += u["peso"]
    restante = sum(u["peso"] for u in us if u["tipo_trabajo"] == "migracion" and bucket(u) != "cerrado")
    media = statistics.mean(por_semana) if por_semana else 0
    if media <= 0:
        return {"velocidad_semanal": 0, "restante": restante, "semanas_min": None, "semanas_max": None}
    q = statistics.quantiles(por_semana, n=4) if len([x for x in por_semana if x]) >= 2 else [media, media, media]
    alta, baja = max(q[2], media), max(q[0], media * 0.5)
    smin, smax = restante / alta, restante / baja
    return {"velocidad_semanal": round(media, 1), "restante": restante, "semanas_min": round(smin, 1), "semanas_max": round(smax, 1),
            "fin_min": (hoy + timedelta(weeks=smin)).isoformat(), "fin_max": (hoy + timedelta(weeks=smax)).isoformat(),
            "por_semana": por_semana}


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde-csv")
    ap.add_argument("--propuesta", action="store_true")
    ap.add_argument("--salida", default=os.path.join(RAIZ, "validacion", "avance"))
    a = ap.parse_args()

    cfg = cargar_yaml("config.yaml", {})
    cat = cargar_yaml("tableros.yaml", {})
    conf = {str(k): v for k, v in (cargar_yaml("asignaciones.yaml", {}).get("asignaciones") or {}).items()}
    filas = azdo.leer_csv(a.desde_csv) if a.desde_csv else azdo.leer_api(cfg["azdo"])
    items = {str(w["id"]): w for w in filas}
    asig = Asignador(cat, conf, items)
    cerr = {norm(s) for s in cfg["estados"]["cerrado"]}
    curso = {norm(s) for s in cfg["estados"]["en_curso"]}

    def bucket(w):
        s = norm(w.get("estado"))
        return "cerrado" if s in cerr else ("en_curso" if s in curso else "pendiente")

    sin_est = all(num(w.get("puntos")) + num(w.get("esfuerzo")) == 0 for w in items.values() if w["tipo_wi"] in US_TIPOS)
    for w in items.values():
        w["tablero"], w["capa"], w["candidatos"] = asig.tablero(w)
        w["gerencia"] = asig.gerencia(w, w["tablero"])
        w["tipo_trabajo"], w["capa_tipo"] = tipo_trabajo(w, cfg, conf, items)
        if w["tipo_trabajo"] is None and w["tablero"] and w["tipo_wi"] in US_TIPOS:
            w["tipo_trabajo"], w["capa_tipo"] = "migracion", "inferido (US de tablero)"
        w["peso"] = 1.0 if sin_est else num(w.get("puntos")) or num(w.get("esfuerzo"))

    us = [w for w in items.values() if w["tipo_wi"] in US_TIPOS]
    tasks = [w for w in items.values() if w["tipo_wi"] == "Task"]

    # --- por tablero
    tableros = []
    for t in cat.get("tableros", []):
        u = [w for w in us if w["tablero"] == t["id"]]
        ids = {str(w["id"]) for w in u}
        etapas = {}
        for e in cfg.get("etapas", []):
            ts = [x for x in tasks if str(x.get("parent")) in ids and norm(e) in norm(x["titulo"])]
            etapas[e] = "sin tasks" if not ts else ("cerrada" if all(bucket(x) == "cerrado" for x in ts) else
                                                     "en curso" if any(bucket(x) != "pendiente" for x in ts) else "pendiente")
        por_tipo = collections.defaultdict(lambda: {"total": 0.0, "cerrado": 0.0, "us": 0})
        for w in u:
            p = por_tipo[w["tipo_trabajo"] or "sin clasificar"]
            p["total"] += w["peso"]
            p["us"] += 1
            p["cerrado"] += w["peso"] if bucket(w) == "cerrado" else 0
        tableros.append({"id": t["id"], "gerencia": t.get("gerencia"), "nombre": (t.get("alias") or [t["id"]])[0],
                         "us": [{"id": w["id"], "titulo": w["titulo"], "estado": w["estado"], "bucket": bucket(w),
                                 "tipo": w["tipo_trabajo"], "peso": w["peso"]} for w in u],
                         "por_tipo": por_tipo, "etapas": etapas, "kit": estado_kit(t["id"])})

    # --- totales y alcance nuevo
    tot = collections.defaultdict(lambda: {"total": 0.0, "cerrado": 0.0, "us": 0})
    for w in us:
        p = tot[w["tipo_trabajo"] or "sin clasificar"]
        p["total"] += w["peso"]
        p["cerrado"] += w["peso"] if bucket(w) == "cerrado" else 0
        p["us"] += 1
    pendientes = [w for w in us if not w["tablero"] or not w["tipo_trabajo"]]
    auto = sum(1 for w in us if w["capa"] not in ("pendiente",) and w["tipo_trabajo"])
    proy = proyeccion(us, cfg, bucket)
    gers = {g["id"]: g.get("nombre", g["id"]) for g in cat.get("gerencias", [])}

    os.makedirs(a.salida, exist_ok=True)
    data = {"generado": date.today().isoformat(), "unidad": "US (sin estimación)" if sin_est else "puntos",
            "totales": tot, "proyeccion": proy, "tableros": tableros, "gerencias": gers,
            "calidad": {"us": len(us), "asignadas_auto": auto, "pendientes": len(pendientes)},
            "sin_tablero": [{"id": w["id"], "titulo": w["titulo"], "tipo": w["tipo_trabajo"], "estado": w["estado"]}
                            for w in us if not w["tablero"]]}
    json.dump(data, open(os.path.join(a.salida, "avance.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=dict)
    with open(os.path.join(a.salida, "pendientes.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "tipo_wi", "titulo", "estado", "falta", "candidatos_tablero", "tipo_sugerido"])
        for x in pendientes:
            falta = " y ".join(k for k, v in (("tablero", x["tablero"]), ("tipo", x["tipo_trabajo"])) if not v)
            w.writerow([x["id"], x["tipo_wi"], x["titulo"], x["estado"], falta,
                        " | ".join(f"{c} ({s:.2f})" for c, s in x["candidatos"]), x["tipo_trabajo"] or ""])
    if a.propuesta:
        with open(os.path.join(a.salida, "propuesta-reorganizacion.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "tipo_wi", "titulo", "estado", "parent_actual", "tablero_sugerido", "gerencia_sugerida",
                        "feature_sugerida", "tag_sugerido", "como_se_decidio"])
            for x in sorted(us, key=lambda z: (z["gerencia"] or "~", z["tablero"] or "~")):
                p = items.get(str(x.get("parent") or ""), {})
                g = next((g for g in cat.get("gerencias", []) if g["id"] == x["gerencia"]), None)
                w.writerow([x["id"], x["tipo_wi"], x["titulo"], x["estado"], p.get("titulo", ""), x["tablero"] or "REVISAR",
                            x["gerencia"] or "REVISAR", (f"{g.get('nombre')} (#{g.get('azdo_feature')})" if g and g.get("azdo_feature")
                                                         else (g.get("nombre") if g else "REVISAR")),
                            x["tipo_trabajo"] or "REVISAR", f"tablero: {x['capa']} · tipo: {x['capa_tipo']}"])

    html = open(PLANTILLA, encoding="utf-8").read().replace("__DATA__", json.dumps(data, ensure_ascii=False, default=dict).replace("</", "<\\/"))
    open(os.path.join(a.salida, "avance-proyecto.html"), "w", encoding="utf-8").write(html)

    # --- resumen corto
    m = tot.get("migracion", {"total": 0, "cerrado": 0})
    otros = sum(v["total"] for k, v in tot.items() if k != "migracion")
    total = m["total"] + otros
    print(f"US: {len(us)} | asignadas automáticamente: {auto} | pendientes de confirmar: {len(pendientes)} | unidad: {data['unidad']}")
    if m["total"]:
        print(f"Migración: {m['cerrado']:.0f}/{m['total']:.0f} cerrado ({m['cerrado'] / m['total']:.0%})"
              + (f" | alcance nuevo + deuda: {otros / total:.0%} del total" if total else ""))
    if proy.get("semanas_min") is not None:
        print(f"Proyección: {proy['restante']:.0f} restantes a {proy['velocidad_semanal']}/semana -> fin entre {proy['fin_min']} y {proy['fin_max']}")
    else:
        print("Proyección: sin cierres de migración en las últimas semanas (no se puede proyectar).")
    print(f"-> {os.path.join(a.salida, 'avance-proyecto.html')}")


if __name__ == "__main__":
    main()
