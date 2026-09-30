# Ejemplos validados Qlik → DAX

Agregá acá cada medida que migraste y validaste. El agente `Qlik a DAX` copia estos patrones, así que cuantos más ejemplos reales (con nombres genéricos si hace falta) haya, mejores van a ser sus traducciones. Ideal: entre 5 y 10, de complejidad variada.

---

## Ejemplo 1 — Pólizas bajas (fecha alternativa)

**Qlik (original):**
```
// COMPLETAR con la expresión de QlikView
```

**DAX (validada):**
```dax
# Polizas Bajas =
CALCULATE(
    DISTINCTCOUNT( Polizas[IDPolizas] ),
    Polizas[Tipo_Estado_Pol] = "No Vigente",
    NOT ISBLANK( Polizas[Fecha_Baja_Sistema_Poliza] ), -- evita arrastre por blanks
    USERELATIONSHIP( Polizas[Fecha_Baja_Sistema_Poliza], 'Calendar'[Date] )
)
```

**Notas:** las bajas se cuentan por fecha de baja, no por fecha de emisión, por eso se activa la relación inactiva.

---

## Ejemplo 2 — Stock final (acumulado)

**Qlik (original):**
```
// COMPLETAR con la expresión de QlikView
```

**DAX (validada):**
```dax
# Polizas Stock Final =
VAR FechaFinPeriodo = MAX( 'Calendar'[Date] )
RETURN
CALCULATE(
    [# Polizas Emitidas] - [# Polizas Bajas],
    FILTER( ALL( 'Calendar' ), 'Calendar'[Date] <= FechaFinPeriodo )
)
```

**Notas:** acumulado histórico hasta el fin del período seleccionado. Sin filtro de fecha devuelve el total histórico (igual que `# Polizas Dif (Altas-Bajas)`).

---

## Ejemplo 3 — (plantilla)

**Qlik (original):**
```
```

**DAX (validada):**
```dax
```

**Notas:**
