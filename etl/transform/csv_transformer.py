"""
Transformador de CSV de cartera topográfica (DATO-02).

Patrón real observado: encabezados PUNTOS;ESTE;NORTE;COTA;NOMBRE,
separador ';' y decimales con coma en vez de punto (formato regional
de Excel en español), ej:

    PUNTOS;ESTE;NORTE;COTA;NOMBRE
    D72A;918549,37;1711339,405;0,243;DELTA

Se reutiliza la misma lógica de coordenadas_excel_transformer.py una
vez que el CSV ya está cargado como DataFrame con esos encabezados,
para no duplicar reglas de validación entre los dos formatos.

Si el archivo viene con separador ',' y punto decimal (formato
"internacional"), también se soporta: se prueba primero el formato
';' + coma decimal (el más visto en los archivos reales del cliente)
y, si no produce las columnas esperadas, se reintenta con ',' + punto.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List
import pandas as pd

from etl.transform.coordenadas_excel_transformer import (
    COLUMNAS_ESPERADAS,
    detecta_patron_coordenadas,
    transformar_coordenadas,
)


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _leer_csv_flexible(path: Path) -> pd.DataFrame:
    """Intenta primero ';' + coma decimal (formato real del cliente);
    si las columnas no coinciden, reintenta con ',' + punto decimal."""
    df = pd.read_csv(path, sep=";", decimal=",")
    df.columns = [str(c).strip().upper() for c in df.columns]
    if COLUMNAS_ESPERADAS.issubset(set(df.columns)):
        return df

    df = pd.read_csv(path, sep=",", decimal=".")
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df


def transformar_csv(path: Path) -> ResultadoTransformacion:
    try:
        df = _leer_csv_flexible(path)
    except Exception as exc:  # noqa: BLE001
        return ResultadoTransformacion(
            dataframe=pd.DataFrame(), filas_validas=0, filas_descartadas=1,
            errores=[f"{path.name}: no se pudo leer el CSV ({exc})."],
        )

    if not detecta_patron_coordenadas(df):
        return ResultadoTransformacion(
            dataframe=pd.DataFrame(), filas_validas=0, filas_descartadas=1,
            errores=[
                f"{path.name}: no tiene las columnas esperadas "
                f"({sorted(COLUMNAS_ESPERADAS)}). Se cataloga sin transformar."
            ],
        )

    resultado = transformar_coordenadas(df, path.name)
    return ResultadoTransformacion(
        dataframe=resultado.dataframe,
        filas_validas=resultado.filas_validas,
        filas_descartadas=resultado.filas_descartadas,
        errores=resultado.errores,
    )
