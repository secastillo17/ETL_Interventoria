"""
Fixtures compartidas.

Las pruebas que usan base de datos necesitan TEST_DATABASE_URL (en GitHub
Actions la da un contenedor de Postgres 16; en local puede ser un Postgres
propio o una rama de pruebas de Neon). Si no está, esas pruebas se omiten.
Nunca apunte TEST_DATABASE_URL a la base de producción: las pruebas borran
los esquemas.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import text

from etl.tabla_maestra import HOJAS, TablaMaestra

DATOS_REALES = Path(os.getenv("PEI_DATOS_REALES", Path(__file__).parent / "datos_reales"))

DIRECTOR = "director@pei.com"
TOPOGRAFO = "topografo@pei.com"
TOPOGRAFO2 = "topografo2@pei.com"
CONTRATISTA = "obra@constructora.com"


def escribir_tabla_maestra(ruta: Path) -> Path:
    filas = {
        "PROYECTOS": [["P001", "Alejandría", "ACTIVO", "2025-01-01", "", "alejandria, ems"],
                      ["P002", "Calle 100", "ACTIVO", "2025-06-01", "", "calle 100"],
                      ["P009", "Mallorquín", "TERMINADO", "2022-01-01", "2024-12-31", "mallorquin"]],
        "ETAPAS": [["P001", "E01", "Redes sanitarias", "2025-01-01", "", "K0+000", "K0+500",
                    1711000, 1711500, 918400, 918800, "sanitaria, mz11"],
                   ["P001", "E02", "Redes pluviales", "2025-01-01", "", "K0+500", "K1+200",
                    "", "", "", "", "pluvial"],
                   ["P002", "E01", "Tramo único", "2025-06-01", "", "", "", "", "", "", "", ""]],
        "FRENTES": [["P001", "E01", "F01", "Manzana 11", "CON", "2025-01-01", "2026-06-30"],
                    ["P001", "E01", "F01", "Manzana 11", "OTR", "2026-07-01", ""],
                    ["P001", "E02", "F01", "Canal", "CON", "2025-01-01", ""],
                    ["P002", "E01", "F01", "Vía", "OTR", "2025-06-01", ""]],
        "CONTRATISTAS": [["CON", "Constructora Uno", CONTRATISTA], ["OTR", "Obras Dos", "obras@dos.com"]],
        "PERSONAS": [[DIRECTOR, "Director", "director", "PEI"], [TOPOGRAFO, "Topógrafo 1", "topografo", "PEI"],
                     [TOPOGRAFO2, "Topógrafo 2", "topografo", "PEI"]],
    }
    wb = Workbook()
    wb.remove(wb.active)
    for hoja, columnas in HOJAS.items():
        ws = wb.create_sheet(hoja)
        ws.append(columnas)
        for f in filas[hoja]:
            ws.append(f)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta


@pytest.fixture
def ruta_tabla(tmp_path) -> Path:
    return escribir_tabla_maestra(tmp_path / "TABLA_MAESTRA_PEI.xlsx")


@pytest.fixture
def tabla(ruta_tabla) -> TablaMaestra:
    return TablaMaestra.desde_excel(ruta_tabla)


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no está definida")
    from etl.db import BaseDatos
    base = BaseDatos(url)
    with base.engine.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS reporte, tecnico, ctrl CASCADE"))
    base.inicializar()
    return base


@pytest.fixture
def drive(tmp_path, ruta_tabla):
    from tests.fake_drive import FakeDrive
    d = FakeDrive(tmp_path / "drive")
    d.subir_como(ruta_tabla, d.raiz_id, "TABLA_MAESTRA_PEI.xlsx")
    return d


def cartera_txt(ruta: Path, desplazamiento: float = 0.0, puntos: int = 6) -> Path:
    """Cartera en el formato que exporta AutoCAD (punto,desc,norte,este,cota)."""
    lineas = [f"{i},D{i},{1711100 + i * 3.5 + desplazamiento:.3f},{918600 + i * 2.1:.3f},{50 + i * 0.2:.3f}"
              for i in range(1, puntos + 1)]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta
