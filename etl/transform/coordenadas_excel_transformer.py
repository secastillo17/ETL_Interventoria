"""
Transformador de hojas de coordenadas en Excel: mismo concepto que los
TXT de mediciones topográficas, pero entregado como tabla de Excel con
encabezados explícitos PUNTOS, ESTE, NORTE, COTA, NOMBRE. Al venir
Norte y Este ya identificados por nombre de columna, aquí no hace
falta el supuesto de magnitud que sí es necesario para los TXT.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List
import pandas as pd

COLUMNAS_ESPERADAS = {"PUNTOS", "ESTE", "NORTE", "COTA", "NOMBRE"}


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df


def detecta_patron_coordenadas(hoja_df: pd.DataFrame) -> bool:
    df = hoja_df.copy()
    df = _normalizar_columnas(df)
    return COLUMNAS_ESPERADAS.issubset(set(df.columns))


def transformar_coordenadas(hoja_df: pd.DataFrame, nombre_archivo: str) -> ResultadoTransformacion:
    errores: List[str] = []
    df = _normalizar_columnas(hoja_df.copy())
    filas_originales = len(df)

    df = df.dropna(subset=["PUNTOS"])
    for col in ("ESTE", "NORTE", "COTA"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    invalidas = df[["ESTE", "NORTE", "COTA"]].isna().any(axis=1).sum()
    if invalidas:
        errores.append(f"{nombre_archivo}: {invalidas} filas con coordenadas no numéricas.")
    df = df.dropna(subset=["ESTE", "NORTE", "COTA"])

    df = df.rename(columns={
        "PUNTOS": "punto", "ESTE": "este", "NORTE": "norte",
        "COTA": "elevacion", "NOMBRE": "descripcion",
    })[["punto", "norte", "este", "elevacion", "descripcion"]]

    return ResultadoTransformacion(
        dataframe=df,
        filas_validas=len(df),
        filas_descartadas=filas_originales - len(df),
        errores=errores,
    )
