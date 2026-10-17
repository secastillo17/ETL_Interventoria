"""
Transformador de hojas de presupuesto/cantidades jerárquico, patrón
visto en hojas "RESUMEN": filas con código (3, 3.1, 3.1.1...),
descripción, unidad y cantidad, donde los códigos de capítulo (ej. "3")
y subcapítulo (ej. "3.1") son encabezados de sección resaltados, sin
unidad ni cantidad propias — solo los ítems de último nivel (ej.
"3.1.1") tienen unidad y cantidad.

La columna donde vive el código NO siempre es la primera: en archivos
reales del cliente aparece en la columna B (índice 1), con la columna A
vacía (probablemente para dejar espacio a una sangría visual en Excel).
Por eso la columna del código se DETECTA revisando las primeras 3
columnas, en vez de asumir siempre la columna 0.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import re
import pandas as pd

PATRON_CODIGO_ITEM = re.compile(r"^\d+(\.\d+){2,}$")  # ej: 3.1.1 (2+ puntos = ítem con cantidad)
PATRON_CODIGO_SECCION = re.compile(r"^\d+(\.\d+)?$")  # ej: 3 o 3.1 (sección, sin cantidad)
MAX_COLUMNAS_A_REVISAR = 3


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _normalizar(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def _detectar_columna_codigo(hoja_df: pd.DataFrame) -> Optional[int]:
    """Revisa las primeras columnas y devuelve el índice de la que tenga
    más coincidencias con el patrón de código jerárquico (3.1.1), o None
    si ninguna tiene al menos 2."""
    mejor_columna, mejor_conteo = None, 0
    for c in range(min(MAX_COLUMNAS_A_REVISAR, hoja_df.shape[1])):
        conteo = sum(
            1 for i in range(len(hoja_df))
            if PATRON_CODIGO_ITEM.match(_normalizar(hoja_df.iat[i, c]))
        )
        if conteo > mejor_conteo:
            mejor_columna, mejor_conteo = c, conteo
    return mejor_columna if mejor_conteo >= 2 else None


def detecta_patron_presupuesto(hoja_df: pd.DataFrame) -> bool:
    return _detectar_columna_codigo(hoja_df) is not None


def transformar_presupuesto(hoja_df: pd.DataFrame, nombre_archivo: str) -> ResultadoTransformacion:
    errores: List[str] = []
    filas = []
    seccion_actual = ""

    col_codigo = _detectar_columna_codigo(hoja_df)
    if col_codigo is None:
        errores.append(f"{nombre_archivo}: no se encontró una columna con códigos jerárquicos (ej. 3.1.1).")
        return ResultadoTransformacion(pd.DataFrame(), 0, 0, errores)

    col_desc, col_unidad, col_cantidad = col_codigo + 1, col_codigo + 2, col_codigo + 3
    ncols = hoja_df.shape[1]

    for i in range(len(hoja_df)):
        fila = hoja_df.iloc[i]
        codigo = _normalizar(fila[col_codigo])
        descripcion = _normalizar(fila[col_desc]) if col_desc < ncols else ""

        if not codigo:
            continue

        if PATRON_CODIGO_ITEM.match(codigo):
            unidad = _normalizar(fila[col_unidad]) if col_unidad < ncols else ""
            cantidad_raw = fila[col_cantidad] if col_cantidad < ncols else None
            try:
                cantidad = float(cantidad_raw)
            except (ValueError, TypeError):
                cantidad = None
                errores.append(f"{nombre_archivo}: ítem {codigo} sin cantidad numérica válida.")

            filas.append({
                "seccion": seccion_actual,
                "codigo": codigo,
                "descripcion": descripcion,
                "unidad": unidad,
                "cantidad": cantidad,
            })
        elif PATRON_CODIGO_SECCION.match(codigo):
            seccion_actual = f"{codigo} {descripcion}".strip()

    df = pd.DataFrame(filas)
    return ResultadoTransformacion(
        dataframe=df,
        filas_validas=len(df),
        filas_descartadas=0,
        errores=errores,
    )

