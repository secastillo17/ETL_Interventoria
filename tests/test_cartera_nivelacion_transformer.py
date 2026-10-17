"""
Prueba de regresión de dos bugs reales encontrados en
cartera_nivelacion_transformer.py con el archivo
TUBERI_A_SANITARIA_EMS_ETAPA3.xlsx:

  1. La fila de VALORES del bloque "LONGITUD" (la que trae los números,
     justo debajo del encabezado LONGITUD/VISTA MAS/...) se colaba como
     si fuera una progresiva real, inventando una fila de datos con la
     longitud del tramo en el lugar de la progresiva.
  2. Las etiquetas de cierre de cada tramo (PROMEDIO, VOLUMEN DE CORTE,
     MATERIAL RELLENO SELECCIONADO, ARENA, ENTIVADO) se trataban como
     identificador de tubería nueva o como fila de datos.
"""

from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.transform.cartera_nivelacion_transformer import transformar_cartera


def _hoja_dos_tramos_con_pie() -> pd.DataFrame:
    filas = [
        [None, "TUBERIA X", None, None, None],
        ["LONGITUD", "VISTA MAS", "ALTURA INSTRUMENTAL", "BM", "ANCHO ZANJA"],
        [31.55, 1.56, 37.132, 35.572, 0.8],
        [None, None, None, None, None],
        ["ADSA", "CORTE", "VISTA INTERMEDIA", "COTA BATEA", "COTA TERRENO"],
        ["MHD29", None, None, None, None],
        ["K0+00", -1.352, 1.54, 34.24, 35.592],
        ["K0+31.55", -1.132, 1.62, 34.38, 35.512],
        ["PROMEDIO", -1.241, None, None, None],
        ["VOLUMEN DE CORTE", None, None, "31.322m3", None],
        ["MATERIAL RELLENO SELECCIONADO", None, None, "16.1788m3", None],
        ["ARENA", None, None, None, 0.094],
        ["ENTIVADO", None, None, "NO", None],
        ["LONGITUD", "VISTA MAS", "ALTURA INSTRUMENTAL", "BM", "ANCHO ZANJA"],
        [14.13, 0.115, 38.067, 37.952, 0.8],
        [None, None, None, None, None],
        ["ADSA", "CORTE", "VISTA INTERMEDIA", "COTA BATEA", "COTA TERRENO"],
        ["MHAR50A", None, None, None, None],
        ["K0+00", -1.777, 1.63, 34.66, 36.437],
        ["K0+14.13", -1.297, 2.17, 34.6, 35.897],
    ]
    return pd.DataFrame(filas)


def test_fila_de_valores_de_longitud_no_se_cuela_como_progresiva():
    resultado = transformar_cartera(_hoja_dos_tramos_con_pie(), "prueba.xlsx")
    progresivas = set(resultado.dataframe["progresiva"])

    # Antes del fix, aparecía una progresiva fantasma "14.13" (la
    # longitud del segundo tramo, mal leída como si fuera una medición).
    assert "14.13" not in progresivas


def test_etiquetas_de_pie_de_tramo_no_contaminan_los_datos():
    resultado = transformar_cartera(_hoja_dos_tramos_con_pie(), "prueba.xlsx")
    tuberias = set(resultado.dataframe["tuberia"])
    progresivas = set(resultado.dataframe["progresiva"])

    for etiqueta in ("PROMEDIO", "VOLUMEN DE CORTE", "MATERIAL RELLENO SELECCIONADO", "ARENA", "ENTIVADO"):
        assert etiqueta not in tuberias
        assert etiqueta not in progresivas


def test_progresivas_reales_quedan_intactas():
    resultado = transformar_cartera(_hoja_dos_tramos_con_pie(), "prueba.xlsx")
    df = resultado.dataframe

    assert resultado.filas_validas == 4  # 2 progresivas por cada uno de los 2 tramos
    fila = df[(df["tuberia"] == "MHD29") & (df["progresiva"] == "K0+00")].iloc[0]
    assert fila["corte"] == -1.352
    assert fila["cota_batea"] == 34.24

    fila2 = df[(df["tuberia"] == "MHAR50A") & (df["progresiva"] == "K0+14.13")].iloc[0]
    assert fila2["longitud"] == 14.13  # metadatos del segundo tramo, ya sin contaminar la progresiva
