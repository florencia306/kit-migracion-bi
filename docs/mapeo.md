# Mapeo de campos QlikView → modelo Power BI

Los agentes usan este archivo para saber dónde quedó cada campo de Qlik en el modelo estrella. Completá una fila por campo a medida que lo migres. Si un campo no está acá, el agente va a preguntar en lugar de inventarlo.

| Tablón / tabla Qlik | Campo Qlik | Tabla Power BI | Columna Power BI | Notas |
|---|---|---|---|---|
| (ej.) Tablon_Polizas | NroPoliza | Polizas | IDPolizas | Clave para conteos distintos |
| (ej.) Tablon_Polizas | FechaBaja | Polizas | Fecha_Baja_Sistema_Poliza | Relación inactiva con 'Calendar' → usar USERELATIONSHIP |
| (ej.) Tablon_Polizas | Estado | Polizas | Tipo_Estado_Pol | Valores: Vigente / No Vigente |
| (ej.) Tablon_Polizas | Canal | dim_canal | (completar) | |
| | | | | |

## Variables de Qlik
| Variable | Valor / lógica | Equivalente en Power BI |
|---|---|---|
| (ej.) vAnioActual | =Year(Today()) | YEAR( TODAY() ) o selección de 'Calendar'[Year] |
