"""
Transformador de Excel de control de cotas de MH (pozos de inspección),
patrón real observado en varios archivos del cliente: bloques "MH
SANITARIOS" / "MH PLUVIALES" con encabezado MH, C.BATEA, C.ACTUAL,
C.TAPA DISEÑO (a veces "C.DISEÑO TAPA"), y a veces columnas extra sin
encabezado (estado de la tapa, código de proyecto) o "BATEA DISEÑO".

No todos los Excel del cliente siguen este patrón (hay otros tipos:
cantidades, tuberías, etc. con su propio formato). Este transformador
solo procesa el archivo si detecta al menos una fila de encabezado
"MH" — si no la encuentra, el dispatcher (excel_dispatcher.py) cae a
otro transformador.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

ESTADOS_TAPA_CONOCIDOS = {"SIN TAPA", "CON TAPA", "SIN CONSTRUIR"}
NOMBRES_C_TAPA_DISENO = {"C.TAPA DISEÑO", "C.DISEÑO TAPA"}


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def _normalizar(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip().upper()


def _a_numero(valor) -> Optional[float]:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def _fila_tiene_titulo_seccion(fila) -> Optional[str]:
    """Busca en TODAS las celdas de la fila un título tipo 'MH SANITARIOS'."""
    for valor in fila:
        texto = _normalizar(valor)
        if texto and texto != "MH" and ("SANITARIOS" in texto or "PLUVIALES" in texto):
            return texto
    return None


def _es_fila_encabezado_mh(fila) -> bool:
    return _normalizar(fila[0]) == "MH"


def detecta_patron_mh(path: Path) -> bool:
    df_crudo = pd.read_excel(path, header=None)
    return any(_es_fila_encabezado_mh(df_crudo.iloc[i]) for i in range(len(df_crudo)))


def transformar_mh(path: Path) -> ResultadoTransformacion:
    df_crudo = pd.read_excel(path, header=None)
    return transformar_mh_desde_df(df_crudo, path.name)


def transformar_mh_desde_df(df_crudo: pd.DataFrame, nombre_archivo: str) -> ResultadoTransformacion:
    errores: List[str] = []
    filas = []
    seccion_actual = ""
    columnas_actuales: Optional[List[str]] = None

    for i in range(len(df_crudo)):
        fila = df_crudo.iloc[i]

        if _es_fila_encabezado_mh(fila):
            columnas_actuales = [_normalizar(c) for c in fila]
            continue

        titulo = _fila_tiene_titulo_seccion(fila)
        if titulo:
            seccion_actual = titulo
            continue

        primera_celda = _normalizar(fila[0])
        if columnas_actuales and primera_celda:
            registro = {
                "seccion": seccion_actual,
                "mh": primera_celda,
                "c_batea": None,
                "c_actual": None,
                "c_tapa_diseno": None,
                "batea_diseno": None,
                "estado_tapa": None,
                "codigo_proyecto": None,
            }

            for idx, nombre_columna in enumerate(columnas_actuales):
                valor = fila[idx]
                if nombre_columna == "C.BATEA":
                    registro["c_batea"] = _a_numero(valor)
                elif nombre_columna == "C.ACTUAL":
                    registro["c_actual"] = _a_numero(valor)
                elif nombre_columna in NOMBRES_C_TAPA_DISENO:
                    registro["c_tapa_diseno"] = _a_numero(valor)
                elif nombre_columna == "BATEA DISEÑO":
                    registro["batea_diseno"] = _a_numero(valor)
                elif nombre_columna == "" and idx > 0:
                    # Columna sin encabezado: se infiere el significado por el contenido.
                    texto = _normalizar(valor)
                    if texto in ESTADOS_TAPA_CONOCIDOS:
                        registro["estado_tapa"] = texto
                    elif texto:
                        registro["codigo_proyecto"] = texto

            filas.append(registro)

    if not filas:
        errores.append(f"{nombre_archivo}: no se encontraron filas de datos bajo un encabezado MH.")

    df = pd.DataFrame(filas)

    return ResultadoTransformacion(
        dataframe=df,
        filas_validas=len(df),
        filas_descartadas=0,
        errores=errores,
    )
