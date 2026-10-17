"""
Transformador de TXT de mediciones topográficas (DATO-02).

El cliente exporta desde AutoCAD en 2 variantes de formato, según cómo
lo genere el jefe de la empresa:

  Formato A (sin timestamp):  PUNTO,DESCRIPCION,COORD1,COORD2,ELEVACION
      ej: 1,D1,1711143.003,916808.491,36.271

  Formato B (con timestamp):  HH:MM:SS.mmm PUNTO,COORD1,COORD2,ELEVACION,DESCRIPCION
      ej: 14:07:04.928 100,915388.7650,1711269.8500,14.6280,E1

Se detecta el formato automáticamente por línea: si el segundo campo no
es numérico, es Formato A (ahí va la descripción); si es numérico, es
Formato B.

Cuál coordenada es NORTE y cuál es ESTE varía entre las dos variantes
(confirmado por el cliente). Se asume que la de mayor magnitud es
NORTE, según la evidencia real de sus archivos (valores ~1'700,000 para
Norte vs ~900,000 para Este). Este supuesto debe validarse con el
topógrafo si se detectan coordenadas de magnitud similar.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List
import re
import pandas as pd

COLUMNAS = ["punto", "norte", "este", "elevacion", "descripcion"]
PATRON_TIMESTAMP = re.compile(r"^\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\s+")


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _es_numero(valor: str) -> bool:
    try:
        float(valor)
        return True
    except ValueError:
        return False


def _parsear_linea(linea: str):
    """Devuelve un dict con punto/norte/este/elevacion/descripcion, o None si no se pudo parsear."""
    linea = PATRON_TIMESTAMP.sub("", linea)  # quita el timestamp del Formato B si existe
    partes = [p.strip() for p in linea.split(",")]
    if len(partes) != 5:
        return None

    punto = partes[0]
    if _es_numero(partes[1]):
        # Formato B: PUNTO,COORD1,COORD2,ELEVACION,DESCRIPCION
        coord1, coord2, elevacion, descripcion = partes[1], partes[2], partes[3], partes[4]
    else:
        # Formato A: PUNTO,DESCRIPCION,COORD1,COORD2,ELEVACION
        descripcion, coord1, coord2, elevacion = partes[1], partes[2], partes[3], partes[4]

    coord1, coord2, elevacion = float(coord1), float(coord2), float(elevacion)
    norte, este = (coord1, coord2) if coord1 > coord2 else (coord2, coord1)

    return {
        "punto": punto,
        "norte": norte,
        "este": este,
        "elevacion": elevacion,
        "descripcion": descripcion,
    }


def transformar_txt_mediciones(path: Path) -> ResultadoTransformacion:
    errores: List[str] = []
    filas = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lineas = [l.strip() for l in f if l.strip()]

    for i, linea in enumerate(lineas, start=1):
        try:
            fila = _parsear_linea(linea)
            if fila is None:
                errores.append(f"{path.name} línea {i}: formato inválido -> '{linea}'")
                continue
            filas.append(fila)
        except ValueError:
            errores.append(f"{path.name} línea {i}: coordenadas no numéricas -> '{linea}'")

    df = pd.DataFrame(filas, columns=COLUMNAS)

    return ResultadoTransformacion(
        dataframe=df,
        filas_validas=len(df),
        filas_descartadas=len(lineas) - len(df),
        errores=errores,
    )
