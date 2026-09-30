---
name: Reporte de migración
description: Arma el catálogo de métricas origen → destino, valida valores y genera el reporte visual con desvío % por métrica.
---
Generás el reporte de un tablero con los scripts; no calcules números en el chat. Origen y destino: `migracion.yaml`.

0. **Origen** (si falta `tableros/<t>/origen/expresiones.csv`): `python scripts/herramientas/qlik_vivo.py extraer "tableros/<t>/qlik/<T>.qvw" tableros/<t>/origen` ; luego `python scripts/herramientas/qlik_vivo.py scripts tableros/<t>/qlik tableros/<t>/origen/scripts` y `python scripts/herramientas/qlik_script.py tableros/<t>/origen/scripts tableros/<t>/qlik/Resources tableros/<t>/origen --qvd tableros/<t>/qlik`. El .qvw del tablero está en `qlik/Frontend/`. Si el tablero tiene `depende_de` en `gestion/tableros.yaml`, sumá `--base <id>=tableros/<id>/origen/scripts` por cada uno (extraé antes los scripts de ese tablero base si faltan). Sin QlikView Desktop, usá el export `.tab`.
1. **Catálogo**: `python scripts/catalogo.py tableros/<t>/origen/expresiones.csv "tableros/<t>/<modelo destino>" validacion/resultados/<t>`
2. **Sin clasificar** (si el resumen dice > 0): leé como máximo 30 filas de `validacion/resultados/<t>/sin-clasificar.csv` y proponé reglas nuevas para `docs/reglas/<origen>.yaml` (id, area, metrica, patrones, medidas_destino). Pedí confirmación, agregalas y repetí el paso 1. Si el resumen lista medidas que no existen en el modelo, proponé corregir `medidas_destino`.
3. **Casos**: para cada métrica `migrada` sin casos en `tableros/<t>/tests/casos.yaml`, agregá casos con su medida principal (total del período, por año y YTD si el origen usa ese corte; ver `cortes_origen` en `catalogo-metricas.csv`). Referencia: `tipo: qlik` con el objeto de Qlik (elegilo en `origen/objetos.csv` por hoja, título y dimensiones; preferí gráficos y tablas simples) y el período en el bloque `qlik:` (`variables`) alineado con los `filtros` de `'Calendar'`. Sin QlikView Desktop: `tipo: csv` con un export.
4. **Validación**: `python scripts/validar.py tableros/<t>/tests/casos.yaml`
5. **Reporte**: `python scripts/reporte.py validacion/resultados/<t> --titulo "Métricas <Tablero>"`. Respondé en 3 líneas (validadas, con diferencias, revisión alta) y terminá con la ruta del HTML generado (`validacion/resultados/<t>/reporte-migracion.html`) para abrirlo en el navegador.
6. **Diferencias**: proponé hasta 3 causas por métrica (ver `observacion`). Si la persona confirma una, actualizá `observacion`/`revision` en `docs/reglas/<origen>.yaml`.

No modifiques el modelo del destino.
