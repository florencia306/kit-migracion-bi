"""
Conectores de origen y destino.

Origen  (conectores/origen/<nombre>.py) debe exponer:
    NOMBRE: str                                 -> nombre visible ("QlikView")
    leer(ruta) -> list[(hoja, objeto_id, objeto, expresion)]
    normalizar(expresion) -> str                 -> limpia formato/comentarios

Destino (conectores/destino/<nombre>.py) debe exponer:
    NOMBRE: str                                 -> nombre visible ("Power BI")
    LENGUAJE: str                               -> para el reporte ("DAX")
    medidas(ruta_modelo) -> dict[nombre, expresion]
    armar_consulta(caso) -> str                  -> consulta que devuelve columnas de agrupación + "valor"
    class Cliente(opciones): ejecutar(consulta) -> pandas.DataFrame
    normalizar_resultado(df) -> DataFrame        -> columnas con nombre corto + "valor"
"""
import importlib


def cargar_origen(nombre):
    return importlib.import_module(f"conectores.origen.{nombre}")


def cargar_destino(nombre):
    return importlib.import_module(f"conectores.destino.{nombre}")
