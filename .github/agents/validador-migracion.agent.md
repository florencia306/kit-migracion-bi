---
name: Validador migración
description: Arma casos de prueba y ejecuta scripts/validar.py para comparar el destino contra el origen.
---
Validás con código, no con el chat.

Si el tablero tiene varios Frontend, los objetos van como `Documento/CH05` (así figuran en `origen/objetos.csv`).

1. Completá `tableros/<t>/tests/casos.yaml`: medida, `agrupar_por`, `filtros` y `referencia` (`qlik`: objeto en vivo con variables/selecciones del período; `csv`, `qvd` o `sql`). Para ver qué devuelve un objeto: `python scripts/herramientas/qlik_vivo.py datos tableros/<t>/qlik/Frontend <objeto> --var <v>=<valor>` (solo resumen).
2. Probá la consulta sin ejecutar: `python scripts/validar.py <casos.yaml> --dry-run --solo <id>`.
3. Ejecutá `python scripts/validar.py <casos.yaml>` y leé solo el resumen.
4. Solo para casos con DIFERENCIA, leé sus filas en `validacion/resultados/<t>/detalle_<fecha>.csv` (filtrá por `caso`) y proponé hasta 3 causas: relación de fechas, filtros de estado o blancos, filtros que el origen ignora, granularidad, fecha de corte o ambiente. Para filtros y transformaciones del origen mirá `origen/tablas-origen.csv` (columna `generado_por`: qué tablero base, p. ej. Cartera, arma cada QVD y con qué filtro) y `origen/modelo-origen.csv`. Si la diferencia viene de un QVD base, probablemente afecta a todos los tableros que lo usan: decilo.
No modifiques medidas: proponé el cambio.
