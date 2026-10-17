"""
Transformador de hojas de "cantidades por abscisa" (corte/lleno), patrón
real observado en archivos tipo EMS_CANTIDADES_*: una tabla en cascada,
NO plana, con esta forma:

    Fila de bloques   :  AREA | CORTE | ...    | AREA | LLENO |  ...
    Fila de subcolumna:       | AREA  | AREA PROMEDIO | VOLUMEN (M3) | ...
    (2 filas en blanco)
    Fila 1 (por abscisa): 'k0+470', <area corte>, None, None, <area lleno>, ...
    Fila 2 (misma absc.): None,      None, <area prom corte>, <vol corte>, ...

Cada abscisa ocupa 2 filas: la primera trae el valor puntual de área en
cada grupo (CORTE, LLENO, LLENO SELECCIONADO, SUBBASE); la segunda trae
el área promedio y el volumen del mismo tramo. Además, la tabla suele
venir "duplicada" en dos bloques de columnas lado a lado que comparten
la misma abscisa (uno para CORTE/LLENO, otro para LLENO SELECCIONADO/
SUBBASE) — por eso hay más de una columna que repite la abscisa.

Esta es la estructura menos estandarizada de todas las que maneja el
pipeline: si el archivo real de la empresa varía el nombre exacto de un
grupo (ej. "SUBASE" vs "SUBBASE"), ajusta `_normalizar_grupo` en vez de
reescribir el transformador completo.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import re
import pandas as pd

PATRON_ABSCISA = re.compile(r"^[Kk]\d+\+\d+$")


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


def _normalizar_grupo(texto: str) -> Optional[str]:
    """Mapea el texto de la fila de bloques a un nombre de grupo estable,
    tolerando variaciones de redacción vistas en archivos reales."""
    if "SELECCIONADO" in texto:
        return "lleno_sel"
    # "SUDBASE" es un typo real visto en los archivos del cliente
    # (debería decir "SUBBASE"/"SUBASE"); se tolera junto con las
    # variantes correctas para no depender de que lo corrijan.
    if "SUBASE" in texto or "SUBBASE" in texto or "SUDBASE" in texto:
        return "subbase"
    if texto == "CORTE":
        return "corte"
    if texto == "LLENO":
        return "lleno"
    return None


def _normalizar_subetiqueta(texto: str) -> Optional[str]:
    if "PROMEDIO" in texto:
        return "area_promedio"
    if "VOLUMEN" in texto:
        return "volumen"
    if texto == "AREA":
        return "area"
    return None


def detecta_patron_cantidades_abscisa(hoja_df: pd.DataFrame) -> bool:
    coincidencias = sum(
        1 for i in range(len(hoja_df)) for j in range(hoja_df.shape[1])
        if PATRON_ABSCISA.match(_normalizar(hoja_df.iat[i, j]))
    )
    return coincidencias >= 2


def _mapear_columnas(hoja_df: pd.DataFrame) -> dict:
    """Devuelve {indice_columna: 'area_corte'|'volumen_lleno'|...} recorriendo
    la fila de bloques y la fila de subcolumnas. Se reinicia el 'grupo
    actual' cada vez que se pasa por una columna que contiene una abscisa,
    porque ahí siempre empieza un bloque nuevo en los archivos reales."""
    n = len(hoja_df)
    ncols = hoja_df.shape[1]

    fila_subcolumna_idx = next(
        (i for i in range(n) if any("PROMEDIO" in _normalizar(v) for v in hoja_df.iloc[i])),
        None,
    )
    if fila_subcolumna_idx is None or fila_subcolumna_idx == 0:
        return {}
    fila_grupo_idx = fila_subcolumna_idx - 1

    columnas_abscisa = {
        j for j in range(ncols)
        if any(PATRON_ABSCISA.match(_normalizar(hoja_df.iat[i, j])) for i in range(n))
    }

    mapa = {}
    grupo_actual = None
    for c in range(ncols):
        if c in columnas_abscisa:
            grupo_actual = None
            continue
        texto_grupo = _normalizar(hoja_df.iat[fila_grupo_idx, c])
        if texto_grupo:
            nuevo_grupo = _normalizar_grupo(texto_grupo)
            if nuevo_grupo:
                grupo_actual = nuevo_grupo
        if grupo_actual is None:
            continue
        sub = _normalizar_subetiqueta(_normalizar(hoja_df.iat[fila_subcolumna_idx, c]))
        if sub is None:
            continue
        campo = f"area_{grupo_actual}" if sub == "area" else f"{sub}_{grupo_actual}"
        mapa[c] = campo

    return mapa, fila_subcolumna_idx, list(columnas_abscisa)


CAMPOS_TABLA = [
    "abscisa", "area_corte", "area_promedio_corte", "volumen_corte",
    "area_lleno", "area_promedio_lleno", "volumen_lleno",
    "area_lleno_sel", "area_promedio_lleno_sel", "volumen_lleno_sel",
    "area_subbase", "area_promedio_subbase", "volumen_subbase",
]


def transformar_cantidades_abscisa(hoja_df: pd.DataFrame, nombre_archivo: str) -> ResultadoTransformacion:
    errores: List[str] = []
    resultado_mapa = _mapear_columnas(hoja_df)
    if not resultado_mapa or not resultado_mapa[0]:
        errores.append(f"{nombre_archivo}: no se pudo ubicar la fila de subcolumnas (AREA PROMEDIO/VOLUMEN).")
        return ResultadoTransformacion(pd.DataFrame(), 0, 0, errores)

    mapa_columnas, fila_subcolumna_idx, columnas_abscisa = resultado_mapa
    col_abscisa_principal = min(columnas_abscisa)

    n = len(hoja_df)
    filas = []
    i = fila_subcolumna_idx + 1
    while i < n:
        valor_abscisa = _normalizar(hoja_df.iat[i, col_abscisa_principal])
        if not PATRON_ABSCISA.match(valor_abscisa):
            i += 1
            continue

        fila1 = hoja_df.iloc[i]
        fila2 = hoja_df.iloc[i + 1] if i + 1 < n else None

        registro = {campo: None for campo in CAMPOS_TABLA}
        registro["abscisa"] = valor_abscisa

        for col, campo in mapa_columnas.items():
            valor = _a_numero(fila1[col])
            if valor is None and fila2 is not None:
                valor = _a_numero(fila2[col])
            registro[campo] = valor

        filas.append(registro)
        i += 2  # cada abscisa ocupa 2 filas (área puntual + área promedio/volumen)

    if not filas:
        errores.append(f"{nombre_archivo}: no se encontraron filas de abscisas (patrón k0+xxx) con datos.")

    df = pd.DataFrame(filas, columns=CAMPOS_TABLA)
    return ResultadoTransformacion(
        dataframe=df, filas_validas=len(df), filas_descartadas=0, errores=errores,
    )
