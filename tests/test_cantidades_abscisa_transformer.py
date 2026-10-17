"""
Prueba del transformador de cantidades por abscisa (cascada CORTE/LLENO/
LLENO SELECCIONADO/SUBBASE). Incluye a propósito el typo real "SUDBASE"
visto en los archivos del cliente, para que una futura "corrección" del
typo en el archivo de origen no rompa silenciosamente el mapeo.
"""

from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.transform.cantidades_abscisa_transformer import (
    detecta_patron_cantidades_abscisa, transformar_cantidades_abscisa,
)


def _hoja_prueba() -> pd.DataFrame:
    filas = [
        ["TITULO", None, None, None, None, None, None, None, "TITULO2", None, None, None, None, None, None],
        ["AREA", "CORTE", None, None, "LLENO", None, None, None, "AREA", "LLENO SELECCIONADO VIA ANDEN", None, None, "LLENO SUDBASE VIA", None, None],
        [None, "AREA", "AREA PROMEDIO", "VOLUMEN (M3)", "AREA", "AREA PROMEDIO", "VOLUMEN (M3)", None, None, "AREA", "AREA PROMEDIO", "VOLUMEN (M3)", "AREA", "AREA PROMEDIO", "VOLUMEN (M3)"],
        [None] * 15,
        ["k0+470", 0.45, None, None, 9.42, None, None, None, "k0+470", 4.498, None, None, 1.2, None, None],
        [None, None, 0.3535, 1.19, None, 11.395, 38.4, None, None, None, 4.499, 3.95, None, 1.2, 12],
    ]
    return pd.DataFrame(filas)


def test_detecta_patron():
    assert detecta_patron_cantidades_abscisa(_hoja_prueba())


def test_transformar_cantidades_abscisa_mapea_columnas_correctamente():
    resultado = transformar_cantidades_abscisa(_hoja_prueba(), "prueba.xlsx")

    assert resultado.filas_validas == 1
    fila = resultado.dataframe.iloc[0]

    assert fila["abscisa"] == "K0+470"
    assert fila["area_corte"] == 0.45
    assert fila["area_promedio_corte"] == 0.3535
    assert fila["volumen_corte"] == 1.19
    assert fila["area_lleno"] == 9.42
    # Estos dos son los que fallaban antes de tolerar el typo "SUDBASE":
    # sin el fix, area_lleno_sel quedaba pisado con el valor de subbase.
    assert fila["area_lleno_sel"] == 4.498
    assert fila["area_subbase"] == 1.2
    assert fila["volumen_subbase"] == 12
