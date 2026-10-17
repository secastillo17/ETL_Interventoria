"""
Dispatcher de Excel: el cliente maneja varios tipos de Excel con
estructuras distintas, y varios de esos archivos tienen más de una
hoja (ej. "CARTERAS", "RESUMEN", "Hoja1"). Este módulo recorre TODAS
las hojas de cada archivo y prueba, en orden, los patrones conocidos:

  1. MH (control de cotas de pozos)          -> control_mh
  2. Coordenadas con encabezado (PUNTOS,ESTE,NORTE,COTA...) -> mediciones_topograficas
  3. Cartera de nivelación de tuberías       -> cartera_nivelacion
  4. Presupuesto/cantidades jerárquico       -> presupuesto_cantidades
  5. Cantidades por abscisa (corte/lleno)    -> cantidades_abscisa
  6. Coordenadas SIN encabezado (última opción, la más genérica) -> mediciones_topograficas
  7. Cantidades ejecutadas (formato simple)  -> cantidades_ejecutadas

Si ninguna hoja de un archivo coincide con nada, se cataloga sin
transformar contenido (igual que un DWG), para no perder evidencia
mientras se construye el transformador específico para ese formato.

Los resultados de todas las hojas que coincidan con el MISMO patrón se
combinan en un solo dataframe. Si un archivo tiene hojas de patrones
DISTINTOS, se cargan todas, cada una a su propia tabla (por eso el
resultado es una lista de (resultado, tabla_destino), no uno solo).
"""

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple
import pandas as pd

from etl.transform.mh_transformer import _es_fila_encabezado_mh, transformar_mh_desde_df
from etl.transform.excel_transformer import transformar_excel_cantidades
from etl.transform.coordenadas_excel_transformer import detecta_patron_coordenadas, transformar_coordenadas
from etl.transform.cartera_nivelacion_transformer import detecta_patron_cartera, transformar_cartera
from etl.transform.presupuesto_transformer import detecta_patron_presupuesto, transformar_presupuesto
from etl.transform.cantidades_abscisa_transformer import (
    detecta_patron_cantidades_abscisa, transformar_cantidades_abscisa,
)
from etl.transform.coordenadas_sin_encabezado_transformer import (
    detecta_patron_coordenadas_sin_encabezado, transformar_coordenadas_sin_encabezado,
)


@dataclass
class ResultadoTransformacion:
    dataframe: pd.DataFrame
    filas_validas: int
    filas_descartadas: int
    errores: List[str]


def transformar_excel(path: Path) -> List[Tuple[ResultadoTransformacion, Optional[str]]]:
    try:
        nombres_hojas = pd.ExcelFile(path).sheet_names
    except Exception as exc:  # noqa: BLE001
        resultado = ResultadoTransformacion(
            dataframe=pd.DataFrame(), filas_validas=0, filas_descartadas=1,
            errores=[f"{path.name}: no se pudo abrir el archivo Excel ({exc})."],
        )
        return [(resultado, None)]

    # Agrupa los dataframes de todas las hojas por tabla destino, para
    # combinarlos en un solo resultado por tabla al final.
    por_tabla: dict = {}
    errores_generales: List[str] = []
    alguna_hoja_coincidio = False

    for nombre_hoja in nombres_hojas:
        hoja_sin_encabezado = pd.read_excel(path, sheet_name=nombre_hoja, header=None)
        etiqueta = f"{path.name}::{nombre_hoja}"

        if any(_es_fila_encabezado_mh(hoja_sin_encabezado.iloc[i]) for i in range(len(hoja_sin_encabezado))):
            resultado = transformar_mh_desde_df(hoja_sin_encabezado, etiqueta)
            tabla = "control_mh"
        elif detecta_patron_cartera(hoja_sin_encabezado):
            resultado = transformar_cartera(hoja_sin_encabezado, etiqueta)
            tabla = "cartera_nivelacion"
        elif detecta_patron_presupuesto(hoja_sin_encabezado):
            resultado = transformar_presupuesto(hoja_sin_encabezado, etiqueta)
            tabla = "presupuesto_cantidades"
        elif detecta_patron_cantidades_abscisa(hoja_sin_encabezado):
            resultado = transformar_cantidades_abscisa(hoja_sin_encabezado, etiqueta)
            tabla = "cantidades_abscisa"
        else:
            hoja_con_encabezado = pd.read_excel(path, sheet_name=nombre_hoja)
            if detecta_patron_coordenadas(hoja_con_encabezado):
                resultado = transformar_coordenadas(hoja_con_encabezado, etiqueta)
                tabla = "mediciones_topograficas"
            elif detecta_patron_coordenadas_sin_encabezado(hoja_sin_encabezado):
                # Última opción, la más genérica: coordenadas sin ningún
                # texto identificador (ni "MH", ni "ADSA", ni encabezado
                # PUNTOS/ESTE/NORTE). Va al final para no confundir una
                # tabla de otro tipo que también tenga números grandes.
                resultado = transformar_coordenadas_sin_encabezado(hoja_sin_encabezado, etiqueta)
                tabla = "mediciones_topograficas"
            else:
                continue  # esta hoja no coincide con ningún patrón conocido

        alguna_hoja_coincidio = True
        if resultado.filas_validas > 0:
            por_tabla.setdefault(tabla, []).append(resultado.dataframe)
        errores_generales.extend(resultado.errores)

    if por_tabla:
        salidas = []
        for tabla, dataframes in por_tabla.items():
            df_final = pd.concat(dataframes, ignore_index=True)
            salidas.append((
                ResultadoTransformacion(
                    dataframe=df_final, filas_validas=len(df_final),
                    filas_descartadas=0, errores=errores_generales,
                ),
                tabla,
            ))
        return salidas

    if not alguna_hoja_coincidio:
        # Último intento: patrón simple de cantidades ejecutadas (una sola hoja plana)
        resultado_cantidades = transformar_excel_cantidades(path)
        if resultado_cantidades.filas_validas > 0:
            return [(resultado_cantidades, "cantidades_ejecutadas")]

    resultado = ResultadoTransformacion(
        dataframe=pd.DataFrame(), filas_validas=1, filas_descartadas=0,
        errores=[
            f"{path.name}: ninguna hoja ({', '.join(nombres_hojas)}) coincide con un "
            "patrón conocido (MH, coordenadas, cartera, presupuesto o cantidades). "
            "Se cataloga sin transformar contenido."
        ],
    )
    return [(resultado, None)]
