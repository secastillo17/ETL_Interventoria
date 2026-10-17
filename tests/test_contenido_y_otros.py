import csv

import pytest

from etl.contenido import leer_contenido, revisar_coherencia
from etl.modos import carpetas, inventario_local, respaldo
from tests.conftest import DATOS_REALES, cartera_txt


def test_txt_de_autocad_va_a_mediciones(tmp_path):
    r = leer_contenido(cartera_txt(tmp_path / "x.txt"), "x.txt")
    assert [t for _, t in r.tablas] == ["mediciones_topograficas"] and r.filas_validas == 6
    assert revisar_coherencia("CAR", r) == []
    assert revisar_coherencia("PRE", r)


def test_inventario_marca_duplicados(tmp_path):
    (tmp_path / "d" / "sub").mkdir(parents=True)
    cartera_txt(tmp_path / "d" / "a.txt")
    cartera_txt(tmp_path / "d" / "sub" / "a copia.txt")
    salida = inventario_local.ejecutar(tmp_path / "d", tmp_path / "inv.csv")
    filas = list(csv.DictReader(open(salida, encoding="utf-8-sig"), delimiter=";"))
    assert len(filas) == 2 and {f["duplicados"] for f in filas} == {"1"}


def test_carpetas_desde_tabla_maestra(drive, db):
    carpetas.ejecutar(drive, db)
    rutas = {drive.ruta_de(m["id"]) for m in drive.items.values()}
    assert "P001 Alejandría/E02 Redes pluviales/PLA Plano" in rutas
    assert "P009 Mallorquín/ZZ General/INF Informe" in rutas
    assert not any(r.startswith("P009 Mallorquín/E") for r in rutas)
    assert "01_ENTRADA" in rutas
    antes = len(drive.items)
    carpetas.ejecutar(drive, db)               # idempotente
    assert len(drive.items) == antes


def test_respaldo_e_integridad(drive, db, tmp_path):
    from tests.test_diario import NOMBRE, _correr, _entrada
    drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), NOMBRE)
    _correr(drive, db)
    zip_path, c = respaldo.ejecutar(drive, db, salida_local=tmp_path / "resp")
    assert zip_path.exists() and c["errores"] == 0
    # Alguien cambia el archivo oficial por fuera del flujo
    oficial = [m for m in drive.items.values() if m["name"] == NOMBRE][0]
    oficial["md5Checksum"] = "0" * 32
    respaldo.ejecutar(drive, db, salida_local=tmp_path / "resp")
    ev = db.leer_sql("SELECT detalle FROM ctrl.evento WHERE accion = 'integridad'")
    assert list(ev.detalle) == ["MD5 DISTINTO"]


ESPERADO_REALES = {
    "POLIGONO5.TXT": {"mediciones_topograficas"},
    "alejandria calle 100  CARTERA.csv": {"mediciones_topograficas"},
    "TUBERIA PLUVIAL EMS.xlsx": {"cartera_nivelacion"},
    "EMS CANTIDADES ALEJANDRIA.xlsx": {"cantidades_abscisa"},
}


@pytest.mark.skipif(not DATOS_REALES.exists(), reason="sin carpeta de datos reales")
@pytest.mark.parametrize("nombre, tablas", ESPERADO_REALES.items())
def test_archivos_reales(nombre, tablas):
    ruta = DATOS_REALES / nombre
    if not ruta.exists():
        pytest.skip(nombre)
    r = leer_contenido(ruta, nombre)
    assert {t for _, t in r.tablas} == tablas and r.filas_validas > 0
