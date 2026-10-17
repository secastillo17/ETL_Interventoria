"""
Modo CARPETAS: crea en Drive la estructura oficial a partir de la tabla
maestra. Se puede correr las veces que se quiera: solo crea lo que falta.

    PEI_REPOSITORIO/
      00_MIGRACION/  01_ENTRADA/  02_REVISION_MIGRACION/  98_RESPALDOS/
      99_RECHAZADOS/  99_POR_REVISAR/  99_ORIGINALES_RECIBIDOS/
      P003 Vía Calle 45/
        E01 Tramo norte/
          CAR Cartera de campo/  CMH Control de pozos (MH)/  ...
        ZZ General/
          PLA Plano/  INF Informe/ ...

Los proyectos TERMINADO solo reciben la carpeta ZZ General, porque la
migración los clasifica hasta proyecto.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from etl import config
from etl.db import BaseDatos
from etl.drive import Drive
from etl.modos.comun import Carpetas, cargar_tabla_maestra, carpeta_temporal, ejecucion
from etl.nomenclatura import GENERAL, TIPOS

log = logging.getLogger("etl")

CONTROL = [config.CARPETA_MIGRACION, config.CARPETA_ENTRADA, config.CARPETA_REVISION_MIGRACION,
           config.CARPETA_RESPALDOS, config.CARPETA_RECHAZADOS, config.CARPETA_POR_REVISAR,
           config.CARPETA_ORIGINALES]


def ejecutar(drive: Optional[Drive] = None, db: Optional[BaseDatos] = None):
    drive = drive or Drive()
    db = db or BaseDatos()
    with ejecucion(db, "carpetas") as (ej_id, c), carpeta_temporal() as tmp:
        raiz = drive.raiz()
        tm = cargar_tabla_maestra(drive, raiz, Path(tmp))
        db.sincronizar_tabla_maestra(tm)
        carpetas = Carpetas(drive, raiz, tm)
        for nombre in CONTROL:
            carpetas.control(nombre)
        for codigo, p in sorted(tm.proyectos.items()):
            etapas = [GENERAL]
            if p.estado != "TERMINADO":
                etapas = sorted(e for (pp, e) in tm.etapas if pp == codigo) + [GENERAL]
            for e in etapas:
                for t in TIPOS:
                    carpetas.tipo(codigo, e, t)
                    c["revisados"] += 1
            log.info("  %s: %d etapa(s) x %d tipos", codigo, len(etapas), len(TIPOS))
        db.evento(ej_id, "carpetas", None, None, f"{c['revisados']} carpetas de tipo verificadas")
    return c
