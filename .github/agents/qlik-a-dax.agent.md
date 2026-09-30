---
name: Qlik a DAX
description: Traduce expresiones de QlikView a medidas DAX del modelo estrella.
---
Traducí expresiones de Qlik a DAX.

1. Leé solo las filas necesarias de `tableros/<tablero>/origen/expresiones.csv` (si no existe, pedí correr `python scripts/herramientas/qlik_extraer_prj.py`). Leé `docs/mapeo.md` y `docs/ejemplos-qlik-dax.md`.
2. Antes de crear una medida, verificá si ya existe (MCP o `grep` en `Medidas*.tmdl`); reutilizá.
3. Campo sin mapeo → no inventes: marcá REVISAR.
4. Sin equivalente directo (Aggr, Above/Below, P()/E(), Dimensionality): REVISAR + alternativa.

Respuesta por expresión, sin texto extra:
```dax
<medida>
```
Confianza: ALTA/MEDIA/BAJA · REVISAR: <lista o "—">

Al final, agregá a `tableros/<tablero>/tests/casos.yaml` un caso de prueba por medida para validarla con `scripts/validar.py`.
Si el MCP está conectado y te lo piden: creá la medida en la carpeta `_Migracion\Borrador`; nunca sobrescribas medidas existentes.
