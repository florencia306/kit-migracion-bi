# Kit de migración y validación de BI
Respondé en español y breve. Mostrá solo resúmenes, no repitas archivos completos.

- Migración actual: ver `migracion.yaml` (origen y destino). Conectores en `conectores/origen/` y `conectores/destino/`; reglas del origen en `docs/reglas/<origen>.yaml`.
- Estructura: `tableros/<tablero>/` (modelo del destino, export del origen, `tests/casos.yaml`); resultados en `validacion/resultados/<tablero>/`.
- Scripts: `catalogo.py` (métricas origen → destino), `validar.py` (compara valores), `reporte.py` (HTML con desvío), `mapeo_objetos.py` (objetos origen ↔ visuales destino), `avance.py` (Azure DevOps + avance del proyecto).
- Gestión: `gestion/tableros.yaml` (gerencias, tableros, alias, IDs de AzDO), `gestion/config.yaml`, `gestion/asignaciones.yaml` (decisiones confirmadas). Azure DevOps es solo lectura.
- Herramientas propias de cada tecnología en `scripts/herramientas/`.
- Nunca calcules ni compares datos en el chat: corré los scripts y leé su resumen de consola.
- Origen Qlik: `tableros/<t>/qlik/` (qvw, qvd, source) solo local; `qlik_vivo.py` y `qlik_script.py` extraen a `origen/`. Nunca abras QVD ni scripts completos en el chat: usá los CSV generados.
- Nunca pegues datos reales; los archivos de datos del origen (QVD, extracts) quedan solo en local.

## Contexto de la migración QlikView → Power BI
- Destino: Azure Synapse + modelo estrella (hechos y `dim_*`), tabla de fechas `'Calendar'`; fechas secundarias con `USERELATIONSHIP`.
- Campos Qlik → modelo: `docs/mapeo.md`. Traducciones validadas: `docs/ejemplos-qlik-dax.md`.
