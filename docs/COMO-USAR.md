# Cómo usar el kit

## Configurar la migración
Editá `migracion.yaml` (origen y destino). Hoy: `qlik` → `powerbi`. Ver `docs/CONECTORES.md` para otras herramientas.

## Por tablero
Estructura: `tableros/<t>/` con el modelo del destino (PBIP), `qlik/` (qvw, qvd, source; no se sube), `origen/` (lo que extrae el kit) y `tests/casos.yaml`.

- **Reporte con desvío por métrica** → agente **Reporte de migración** (o a mano):
  0. `python scripts/herramientas/qlik_vivo.py extraer tableros/<t>/qlik/Frontend tableros/<t>/origen` (uno o varios .qvw)
  1. `python scripts/catalogo.py tableros/<t>/origen/expresiones.csv "tableros/<t>/<T>.SemanticModel" validacion/resultados/<t>`
  2. `python scripts/validar.py tableros/<t>/tests/casos.yaml`
  3. `python scripts/reporte.py validacion/resultados/<t> --titulo "Métricas <T>"` → abrir `reporte-migracion.html`
- **Trazabilidad de objetos (migración no 1:1)** → agente **Mapeo de objetos**:
  `python scripts/mapeo_objetos.py validacion/resultados/<t> <inventario_visuales.csv> --modelo "..." --confirmado tableros/<t>/mapa-objetos.yaml`
- **Traducir expresiones** → agente **Qlik a DAX** (específico de Qlik → Power BI).
- **Revisión técnica del modelo** → agente **Auditor de tableros** (usa `scripts/herramientas/powerbi_inventario.py`).

## Avance del proyecto (Azure DevOps)
Agente **Avance del proyecto**. Organización sugerida del backlog: una **Feature por gerencia** y una **US por tablero**; Tasks con las etapas (Modelo, Medidas, Visuales, Validación, UAT); tag `alcance-nuevo` o `deuda-tecnica` para lo que no es migración.

1. Completá `gestion/config.yaml` (organización, proyecto, área) y `gestion/tableros.yaml` (gerencias, tableros, alias y, si existen, `azdo_feature`/`azdo_us`).
2. Token de solo lectura (Work Items: Read) en la variable `AZDO_PAT`, o exportá la consulta a CSV.
3. `python scripts/avance.py --propuesta` (o `--desde-csv export.csv`) → `validacion/avance/avance-proyecto.html`, `pendientes.csv`, `propuesta-reorganizacion.csv`.
4. El agente resuelve los pendientes con vos y guarda las decisiones en `gestion/asignaciones.yaml`.

Asignación de cada US a un tablero, en orden: confirmado > ID en `tableros.yaml` > heredado de la US (Tasks) > alias en el título > similitud ≥ 0,85 > pendiente. La proyección usa solo trabajo de migración y la velocidad de las últimas semanas (rango, no fecha exacta).

## Herramientas por tecnología (`scripts/herramientas/`)
- `qlik_vivo.py`: QlikView Desktop en vivo. `extraer` saca hojas, objetos, expresiones, variables y script del .qvw; `datos` lee un objeto con período/selecciones. El validador lo usa con `referencia: tipo: qlik`.
- `qlik_script.py`: script de carga (`source/` o `script.qvs`) + cabeceras de QVD → `modelo-origen.csv`, `tablas-origen.csv`, `qvd-campos.csv` (sin leer datos).
- `qlik_extraer_prj.py`: proyecto -prj de QlikView → `expresiones.csv`.
- `powerbi_inventario.py`: visuales y medidas usadas de un reporte PBIR.

## Tips para gastar menos tokens
- Corré los scripts vos y pasale al agente solo el resumen.
- Un chat nuevo por tarea; referenciá archivos puntuales con `#archivo`.
- Traducí de a 5–10 expresiones; modelo liviano para lo simple.

## Requisitos
`pip install pandas pyyaml pythonnet pyqvd pyodbc pywin32` · Power BI Desktop abierto con el .pbip (destino powerbi).
