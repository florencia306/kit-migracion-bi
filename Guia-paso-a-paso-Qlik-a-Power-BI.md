# Guía paso a paso: validar la migración de un tablero de QlikView a Power BI

Esta guía sirve para **cualquier tablero** que se migre de QlikView a Power BI con el kit de agentes.

Al terminar vas a tener:

- el catálogo de métricas de Qlik con su medida equivalente en Power BI,
- la validación de valores entre las dos herramientas,
- un reporte HTML con el desvío % por métrica.

> Para la descripción general del kit, ver la página [[Kit de migración y validación de BI]].

**Convenciones de esta guía**

| Marcador | Qué va | Ejemplo |
|---|---|---|
| `<tablero>` | Nombre corto de la carpeta, en minúsculas y con guiones | `ventas-comerciales` |
| `<Tablero>` | Nombre del archivo PBIP | `Ventas Comerciales` |
| `<periodo>` | Período con el que se compara | enero de 2024 |

Los valores que aparecen en las salidas de ejemplo son ilustrativos.

---

## Antes de empezar (una sola vez por persona)

**1. Clonar el repositorio** de agentes y abrirlo en VS Code.

**2. Instalar las dependencias de Python** (3.10 o superior):

```bash
pip install pandas pyyaml pythonnet pyqvd pyodbc pywin32
```

Para leer Qlik en vivo hace falta **QlikView Desktop** instalado y con licencia en la misma PC.

**3. Verificar que Copilot vea los agentes.** Abrí el chat de Copilot en modo agente, desplegá el selector de agentes y comprobá que aparezcan:

- Reporte de migración
- Validador migración
- Auditor de tableros
- Qlik a DAX
- Mapeo de objetos
- Avance del proyecto

**4. Revisar `migracion.yaml`:**

```yaml
origen: qlik
destino: powerbi
```

**5. (Opcional) MCP de Power BI.** Si está configurado, los agentes pueden leer el modelo abierto y crear medidas borrador. No es obligatorio.

---

## Resumen del flujo

| Paso | Qué hacés vos | Qué hace el agente |
|---|---|---|
| 1 | Copiar el PBIP y la carpeta de QlikView (qvw, qvd, source) | — |
| 2 | Abrir el .qvw en QlikView (opcional) | Extrae expresiones, variables y script del .qvw |
| 3 | — | Arma el modelo del origen desde el script y los QVD |
| 4 | Abrir el PBIP en Power BI Desktop | — |
| 5 | Pedir el reporte | Arma el catálogo y propone reglas nuevas |
| 6 | Revisar y confirmar | Escribe los casos de prueba |
| 7 | — | Valida los valores |
| 8 | Abrir el HTML | Genera el reporte |
| 9 | Confirmar las causas con el equipo | Propone causas de las diferencias |
| 10–11 | (Opcional) | Traduce medidas y audita el modelo |
| 12 | Subir los cambios al repo | — |

---

## Paso 1 · Preparar la carpeta del tablero

Copiá el proyecto PBIP y la carpeta del tablero de QlikView tal como la tenés (front, QVD y source):

```
tableros/<tablero>/
├── <Tablero>.pbip
├── <Tablero>.Report/
├── <Tablero>.SemanticModel/
├── qlik/                  # 🔒 no se sube al repo
│   ├── <Tablero>.qvw
│   ├── qvd/
│   └── source/            # scripts de carga (.qvs) e includes
├── origen/                # lo que genera el kit a partir de qlik/
└── tests/
```

> ⚠️ Usá la versión del modelo que apunta a **QA/test**, nunca a producción.
> Si el tablero no está guardado como PBIP, en Power BI Desktop andá a **Archivo → Guardar como → Proyecto de Power BI (.pbip)**.
> 🔒 `qlik/` completa está en el `.gitignore`: el .qvw, los QVD y los scripts (que pueden tener conexiones) quedan solo en tu PC.

---

## Paso 2 · Extraer todo del .qvw (el agente lo hace)

El kit se conecta a QlikView Desktop y lee el documento: hojas, objetos, expresiones, dimensiones, variables y script de carga. Si el .qvw ya está abierto usa ese; si no, lo abre sin recargar datos.

```bash
python scripts/herramientas/qlik_vivo.py extraer "tableros/<tablero>/qlik/<Tablero>.qvw" tableros/<tablero>/origen
```

```
Hojas: 9 | objetos: 184 | expresiones: 811 | variables: 57 | script: sí
```

Genera en `origen/`: `expresiones.csv` (lo usa el catálogo), `objetos.csv`, `variables.csv` y `script.qvs` con las conexiones y contraseñas ocultas.

> Sin QlikView Desktop: exportá las expresiones con **Configuración → Resumen de expresiones** (`Ctrl + Alt + E`) a `origen/metricas.tab`, o usá la carpeta `-prj` con `qlik_extraer_prj.py`.

---

## Paso 3 · Modelo del origen desde el script y los QVD (el agente lo hace)

```bash
python scripts/herramientas/qlik_script.py tableros/<tablero>/qlik/source tableros/<tablero>/origen --qvd tableros/<tablero>/qlik/qvd
```

- `modelo-origen.csv`: cada campo de Qlik con su tabla y la expresión con que se calcula (`ApplyMap`, `If`, fechas…).
- `tablas-origen.csv`: de dónde sale cada tabla, sus **filtros `WHERE`**, joins y QVD que genera.
- `qvd-campos.csv`: campos y cantidad de filas de cada QVD. Lee solo la cabecera, **nunca los datos**.

El agente usa estos archivos para completar `docs/mapeo.md` (campo de Qlik → columna del modelo) y para detectar filtros o transformaciones que el modelo de Power BI tiene que replicar.

---

## Paso 4 · Abrir el tablero en Power BI Desktop

Abrí `<Tablero>.pbip` en Power BI Desktop y dejalo abierto mientras trabajás. El validador se conecta a ese Desktop para ejecutar las medidas.

> Si tenés varios Desktop abiertos, el validador usa el último que abriste. Dejá abierto solo el del tablero que estás validando.

---

## Paso 5 · Generar el catálogo con el agente

En el chat de Copilot, elegí el agente **Reporte de migración** y escribí:

```
Generá el reporte de migración del tablero <tablero>.
Qlik está en qlik/<Tablero>.qvw.
```

El agente ejecuta `scripts/catalogo.py` y lee solo el resumen:

```
640 expresiones | 410 únicas | 32 métricas | migrada: 20 | sin_medida: 6 | fuera: 3 | tecnico: 3 | sin clasificar: 12
Revisión alta: <métricas que conviene revisar primero>
```

**Cómo se lee:**

| Estado | Significa |
|---|---|
| `migrada` | La métrica tiene una medida equivalente en Power BI. |
| `sin_medida` | No hay medida equivalente. Confirmá con negocio si todavía se usa: la migración no tiene por qué ser 1 a 1. |
| `fuera` | La hoja de Qlik no tiene página en Power BI. |
| `tecnico` | Etiquetas, recargas o cálculos propios del visual. No se migran como medida. |
| `sin clasificar` | Ninguna regla reconoce la expresión (ver abajo). |

### Expresiones sin clasificar (lo normal en un tablero nuevo)

Las reglas de `docs/reglas/qlik.yaml` se comparten entre todos los tableros. Cuando migrás uno nuevo, aparecen métricas que las reglas todavía no conocen. El agente te muestra algunas y propone reglas. Por ejemplo:

```yaml
- id: clientes_activos
  area: Comercial
  metrica: Clientes activos
  patrones: ['ClienteId', 'Estado.*Activo']
  medidas_destino: ['# Clientes Activos']
```

Revisalas, confirmá, y el agente vuelve a generar el catálogo hasta llegar a 0 sin clasificar o a un número que aceptes. Cada tablero que migrás hace que las reglas reconozcan más, y el siguiente cuesta menos.

> Si el resumen dice que una medida de las reglas **no existe en el modelo**, el agente propone corregir `medidas_destino` con el nombre real.

---

## Paso 6 · Casos de prueba

Para cada métrica migrada, el agente agrega casos en `tableros/<tablero>/tests/casos.yaml`. La referencia se lee **en vivo del objeto de Qlik**, con el período fijado por variable o selección: no hace falta exportar nada.

```yaml
tablero: <tablero>
destino: powerbi
qlik:                                   # común a todos los casos tipo qlik
  documento: qlik/<Tablero>.qvw
  variables: { vPeriodoReporte: "202608" }

casos:
  # Una tarjeta (objeto de texto) en el período
  - id: kpi_clientes_activos
    medida: "# Clientes Activos"
    filtros: { "'Calendar'[YearMonth]": [202608] }
    referencia: { tipo: qlik, objeto: TX12 }
    tolerancia: 0

  # Una serie por año (columna = etiqueta de la expresión en el gráfico)
  - id: evolucion_ventas_por_anio
    medida: "$ Ventas"
    agrupar_por: ["'Calendar'[Year]"]
    referencia:
      tipo: qlik
      objeto: CH05
      columna: Ventas
      selecciones: { "Canal": ["Agentes"] }   # opcional, se suma al período
      renombrar: { "Año": "Year" }            # dimensión en Qlik -> en Power BI
    tolerancia_pct: 0.5
```

Antes de cada caso el validador limpia las selecciones, fija las variables del caso, lee el objeto y vuelve a dejar las variables como estaban. Para ver qué devuelve un objeto sin validar:

```bash
python scripts/herramientas/qlik_vivo.py datos "tableros/<tablero>/qlik/<Tablero>.qvw" CH05 --var vPeriodoReporte=202608
```

Tipos de referencia disponibles:

| Tipo | Cuándo usarlo |
|---|---|
| `qlik` | Objeto de QlikView en vivo. Es lo recomendado: es exactamente lo que ve el usuario hoy, set analysis incluido. |
| `csv` | Export manual de un objeto (si no tenés QlikView Desktop a mano). |
| `qvd` | Total calculado desde un QVD local, que nunca se sube al repo. |
| `sql` | Consulta directa al data warehouse, como referencia independiente. |

También se pueden validar **identidades internas**, que no necesitan Qlik. Por ejemplo: *stock final = stock inicial + altas − bajas*, o *total de la tabla = tarjeta*.

> ⚠️ **El período tiene que ser el mismo en las dos herramientas.** La variable o selección de período en Qlik y el filtro de `'Calendar'` del caso tienen que coincidir. Es la causa más común de diferencias falsas.

El agente elige el objeto con `origen/objetos.csv` (hoja, título, dimensiones). Usá gráficos y tablas simples; las tablas pivote conviene validarlas con un gráfico o tabla simple equivalente.

Para revisar las consultas DAX sin ejecutarlas:

```bash
python scripts/validar.py tableros/<tablero>/tests/casos.yaml --dry-run
```

---

## Paso 7 · Validación

El agente ejecuta `scripts/validar.py` con tu Desktop abierto:

```
<tablero>: 15 casos | OK: 13 | DIFERENCIA: 2
                  caso          medida      estado  filas  filas_con_dif  total_destino  total_origen
 kpi_clientes_activos  # Clientes Activos  DIFERENCIA      1              1           4870          4912
 ...
Detalle: validacion/resultados/<tablero>
```

Los archivos quedan en `validacion/resultados/<tablero>/`:

- `resumen_<fecha>.csv`: un renglón por caso.
- `detalle_<fecha>.csv`: valores fila por fila. Está en el `.gitignore`.

---

## Paso 8 · El reporte HTML

El agente ejecuta `scripts/reporte.py` y responde con 3 líneas y la ruta del archivo:

```
Validadas: 13/20 · Con diferencias: 2 · Revisión alta: 3
validacion/resultados/<tablero>/reporte-migracion.html
```

Abrilo con doble clic. El reporte tiene cuatro partes:

1. **Tarjetas de resumen**: expresiones, métricas, migradas, validadas y con diferencias.
2. **Estado del catálogo**: qué parte de las expresiones de Qlik quedó migrada, sin medida, fuera de alcance o técnica.
3. **Cortes temporales**: cuántas expresiones usa Qlik por corte (mes, acumulado del año, evolución, stock) y cómo se resuelve cada uno con la tabla `'Calendar'`.
4. **Catálogo de métricas**, con filtros por área, estado y severidad:
   - **Desvío vs QlikView**: 🟢 coincide · 🟡 diferencia de hasta 1 % · 🔴 diferencia mayor a 1 %. Muestra también los dos valores.
   - **Comparar QlikView vs Power BI**: abre la expresión de Qlik y el DAX de la medida, lado a lado.
   - **Revisar**: observaciones y severidad (alta, media o baja).

---

## Paso 9 · Investigar las diferencias

Elegí el agente **Validador migración** y pedile:

```
Analizá la diferencia del caso <id del caso>.
```

El agente lee solo las filas de ese caso y propone hasta 3 causas probables. Las más comunes en Qlik → Power BI:

| Causa | Cómo se ve |
|---|---|
| **Relación de fechas distinta** | Qlik corta por una fecha (por ejemplo, vigencia) y la medida usa otra relación (por ejemplo, alta o baja). Falta un `USERELATIONSHIP`. |
| **Bordes del período** | Qlik usa `<=` y `>` en unas expresiones y `<` y `>=` en otras. |
| **Conteo sin DISTINCT** | Qlik usa `Count(Id)` y Power BI `DISTINCTCOUNT`: difieren si hay filas repetidas. |
| **Set analysis que ignora filtros** | `{1}` o `{<Campo=>}` en Qlik; en DAX hace falta `REMOVEFILTERS` o `ALL`. |
| **Granularidad** | Se cuentan unidades distintas: por ejemplo, pólizas contra certificados, o pedidos contra líneas. |
| **Datos distintos** | Fecha de corte o ambiente distinto (QA contra producción). |

Cuando confirmes la causa con el equipo, pedile que la registre:

```
Confirmado: es la relación de fechas. Actualizá la observación en las reglas.
```

La observación queda en `docs/reglas/qlik.yaml` y aparece en los próximos reportes, también en otros tableros que usen esa métrica.

> El agente **no modifica el modelo**. Si hay que corregir una medida, la propone y la aprobás vos.

---

## Paso 10 · (Opcional) Traducir medidas que faltan

Para métricas `sin_medida` que sí hay que migrar, usá el agente **Qlik a DAX**:

```
Traducí a DAX las métricas sin medida del área <área> del tablero <tablero>.
```

Respuesta esperada, por cada expresión:

````
```dax
# Clientes Activos =
CALCULATE(
    DISTINCTCOUNT( Clientes[ClienteId] ),
    Clientes[Estado] = "Activo"
)
```
Confianza: ALTA · REVISAR: —
````

Para mejores traducciones:

- mantené `docs/mapeo.md` al día (campo de Qlik → tabla y columna del modelo);
- sumá a `docs/ejemplos-qlik-dax.md` las traducciones ya validadas (5 a 10 buenas alcanzan).

Si el MCP de Power BI está conectado, podés pedirle que cree la medida en la carpeta `_Migracion\Borrador`. El agente también agrega el caso de prueba para validarla.

---

## Paso 11 · (Opcional) Auditoría técnica del tablero

Con el agente **Auditor de tableros**:

```
Auditá el tablero <tablero>.
```

Revisa, pidiendo confirmación en cada etapa:

- **Inventario**: qué medidas usa cada visual y cuáles no se usan.
- **Buenas prácticas**: tablas de fecha automáticas, tablas duplicadas, medidas de prueba, servidores escritos en las consultas, divisiones sin `DIVIDE`.
- **Consistencia interna**: identidades que siempre deberían cumplirse.

Genera un informe con semáforo por página.

---

## Paso 12 · Subir los cambios al repo

**Sí se suben:**

- el proyecto PBIP,
- `origen/metricas.tab` (solo contiene expresiones),
- `tests/casos.yaml`,
- los cambios en `docs/reglas/qlik.yaml`, `docs/mapeo.md` y `docs/ejemplos-qlik-dax.md`,
- el catálogo, los resúmenes y el reporte HTML (si el equipo decidió versionarlos).

**No se suben** (ya están en el `.gitignore`):

- QVD y datos locales,
- los CSV exportados de Qlik con valores,
- los `detalle_*.csv`.

> Commit sugerido: `<tablero>: catálogo, casos y reporte de validación (<periodo>)`

---

## Prompts rápidos

| Quiero… | Agente | Prompt |
|---|---|---|
| El reporte completo | Reporte de migración | `Generá el reporte de migración del tablero <tablero>.` |
| Actualizarlo después de corregir algo | Reporte de migración | `Volvé a validar y regenerá el reporte de <tablero>.` |
| Validar una medida puntual | Validador migración | `Validá <medida> por año contra el objeto CH05 de Qlik con vPeriodoReporte=202608.` |
| Entender una diferencia | Validador migración | `Analizá la diferencia del caso <id>.` |
| Traducir expresiones | Qlik a DAX | `Traducí a DAX las métricas sin medida del área <área>.` |
| Revisar el modelo | Auditor de tableros | `Auditá el tablero <tablero>.` |

---

## Problemas frecuentes

| Mensaje o síntoma | Causa | Solución |
|---|---|---|
| `No encontré Power BI Desktop abierto` | Desktop cerrado o el `.pbip` no terminó de cargar | Abrí el `.pbip`, esperá que cargue y volvé a correr. |
| `No encontré Microsoft.AnalysisServices.AdomdClient.dll` | Desktop instalado en otra ruta | Pasá la ruta con `--adomd "<ruta al dll>"`. |
| Casos en ERROR con el nombre de una medida | La medida no existe o cambió de nombre | Revisá el nombre exacto en el modelo y en `casos.yaml`. |
| Diferencias en todos los casos | El período de Qlik y el filtro de `'Calendar'` no coinciden | Alineá `variables` del bloque `qlik:` y los `filtros` del caso. |
| Números mal leídos (por ejemplo, 38 en vez de 38.437) | Formato de números del objeto o del export | Agregá `formato_numero: us` (o `separador: ";"` en CSV) en la `referencia`. |
| `No hay un documento abierto en QlikView` / `Falta pywin32` | QlikView Desktop cerrado o falta la librería | Pasá la ruta del .qvw o `pip install pywin32`. |
| Un objeto de Qlik devuelve columnas raras | Es una tabla pivote o un contenedor | Usá un gráfico o tabla simple equivalente, o `referencia: tipo: csv`. |
| Muchas expresiones sin clasificar | Tablero con métricas nuevas | Es esperable: dejá que el agente proponga reglas (paso 5). |
| El agente lee archivos enteros y gasta tokens | Pedido demasiado amplio | Un chat por tarea y archivos puntuales con `#archivo`. |

---

_Última actualización: completar · Contacto: completar_
