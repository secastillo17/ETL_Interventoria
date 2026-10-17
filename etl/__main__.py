"""
Punto de entrada único de la ETL. Un solo programa con varios modos:

  python -m etl diario                     procesa 01_ENTRADA (lo corre Actions cada día)
  python -m etl migracion-propuesta        genera la hoja de revisión de 00_MIGRACION
  python -m etl migracion-aplicar [--hoja ID]   aplica la hoja revisada y aprobada
  python -m etl carpetas                   crea la estructura de carpetas desde la tabla maestra
  python -m etl respaldo [--salida DIR]    verifica integridad y respalda la base
  python -m etl bd-inicializar [--permisos]     crea esquemas, tablas y vistas en Neon
  python -m etl plantilla [--salida RUTA]  genera la tabla maestra vacía (.xlsx)
  python -m etl validar NOMBRE [--tabla RUTA.xlsx]   revisa un nombre sin tocar nada
  python -m etl inventario CARPETA --salida RUTA.csv  inventario de un disco o USB (local)
  python -m etl leer CARPETA               prueba los transformadores con archivos locales
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(prog="python -m etl", description="ETL de gobierno de datos PEI")
    sub = ap.add_subparsers(dest="modo", required=True)
    sub.add_parser("diario")
    sub.add_parser("migracion-propuesta")
    p = sub.add_parser("migracion-aplicar")
    p.add_argument("--hoja", help="ID de la hoja de revisión (por defecto la más reciente)")
    sub.add_parser("carpetas")
    p = sub.add_parser("respaldo")
    p.add_argument("--salida", type=Path, help="carpeta local donde dejar también el .zip")
    p = sub.add_parser("bd-inicializar")
    p.add_argument("--permisos", action="store_true", help="aplicar también 03_permisos.sql")
    p = sub.add_parser("plantilla")
    p.add_argument("--salida", type=Path, default=Path("TABLA_MAESTRA_PEI.xlsx"))
    p = sub.add_parser("validar")
    p.add_argument("nombres", nargs="+")
    p.add_argument("--tabla", type=Path, help="tabla maestra local (.xlsx) para validar también contra ella")
    p = sub.add_parser("inventario")
    p.add_argument("carpeta", type=Path)
    p.add_argument("--salida", type=Path, default=Path("inventario.csv"))
    p = sub.add_parser("leer")
    p.add_argument("carpeta", type=Path)
    a = ap.parse_args(argv)

    if a.modo == "diario":
        from etl.modos import diario
        c = diario.ejecutar()
        return 1 if c["errores"] else 0
    if a.modo == "migracion-propuesta":
        from etl.modos import migracion
        migracion.proponer()
    elif a.modo == "migracion-aplicar":
        from etl.modos import migracion
        res = migracion.aplicar(hoja_id=a.hoja)
        return 1 if (res["resultado"] == "ERROR").any() else 0
    elif a.modo == "carpetas":
        from etl.modos import carpetas
        carpetas.ejecutar()
    elif a.modo == "respaldo":
        from etl.modos import respaldo
        _, c = respaldo.ejecutar(salida_local=a.salida)
        if c["errores"]:
            print(f"ATENCIÓN: {c['errores']} archivo(s) oficiales con problemas de integridad (ver ctrl.evento)")
            return 1
    elif a.modo == "bd-inicializar":
        from etl.db import BaseDatos
        BaseDatos().inicializar(incluir_permisos=a.permisos)
        print("Esquemas ctrl, tecnico y reporte listos.")
    elif a.modo == "plantilla":
        from etl.tabla_maestra import generar_plantilla
        print(f"Plantilla creada en {generar_plantilla(a.salida)}")
    elif a.modo == "validar":
        from etl.nomenclatura import validar_nombre
        tm = None
        if a.tabla:
            from etl.tabla_maestra import TablaMaestra
            tm = TablaMaestra.desde_excel(a.tabla)
        malos = 0
        for nombre in a.nombres:
            n = validar_nombre(nombre)
            motivos, avisos = list(n.motivos), list(n.avisos)
            if n.valido and tm:
                m2, a2, contratista = tm.validar(n)
                motivos += m2
                avisos += a2
            estado = "VÁLIDO" if not motivos else "RECHAZADO"
            malos += bool(motivos)
            print(f"{estado:9} {nombre}")
            for m in motivos:
                print(f"          - {m}")
            for av in avisos:
                print(f"          (aviso) {av}")
        return 1 if malos else 0
    elif a.modo == "inventario":
        from etl.modos import inventario_local
        inventario_local.ejecutar(a.carpeta, a.salida)
    elif a.modo == "leer":
        from etl.contenido import leer_contenido
        for ruta in sorted(x for x in a.carpeta.rglob("*") if x.is_file()):
            r = leer_contenido(ruta, ruta.name)
            tablas = ", ".join(f"{t}({len(df)})" for df, t in r.tablas) or "-"
            print(f"[{r.tipo_detectado or '?':6}] {ruta.name}: {tablas}")
            for av in r.avisos:
                print(f"         aviso: {av}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
