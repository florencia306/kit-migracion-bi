---
name: Mapeo de objetos
description: Empareja los objetos del tablero origen (Qlik) con los visuales del destino (Power BI), razona los casos que no son 1:1 y deja la trazabilidad confirmada.
---
La migración no es 1:1 (puede haber varios Frontend de Qlik unificados en un solo Power BI; sus objetos vienen como `Documento/CH05`): un objeto del origen puede dividirse (1:N), unificarse con otros (N:1), quedar fuera de alcance o no migrarse. El script propone; vos razonás solo los casos dudosos; la persona confirma. No calcules ni compares en el chat.

1. **Inventario del destino**: `python scripts/herramientas/powerbi_inventario.py "tableros/<t>/<T>.Report" "tableros/<t>/<T>.SemanticModel" validacion/resultados/<t>/inventario`
2. **Catálogo** (si no existe `validacion/resultados/<t>/catalogo.json`): `python scripts/catalogo.py tableros/<t>/origen/<export> "tableros/<t>/<T>.SemanticModel" validacion/resultados/<t>`
3. **Mapa**: `python scripts/mapeo_objetos.py validacion/resultados/<t> validacion/resultados/<t>/inventario/inventario_visuales.csv --modelo "tableros/<t>/<T>.SemanticModel" --confirmado tableros/<t>/mapa-objetos.yaml`
   (sumá `--excluir-hojas "Hoja1,Hoja2"` para hojas técnicas del origen que nunca se migran).
4. **Revisión**: leé como máximo 30 filas de `mapa-objetos-propuesto.csv` con `confianza` media o baja, más `destino-sin-origen.csv`. Por cada una proponé en una línea: visual equivalente, relación (1:1, 1:N, N:1), estado (migrado, parcial, no migrado, fuera de alcance) y por qué. Los visuales sin origen son posible **alcance nuevo**: marcalos así.
5. **Confirmar**: con el OK de la persona, agregá a `tableros/<t>/mapa-objetos.yaml`:
   ```yaml
   objetos:
     - origen: CH123            # objeto_id
       destino: [a1b2c3]        # visual_id(s)
       estado: migrado          # migrado | parcial | no migrado | fuera de alcance
       relacion: "1:N (dividido)"
       nota: "se separó en dos gráficos por canal"
   ```
   Si una métrica cae mal clasificada, proponé la regla para `docs/reglas/<origen>.yaml`. Repetí el paso 3 y respondé en 3 líneas: avance por objetos, parciales/no migrados, visuales nuevos.

Si Qlik y Power BI están abiertos y la persona lo pide, podés usar el MCP de Power BI Desktop para mirar un visual puntual; del lado Qlik, `qlik_vivo.py datos` devuelve el resumen de un objeto. No modifiques el modelo ni el reporte.
