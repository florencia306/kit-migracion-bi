---
name: Auditor de tableros
description: Audita un tablero ya migrado (inventario, buenas prácticas, consistencia y validación) y genera un informe con semáforo.
---
Auditá sin modificar nada. Pedí confirmación entre etapas.

1. Inventario: `python scripts/herramientas/powerbi_inventario.py "<Report>" "<SemanticModel>" validacion/resultados/<tablero>/inventario`. Usá solo el resumen de consola.
2. Buenas prácticas (buscá con grep, no leas archivos completos): `LocalDateTable_`, tablas `(2)`, medidas TEST/sin uso (de `chequeo_medidas.csv`), servidor escrito en Power Query, relaciones bidireccionales, divisiones con `/`, `IFERROR`, columnas calculadas. Listá hallazgo · severidad · corrección.
3. Consistencia y Qlik: agregá a `tests/casos.yaml` casos de identidades (ej. stock final = inicial + emitidas − bajas; stock inicial N = final N−1; total tabla = tarjeta) y los KPIs de cada página; ejecutá con el agente o script de validación.
4. Informe `validacion/resultados/<tablero>/auditoria-<fecha>.md`: semáforo 🟢🟡🔴 por página, hallazgos por severidad, pendientes. Máximo 1 página.
