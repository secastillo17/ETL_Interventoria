"""
Lectura del contenido de los archivos tabulares (Excel, CSV, TXT) con los
transformadores de la v2.4. Devuelve los dataframes listos para cargar
en el esquema tecnico, sin tocar la base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from etl.sniffer import clasificar_archivo
from etl.transform.csv_transformer import transformar_csv
from etl.transform.excel_dispatcher import transformar_excel
from etl.transform.txt_transformer import transformar_txt_mediciones

# Qué tipos del estándar son coherentes con cada tabla técnica
TIPOS_COHERENTES = {
    "control_mh": {"CMH"},
    "cartera_nivelacion": {"CAR", "MED"},
    "mediciones_topograficas": {"CAR", "MED"},
    "presupuesto_cantidades": {"PRE", "CNT", "PAC"},
    "cantidades_abscisa": {"CNT", "MED", "PAC"},
    "cantidades_ejecutadas": {"CNT", "PAC", "SOP"},
}


@dataclass
class ContenidoLeido:
    tipo_detectado: Optional[str] = None             # excel | csv | txt | ...
    tablas: List[Tuple[pd.DataFrame, str]] = field(default_factory=list)
    filas_validas: int = 0
    filas_descartadas: int = 0
    avisos: List[str] = field(default_factory=list)


def leer_contenido(ruta: Path, nombre_original: str) -> ContenidoLeido:
    r = ContenidoLeido()
    tipo, aviso = clasificar_archivo(ruta, nombre_original=nombre_original)
    r.tipo_detectado = tipo
    if aviso:
        r.avisos.append(aviso)
    if tipo == "excel":
        pares = transformar_excel(ruta)
    elif tipo == "txt":
        pares = [(transformar_txt_mediciones(ruta), "mediciones_topograficas")]
    elif tipo == "csv":
        pares = [(transformar_csv(ruta), "mediciones_topograficas")]
    else:
        return r
    for resultado, tabla in pares:
        r.filas_validas += resultado.filas_validas if tabla else 0
        r.filas_descartadas += resultado.filas_descartadas
        r.avisos.extend(resultado.errores)
        if tabla and resultado.dataframe is not None and not resultado.dataframe.empty:
            r.tablas.append((resultado.dataframe, tabla))
    return r


def revisar_coherencia(tipo_declarado: str, contenido: ContenidoLeido) -> List[str]:
    avisos = []
    for _, tabla in contenido.tablas:
        esperados = TIPOS_COHERENTES.get(tabla, set())
        if esperados and tipo_declarado not in esperados:
            avisos.append(f"el nombre dice {tipo_declarado} pero el contenido parece {tabla} "
                          f"(se esperaría {'/'.join(sorted(esperados))})")
    return avisos
