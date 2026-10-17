"""
Catalogador de archivos DWG (DATO-01: Planos técnicos).

A diferencia de excel_transformer.py y txt_transformer.py, este módulo NO
transforma contenido tabular: el DWG es un formato binario propietario de
Autodesk, y no existe una librería Python que lo lea directamente (las
disponibles, como ezdxf, solo leen DXF, su formato hermano abierto).

Esto es intencional y coherente con el alcance aprobado en el
anteproyecto: el plano es un documento de referencia, no una fuente de
datos tabulares. Aquí solo se valida que el archivo sea realmente un DWG
(revisando su firma binaria) y se deja que main.py registre sus metadatos
en archivo_metadato, igual que se haría con una foto. El archivo en sí
permanece intacto en el repositorio documental (Google Drive) para que el
ingeniero lo siga abriendo en AutoCAD normalmente.

Si más adelante se necesita extraer geometría real del plano (capas,
coordenadas, bloques), el camino es: convertir el DWG a DXF con el ODA
File Converter (herramienta externa gratuita, no es Python) y luego leer
ese DXF con la librería ezdxf. Eso amplía el alcance actual y conviene
acordarlo primero con el director.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List
import pandas as pd

# Los archivos DWG empiezan con una firma "AC10xx" o "AC1032", etc.,
# según la versión de AutoCAD en que se guardaron. Validar esto evita
# catalogar por error un archivo renombrado que no es realmente un DWG.
FIRMAS_DWG_VALIDAS = (b"AC10", b"AC15", b"AC18", b"AC21", b"AC24", b"AC32")


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def catalogar_dwg(path: Path) -> ResultadoTransformacion:
    errores: List[str] = []

    with open(path, "rb") as f:
        firma = f.read(4)

    es_dwg_valido = firma in FIRMAS_DWG_VALIDAS
    if not es_dwg_valido:
        errores.append(
            f"{path.name}: la firma binaria no corresponde a un DWG válido "
            f"({firma!r}). Verifica que el archivo no esté corrupto o mal renombrado."
        )

    # No hay contenido tabular que cargar: el dataframe va vacío a propósito.
    # Los metadatos (nombre, ruta, tamaño, fecha) los registra main.py en
    # archivo_metadato, igual que para cualquier otro tipo de archivo.
    return ResultadoTransformacion(
        dataframe=pd.DataFrame(),
        filas_validas=1 if es_dwg_valido else 0,
        filas_descartadas=0 if es_dwg_valido else 1,
        errores=errores,
    )
