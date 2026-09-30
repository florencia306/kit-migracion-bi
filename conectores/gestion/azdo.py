"""Gestión: Azure DevOps Boards (solo lectura). Trae Epics, Features, US/PBI, Tasks y Bugs de un área.

Credenciales: variable de entorno AZDO_PAT (token con permiso 'Work Items: Read').
Sin token: exportá una consulta desde Azure DevOps a CSV y usá leer_csv().
"""
import base64
import csv
import json
import os
import urllib.request

NOMBRE = "Azure DevOps"
CAMPOS = {
    "System.Id": "id", "System.WorkItemType": "tipo_wi", "System.Title": "titulo", "System.State": "estado",
    "System.Tags": "tags", "System.Parent": "parent", "System.AreaPath": "area", "System.IterationPath": "iteracion",
    "Microsoft.VSTS.Scheduling.StoryPoints": "puntos", "Microsoft.VSTS.Scheduling.Effort": "esfuerzo",
    "Microsoft.VSTS.Common.ClosedDate": "cerrado", "System.CreatedDate": "creado",
}
# nombres de columna del export CSV de Azure DevOps (inglés y español)
COLUMNAS_CSV = {
    "ID": "id", "Id.": "id", "Work Item Type": "tipo_wi", "Tipo de elemento de trabajo": "tipo_wi", "Title": "titulo", "Título": "titulo",
    "State": "estado", "Estado": "estado", "Tags": "tags", "Etiquetas": "tags", "Parent": "parent", "Primario": "parent",
    "Area Path": "area", "Ruta de acceso del área": "area", "Iteration Path": "iteracion", "Ruta de iteración": "iteracion",
    "Story Points": "puntos", "Puntos de historia": "puntos", "Effort": "esfuerzo", "Esfuerzo": "esfuerzo",
    "Closed Date": "cerrado", "Fecha de cierre": "cerrado", "Created Date": "creado", "Fecha de creación": "creado",
}


def _req(url, cuerpo=None):
    pat = os.environ.get("AZDO_PAT")
    if not pat:
        raise SystemExit("Definí la variable de entorno AZDO_PAT (token de solo lectura) o usá --desde-csv.")
    auth = base64.b64encode(f":{pat}".encode()).decode()
    data = json.dumps(cuerpo).encode() if cuerpo is not None else None
    r = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                               headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read())


def leer_api(cfg):
    """cfg: organizacion, proyecto, area (ruta de área, se incluyen sub-áreas)."""
    base = f"https://dev.azure.com/{cfg['organizacion']}/{cfg['proyecto']}/_apis/wit"
    tipos = ", ".join(f"'{t}'" for t in cfg.get("tipos", ["Epic", "Feature", "User Story", "Product Backlog Item", "Task", "Bug"]))
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "
                     f"AND [System.WorkItemType] IN ({tipos}) AND [System.AreaPath] UNDER '{cfg['area']}'"}
    ids = [w["id"] for w in _req(f"{base}/wiql?api-version=7.1", wiql)["workItems"]]
    out = []
    for i in range(0, len(ids), 200):
        lote = _req(f"{base}/workitemsbatch?api-version=7.1", {"ids": ids[i:i + 200], "fields": list(CAMPOS)})
        for wi in lote["value"]:
            f = wi["fields"]
            out.append({v: f.get(k, "") for k, v in CAMPOS.items()} | {"id": wi["id"]})
    return out


def leer_csv(ruta):
    with open(ruta, encoding="utf-8-sig") as fh:
        sep = ";" if fh.readline().count(";") > 0 else ","
        fh.seek(0)
        filas = list(csv.DictReader(fh, delimiter=sep))
    out = []
    for r in filas:
        d = {COLUMNAS_CSV.get(k.strip(), k.strip()): (v or "").strip() for k, v in r.items() if k}
        if d.get("id"):
            out.append(d)
    return out
