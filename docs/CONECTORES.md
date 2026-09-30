# Conectores: cómo sumar otra herramienta de BI

El kit separa lo general (catálogo, validación, reporte) de lo propio de cada herramienta.

| Pieza | Dónde | Qué cambia por herramienta |
|---|---|---|
| Conector de origen | `conectores/origen/<nombre>.py` | Cómo leer las métricas/expresiones (`leer`, `normalizar`, `NOMBRE`) |
| Reglas del origen | `docs/reglas/<nombre>.yaml` | Patrones para agrupar en métricas, cortes temporales, observaciones |
| Conector de destino | `conectores/destino/<nombre>.py` | Leer medidas del modelo, armar y ejecutar consultas (`medidas`, `armar_consulta`, `Cliente`, `normalizar_resultado`, `NOMBRE`, `LENGUAJE`) |
| Conector de gestión | `conectores/gestion/<nombre>.py` | Leer work items (`leer_api`, `leer_csv`); hoy Azure DevOps. Otro (Jira) debe devolver los mismos campos: id, tipo_wi, titulo, estado, tags, parent, puntos, esfuerzo, cerrado |
| Configuración | `migracion.yaml` | `origen:` y `destino:` de la migración actual |

La interfaz exacta está documentada en `conectores/__init__.py`.

## Disponibles
- Origen **qlik**: export de expresiones de QlikView (.tab) o `expresiones.csv` del proyecto -prj.
- Origen **tableau** (beta): campos calculados de .twb/.twbx. Reglas en `docs/reglas/tableau.yaml` como plantilla.
- Destino **powerbi**: modelo PBIP/TMDL + consultas DAX contra Power BI Desktop.

## Para sumar una herramienta nueva
1. Copiá el conector más parecido y adaptá sus funciones.
2. Creá `docs/reglas/<nombre>.yaml` (copiá `tableau.yaml` como base).
3. Probá con `python scripts/catalogo.py <export> <modelo> <salida> --origen <nombre>` y revisá `sin-clasificar.csv`.
4. La validación contra SQL del data warehouse (`referencia: tipo: sql`) funciona igual para cualquier herramienta.

Antes de reutilizar el kit en otro proyecto o fuera de la empresa, quitá lo propio del negocio: nombres de medidas, reglas y servidores.
