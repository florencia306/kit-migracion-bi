"""Destino Power BI: medidas desde el modelo PBIP/TMDL y consultas DAX contra Power BI Desktop."""
import glob
import os
import re
import sys

import pandas as pd

NOMBRE = "Power BI"
LENGUAJE = "DAX"


# ---------------------------------------------------------------- modelo
def medidas(ruta_modelo):
    """{nombre: DAX} leyendo definition/tables/*.tmdl."""
    out = {}
    for p in glob.glob(os.path.join(ruta_modelo, "definition", "tables", "*.tmdl")):
        lines = open(p, encoding="utf-8-sig").read().split("\n")
        i = 0
        while i < len(lines):
            m = re.match(r"^\tmeasure\s+('([^']+)'|([^\s=]+))\s*=?\s*(.*)$", lines[i])
            if not m:
                i += 1
                continue
            name, body = m.group(2) or m.group(3), [m.group(4)] if m.group(4).strip() else []
            i += 1
            while i < len(lines) and (lines[i].startswith("\t\t\t") or not lines[i].strip()):
                body.append(lines[i][3:] if lines[i].startswith("\t\t\t") else "")
                i += 1
            out[name] = "\n".join(body).replace("```", "").strip()[:1500]
    return out


# ---------------------------------------------------------------- consultas
def armar_consulta(caso):
    if caso.get("consulta") or caso.get("dax"):
        return caso.get("consulta") or caso["dax"]
    grupos = caso.get("agrupar_por", [])
    partes = list(grupos)
    for col, valores in (caso.get("filtros") or {}).items():
        vals = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in valores)
        partes.append(f"TREATAS({{ {vals} }}, {col})")
    partes.append(f'"valor", [{caso["medida"]}]')
    cuerpo = ",\n    ".join(partes)
    orden = f"\nORDER BY {', '.join(grupos)}" if grupos else ""
    return f"EVALUATE\nSUMMARIZECOLUMNS(\n    {cuerpo}\n){orden}"


def normalizar_resultado(df):
    return df.rename(columns={c: (c.split("[")[-1].rstrip("]") if "[" in c else c) for c in df.columns})


def _puerto():
    bases = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces"),
             os.path.expandvars(r"%USERPROFILE%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces")]
    files = [f for b in bases for f in glob.glob(os.path.join(b, "*", "Data", "msmdsrv.port.txt"))]
    if not files:
        sys.exit("No encontré Power BI Desktop abierto. Abrí el .pbip y volvé a correr.")
    files.sort(key=os.path.getmtime, reverse=True)
    if len(files) > 1:
        print(f"Aviso: {len(files)} instancias de Desktop abiertas; uso la más reciente (--puerto para elegir).")
    raw = open(files[0], "rb").read()
    for enc in ("utf-16", "utf-8"):
        try:
            return int(raw.decode(enc).strip("\x00 \r\n\ufeff"))
        except (UnicodeDecodeError, ValueError):
            pass
    sys.exit(f"No pude leer el puerto de {files[0]}")


def _dll():
    for p in [r"C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.AnalysisServices.AdomdClient.dll",
              r"C:\Program Files\Microsoft.NET\ADOMD.NET\*\Microsoft.AnalysisServices.AdomdClient.dll",
              r"C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop*\bin\Microsoft.AnalysisServices.AdomdClient.dll"]:
        hits = glob.glob(p)
        if hits:
            return sorted(hits)[-1]
    sys.exit("No encontré Microsoft.AnalysisServices.AdomdClient.dll. Indicá la ruta con --adomd.")


class Cliente:
    def __init__(self, opciones):
        import clr  # pythonnet
        clr.AddReference(opciones.get("adomd") or _dll())
        from Microsoft.AnalysisServices.AdomdClient import AdomdConnection
        self.conn = AdomdConnection(f"Data Source=localhost:{opciones.get('puerto') or _puerto()}")
        self.conn.Open()

    def ejecutar(self, consulta):
        from Microsoft.AnalysisServices.AdomdClient import AdomdCommand
        r = AdomdCommand(consulta, self.conn).ExecuteReader()
        cols = [r.GetName(i) for i in range(r.FieldCount)]
        rows = []
        while r.Read():
            rows.append([None if r.IsDBNull(i) else r.GetValue(i) for i in range(r.FieldCount)])
        r.Close()
        return pd.DataFrame(rows, columns=cols)
