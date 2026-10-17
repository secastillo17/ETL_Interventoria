"""
Transformador de archivos Excel de "cantidades ejecutadas" (DATO-03).

Reglas de normalización aplicadas (ajústalas según el formato real
que use Planialtimetría e Ingeniería del Caribe S.A.S.):
  - Nombres de columnas estandarizados a minúsculas y sin espacios.
  - Se exige que existan las columnas: proyecto, item, unidad,
    cantidad_ejecutada, fecha_registro.
  - Se descartan filas totalmente vacías.
  - Se valida que cantidad_ejecutada sea numérica.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List
import pandas as pd

COLUMNAS_ESPERADAS = ["proyecto", "item", "unidad", "cantidad_ejecutada", "fecha_registro"]


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("í", "i").replace("ó", "o")
        for c in df.columns
    ]
    return df


def transformar_excel_cantidades(path: Path) -> ResultadoTransformacion:
    errores: List[str] = []
    df = pd.read_excel(path)
    df = _normalizar_columnas(df)

    faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
    if faltantes:
        errores.append(f"Columnas faltantes en {path.name}: {faltantes}")
        return ResultadoTransformacion(pd.DataFrame(), 0, len(df), errores)

    df = df.dropna(how="all")
    filas_originales = len(df)

    # Validar tipo numérico de cantidad_ejecutada
    df["cantidad_ejecutada"] = pd.to_numeric(df["cantidad_ejecutada"], errors="coerce")
    invalidas = df["cantidad_ejecutada"].isna().sum()
    if invalidas:
        errores.append(f"{invalidas} filas con cantidad_ejecutada no numérica en {path.name}")
    df = df.dropna(subset=["cantidad_ejecutada"])

    # Normalizar fecha
    df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce").dt.date

    df = df[COLUMNAS_ESPERADAS]
    filas_descartadas = filas_originales - len(df)

    return ResultadoTransformacion(
        dataframe=df,
        filas_validas=len(df),
        filas_descartadas=filas_descartadas,
        errores=errores,
    )
