"""
Transformador de "cartera de nivelación" de tuberías: hojas con un
bloque de metadatos del levantamiento (LONGITUD, VISTA MAS, ALTURA
INSTRUMENTAL, BM, ANCHO/ANCHO ZANJA) seguido de una tabla de
progresivas con encabezado ADSA, CORTE, VISTA INTERMEDIA, COTA BATEA,
COTA TERRENO. Una hoja puede traer más de un tramo de tubería seguido
(cada uno reinicia su propio bloque de metadatos).

Cada tramo suele cerrar con un pie de resumen (PROMEDIO, VOLUMEN DE
CORTE, MATERIAL RELLENO SELECCIONADO, ARENA, ENTIVADO) que NO es una
progresiva real: hay que reconocerlo y saltarlo explícitamente, o se
cuela como basura en la tabla (una "progresiva" con id 'PROMEDIO', o un
tramo nuevo fantasma llamado 'VOLUMEN DE CORTE'). Los totales que traen
esas filas no se guardan por ahora: si hacen falta en el repositorio,
hay que agregar columnas nuevas y ampliar este transformador.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

# Etiquetas de pie de tramo conocidas: ni son progresivas reales, ni
# identificadores de tubería nueva. Se comparan con "empieza por" para
# tolerar variantes con espacios finales u otro texto pegado (ej. si
# algún archivo trae "PROMEDIO GENERAL" en vez de solo "PROMEDIO").
ETIQUETAS_PIE_DE_TRAMO = (
    "PROMEDIO", "VOLUMEN DE CORTE", "MATERIAL RELLENO SELECCIONADO",
    "ARENA", "ENTIVADO",
)


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


def _fila_contiene(fila, texto: str) -> bool:
    return any(texto in _normalizar(v) for v in fila)


def _es_pie_de_tramo(primera_celda: str) -> bool:
    return any(primera_celda.startswith(etiqueta) for etiqueta in ETIQUETAS_PIE_DE_TRAMO)


def detecta_patron_cartera(hoja_df: pd.DataFrame) -> bool:
    return any(_normalizar(hoja_df.iloc[i, 0]) == "ADSA" for i in range(len(hoja_df)))


def transformar_cartera(hoja_df: pd.DataFrame, nombre_archivo: str) -> ResultadoTransformacion:
    errores: List[str] = []
    filas = []

    metadatos = {"longitud": None, "vista_mas": None, "altura_instrumental": None,
                 "bm": None, "ancho": None}
    tuberia_actual = ""
    columnas_datos: Optional[List[str]] = None

    n = len(hoja_df)
    i = 0
    while i < n:
        fila = hoja_df.iloc[i]
        primera_celda = _normalizar(fila[0])

        # Bloque de metadatos del levantamiento (reinicia con cada tramo
        # nuevo). Se consumen AMBAS filas (encabezado + valores) de una
        # vez, avanzando el índice manualmente: si solo se salta la fila
        # de encabezado, la fila de valores (ej. "31.55, 1.56, 37.132,
        # 35.572, 0.8") queda para la siguiente vuelta del bucle y se
        # cuela como si fuera una progresiva real con datos inventados.
        if _fila_contiene(fila, "LONGITUD"):
            posiciones = {_normalizar(v): idx for idx, v in enumerate(fila)}
            fila_valores = hoja_df.iloc[i + 1] if i + 1 < n else None
            if fila_valores is not None:
                for clave_buscar, campo in [("LONGITUD", "longitud"), ("VISTA MAS", "vista_mas"),
                                             ("BM", "bm")]:
                    idx = posiciones.get(clave_buscar)
                    if idx is not None:
                        metadatos[campo] = _a_numero(fila_valores[idx])
                for clave, idx in posiciones.items():
                    if "ALTURA" in clave:
                        metadatos["altura_instrumental"] = _a_numero(fila_valores[idx])
                    if clave.startswith("ANCHO"):
                        metadatos["ancho"] = _a_numero(fila_valores[idx])
            i += 2 if fila_valores is not None else 1
            continue

        if primera_celda == "ADSA":
            columnas_datos = [_normalizar(c) for c in fila]
            i += 1
            continue

        if _es_pie_de_tramo(primera_celda):
            # Resumen de cierre del tramo (PROMEDIO/VOLUMEN DE CORTE/...):
            # no es una progresiva ni un tramo nuevo, se descarta.
            i += 1
            continue

        if columnas_datos and primera_celda:
            idx_corte = columnas_datos.index("CORTE") if "CORTE" in columnas_datos else None
            idx_vista = columnas_datos.index("VISTA INTERMEDIA") if "VISTA INTERMEDIA" in columnas_datos else None
            idx_batea = next((j for j, c in enumerate(columnas_datos) if "COTA BATEA" in c), None)
            idx_terreno = next((j for j, c in enumerate(columnas_datos) if "COTA TERRENO" in c), None)

            valores_extra = [
                fila[j] for j in (idx_corte, idx_vista, idx_batea, idx_terreno) if j is not None
            ]
            todos_vacios = all(_a_numero(v) is None for v in valores_extra)

            if todos_vacios:
                # Fila que solo trae el identificador del tramo (ej. "MHD29"), sin datos numéricos aún.
                tuberia_actual = primera_celda
                i += 1
                continue

            filas.append({
                "tuberia": tuberia_actual,
                "progresiva": primera_celda,
                "corte": _a_numero(fila[idx_corte]) if idx_corte is not None else None,
                "vista_intermedia": _a_numero(fila[idx_vista]) if idx_vista is not None else None,
                "cota_batea": _a_numero(fila[idx_batea]) if idx_batea is not None else None,
                "cota_terreno": _a_numero(fila[idx_terreno]) if idx_terreno is not None else None,
                "longitud": metadatos["longitud"],
                "vista_mas": metadatos["vista_mas"],
                "altura_instrumental": metadatos["altura_instrumental"],
                "bm": metadatos["bm"],
                "ancho": metadatos["ancho"],
            })

        i += 1

    if not filas:
        errores.append(f"{nombre_archivo}: no se encontraron filas de datos bajo un encabezado ADSA.")

    df = pd.DataFrame(filas)
    return ResultadoTransformacion(
        dataframe=df,
        filas_validas=len(df),
        filas_descartadas=0,
        errores=errores,
    )

