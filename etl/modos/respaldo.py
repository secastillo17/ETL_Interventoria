"""
Modo RESPALDO (semanal):
  1. Verifica la integridad de lo oficial: cada archivo VIGENTE de la base
     debe seguir en Drive con el mismo md5. Si alguien lo borró o lo
     cambió por fuera del flujo, queda como evento 'integridad'.
  2. Exporta las tablas de la base a CSV, junto con la tabla maestra y el
     inventario de Drive, en un .zip que se guarda en 98_RESPALDOS y
     también como artefacto de GitHub Actions (copia fuera de Drive).
"""

from __future__ import annotations

import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from etl import config
from etl.db import BaseDatos
from etl.drive import Drive
from etl.modos.comun import Carpetas, cargar_tabla_maestra, carpeta_temporal, ejecucion

log = logging.getLogger("etl")

TABLAS = ["ctrl.proyecto", "ctrl.etapa", "ctrl.contratista", "ctrl.frente_asignacion",
          "ctrl.tipo_documento", "ctrl.documento", "ctrl.archivo", "ctrl.evento",
          "ctrl.ejecucion", "ctrl.migracion_item",
          "tecnico.cantidades_ejecutadas", "tecnico.mediciones_topograficas", "tecnico.control_mh",
          "tecnico.cartera_nivelacion", "tecnico.presupuesto_cantidades", "tecnico.cantidades_abscisa"]


def ejecutar(drive: Optional[Drive] = None, db: Optional[BaseDatos] = None,
             salida_local: Optional[Path] = None):
    drive = drive or Drive()
    db = db or BaseDatos()
    with ejecucion(db, "respaldo") as (ej_id, c), carpeta_temporal() as tmp:
        tmp = Path(tmp)
        raiz = drive.raiz()
        tm = cargar_tabla_maestra(drive, raiz, tmp)
        carpetas = Carpetas(drive, raiz, tm)

        # 1. Integridad
        vigentes = db.leer_sql("SELECT id, drive_id, nombre_drive, md5 FROM ctrl.archivo WHERE estado = 'VIGENTE'")
        inventario = []
        for _, f in vigentes.iterrows():
            c["revisados"] += 1
            try:
                a = drive.obtener(f["drive_id"])
                estado = "OK"
                if a.get("md5Checksum") and f["md5"] and a["md5Checksum"] != f["md5"]:
                    estado = "MD5 DISTINTO"
                if a.get("trashed"):
                    estado = "EN PAPELERA"
            except Exception:  # noqa: BLE001
                a, estado = {}, "NO ENCONTRADO"
            inventario.append({"archivo_id": f["id"], "drive_id": f["drive_id"], "nombre": f["nombre_drive"],
                               "md5_base": f["md5"], "md5_drive": a.get("md5Checksum"),
                               "tamano": a.get("size"), "estado": estado})
            if estado != "OK":
                c["errores"] += 1
                db.evento(ej_id, "integridad", f["drive_id"], f["nombre_drive"], estado)
                log.warning("  INTEGRIDAD %s: %s", estado, f["nombre_drive"])

        # 2. Respaldo
        sello = datetime.now().strftime("%Y-%m-%d_%H%M")
        zip_path = (salida_local or tmp) / f"respaldo_pei_{sello}.zip"
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for t in TABLAS:
                df = db.leer_sql(f"SELECT * FROM {t}")
                z.writestr(f"base/{t}.csv", df.to_csv(index=False))
                c["filas_cargadas"] += len(df)
            z.writestr("drive/inventario_integridad.csv", pd.DataFrame(inventario).to_csv(index=False))
            z.write(tmp / "tabla_maestra.xlsx", "drive/tabla_maestra.xlsx")
        subido = drive.subir(zip_path, carpetas.control(config.CARPETA_RESPALDOS), zip_path.name,
                             mime="application/zip")
        db.evento(ej_id, "respaldo", subido["id"], zip_path.name,
                  f"{c['filas_cargadas']} filas; integridad: {c['revisados'] - c['errores']}/{c['revisados']} OK")
        log.info("Respaldo %s subido a 98_RESPALDOS", zip_path.name)
        return zip_path, c
