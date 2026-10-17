"""
Transformador de coordenadas dentro de una hoja de Excel SIN fila de
encabezado — patrón real visto en archivos que el cliente exporta
directamente desde el software topográfico (a veces guardados con
extensión .xlsx, a veces mal renombrados como .csv, ver
extract/sniffer.py para ese segundo caso).

La hoja no tiene encabezado, y cada fila es igual al Formato A de los
TXT de cartera (transform/txt_transformer.py): PUNTO, CODIGO/DESCRIPCION,
COORD1, COORD2, ELEVACION. Se reutiliza la misma regla de magnitud para
decidir cuál coordenada es NORTE y cuál es ESTE.

Este detector es intencionalmente el ÚLTIMO que prueba el dispatcher
para hojas sin encabezado (excel_dispatcher.py): al no depender de
ningún texto identificador (como "MH", "ADSA" o un código jerárquico),
es el más fácil de confundir con una tabla de otro tipo, así que solo
se usa cuando ningún patrón más específico coincidió.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _es_fila_coordenada(fila) -> bool:
    """Una fila 'PUNTO, CODIGO, COORD1, COORD2, ELEVACION' donde las dos
    coordenadas centrales son mucho mayores en magnitud que la elevación
    (mismo supuesto de txt_transformer.py, confirmado con los archivos
    reales del cliente: coordenadas ~900,000-1'700,000 vs elevaciones
    de un par de decenas a poco más de cien)."""
    valores = list(fila)[:5]
    if len(valores) != 5 or any(pd.isna(v) for v in valores):
        return False
    try:
        coord1, coord2, elevacion = float(valores[2]), float(valores[3]), float(valores[4])
    except (TypeError, ValueError):
        return False
    return abs(coord1) > 1000 and abs(coord2) > 1000 and abs(elevacion) < 1000


def detecta_patron_coordenadas_sin_encabezado(hoja_df: pd.DataFrame) -> bool:
    if hoja_df.shape[1] < 5 or len(hoja_df) < 2:
        return False
    coincidencias = sum(1 for i in range(len(hoja_df)) if _es_fila_coordenada(hoja_df.iloc[i]))
    # Al menos la mitad de las filas deben calzar con el patrón, para no
    # confundir una tabla cualquiera de 5+ columnas con números grandes.
    return coincidencias >= max(2, len(hoja_df) // 2)


def transformar_coordenadas_sin_encabezado(hoja_df: pd.DataFrame, nombre_archivo: str) -> ResultadoTransformacion:
    errores: List[str] = []
    filas = []
    descartadas = 0

    for i in range(len(hoja_df)):
        fila = hoja_df.iloc[i]
        if not _es_fila_coordenada(fila):
            if not all(pd.isna(v) for v in list(fila)[:5]):
                descartadas += 1
            continue

        valores = list(fila)[:5]
        punto, descripcion = str(valores[0]).strip(), str(valores[1]).strip()
        coord1, coord2, elevacion = float(valores[2]), float(valores[3]), float(valores[4])
        norte, este = (coord1, coord2) if coord1 > coord2 else (coord2, coord1)

        filas.append({
            "punto": punto, "norte": norte, "este": este,
            "elevacion": elevacion, "descripcion": descripcion,
        })

    if descartadas:
        errores.append(f"{nombre_archivo}: {descartadas} filas no calzan con el patrón de coordenadas y se descartaron.")

    df = pd.DataFrame(filas, columns=["punto", "norte", "este", "elevacion", "descripcion"])
    return ResultadoTransformacion(
        dataframe=df, filas_validas=len(df), filas_descartadas=descartadas, errores=errores,
    )
