"""Piezas compartidas por los modos de la ETL."""

from __future__ import annotations

import logging
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from etl import config
from etl.drive import HOJA_MIME, Drive
from etl.nomenclatura import GENERAL, TIPOS
from etl.tabla_maestra import TablaMaestra

log = logging.getLogger("etl")


def cargar_tabla_maestra(drive: Drive, raiz_id: str, carpeta_tmp: Path) -> TablaMaestra:
    if config.TABLA_MAESTRA_ID:
        archivo = drive.obtener(config.TABLA_MAESTRA_ID)
    else:
        archivo = (drive.buscar_por_nombre(config.TABLA_MAESTRA_NOMBRE, raiz_id, HOJA_MIME)
                   or drive.buscar_por_nombre(config.TABLA_MAESTRA_NOMBRE + ".xlsx", raiz_id))
    if not archivo:
        raise RuntimeError(
            f"No se encontró la tabla maestra '{config.TABLA_MAESTRA_NOMBRE}' en la carpeta raíz. "
            "Genérela con `python -m etl plantilla` y súbala a Drive como Hoja de cálculo.")
    ruta = drive.exportar_xlsx(archivo, carpeta_tmp / "tabla_maestra.xlsx")
    tm = TablaMaestra.desde_excel(ruta)
    for p in tm.problemas:
        log.warning("Tabla maestra: %s", p)
    if not tm.proyectos:
        raise RuntimeError("La tabla maestra no tiene proyectos registrados.")
    return tm


class Carpetas:
    """Resuelve (y crea si hace falta) las carpetas del repositorio:
    raíz / P003 Nombre / E02 Nombre / CAR Cartera de campo."""

    def __init__(self, drive: Drive, raiz_id: str, tm: TablaMaestra):
        self.d, self.raiz, self.tm = drive, raiz_id, tm

    def control(self, nombre: str) -> str:
        return self.d.asegurar_carpeta(nombre, self.raiz)

    def proyecto(self, p: str) -> str:
        nombre = f"{p} {self.tm.nombre_proyecto(p)}".strip()
        return self.d.asegurar_carpeta(nombre, self.raiz, prefijo=p)

    def etapa(self, p: str, e: str) -> str:
        nombre = f"{e} {self.tm.nombre_etapa(p, e) or ('General' if e == GENERAL else '')}".strip()
        return self.d.asegurar_carpeta(nombre, self.proyecto(p), prefijo=e)

    def tipo(self, p: str, e: str, t: str) -> str:
        return self.d.asegurar_carpeta(f"{t} {TIPOS.get(t, '')}".strip(), self.etapa(p, e), prefijo=t)

    def historico(self, carpeta_tipo_id: str) -> str:
        return self.d.asegurar_carpeta(config.CARPETA_HISTORICO, carpeta_tipo_id)


@contextmanager
def ejecucion(db, modo: str):
    """Abre una fila en ctrl.ejecucion y la cierra con el resultado, también
    cuando la corrida falla. Entrega (id, contadores)."""
    ej_id = db.iniciar_ejecucion(modo)
    contadores = Counter()
    try:
        yield ej_id, contadores
    except Exception as exc:
        db.cerrar_ejecucion(ej_id, contadores, "fallida", f"{type(exc).__name__}: {exc}")
        raise
    estado = "exitosa" if contadores["errores"] == 0 else "con_errores"
    db.cerrar_ejecucion(ej_id, contadores, estado, resumen(contadores))
    log.info("Ejecución %s %s: %s", ej_id, estado, resumen(contadores))


def resumen(c: Counter) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(c.items()) if v)


def carpeta_temporal() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix="pei_etl_")
