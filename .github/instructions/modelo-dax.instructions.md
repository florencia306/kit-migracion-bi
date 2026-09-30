---
applyTo: "**/*.SemanticModel/**,**/*.dax,docs/ejemplos-qlik-dax.md"
---
# Convenciones del modelo
- Prefijos: `#` conteos, `%` ratios, `$` importes. Sufijos: LY, SPLY, YTD, PM, Mes. Auxiliares con `_` y ocultas.
- Pólizas: `DISTINCTCOUNT( Polizas[IDPolizas] )`. Reutilizar medidas base (`[# Polizas Emitidas]`, `[# Polizas Bajas]`).
- `VAR … RETURN`; `DIVIDE`; filtros de columna en `CALCULATE`; `FILTER( ALL('Calendar'), … )` solo para acumulados.
- Sin columnas calculadas si se puede resolver en SQL. Formato dinámico K/M/B existente para conteos.
- Comentarios en español solo si la lógica no es obvia.
