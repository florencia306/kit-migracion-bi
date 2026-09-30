---
name: Avance del proyecto
description: Lee Azure DevOps (solo lectura), asigna US a tableros y gerencias, separa migración de alcance nuevo y calcula cuánto falta con proyección.
---
Trabajás con `scripts/avance.py`; nunca cuentes ni sumes work items en el chat. Solo lectura de Azure DevOps: no crees, muevas ni edites work items.

1. **Correr**: `python scripts/avance.py --propuesta` (usa `AZDO_PAT` y `gestion/config.yaml`). Sin token: la persona exporta la consulta a CSV y corrés `python scripts/avance.py --desde-csv <archivo.csv> --propuesta`.
2. **Pendientes**: si el resumen dice "pendientes de confirmar" > 0, leé como máximo 30 filas de `validacion/avance/pendientes.csv`. Para cada una proponé en una línea tablero (usá `candidatos_tablero` y `gestion/tableros.yaml`) y tipo: `migracion` (trabajo necesario para igualar el tablero de Qlik), `alcance-nuevo` (algo que Qlik no tenía) o `deuda-tecnica`. Si dudás, preguntá; no adivines.
3. **Confirmar**: con el OK, escribí en `gestion/asignaciones.yaml`:
   ```yaml
   asignaciones:
     1234: { tablero: cartera, tipo: alcance-nuevo }
   ```
   Si un tablero aparece con un nombre nuevo, agregalo a `alias` en `gestion/tableros.yaml` (así la próxima vez sale solo). Si falta un tablero o gerencia, proponé la entrada completa.
4. Repetí el paso 1 y respondé en 3 líneas: % de migración cerrado, % de trabajo fuera del alcance, rango de fin estimado. Terminá con la ruta `validacion/avance/avance-proyecto.html`.
5. **Reorganización** (solo si la piden): resumí `validacion/avance/propuesta-reorganizacion.csv` por gerencia (Feature) → tableros (US) y los tags sugeridos. Es una propuesta para el scrum; los cambios en Azure DevOps los hace el equipo.

Cruce con el kit: el avance por tablero suma objetos migrados (`mapa-objetos.json`) y métricas validadas (`resumen_*.csv`) si existen en `validacion/resultados/<t>/`. Si faltan, sugerí correr los agentes Mapeo de objetos y Reporte de migración.
