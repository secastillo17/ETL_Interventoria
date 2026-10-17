"""Modo diario de punta a punta con un Drive en memoria y Postgres real."""

from datetime import date

from etl import config
from etl.modos import diario
from tests.conftest import CONTRATISTA, DIRECTOR, TOPOGRAFO, TOPOGRAFO2, cartera_txt

HOY = date(2026, 10, 30)
NOMBRE = "P001-PEI-E01-F01-CAR-14-10-2026-01.txt"


def _entrada(drive):
    return drive.asegurar_carpeta(config.CARPETA_ENTRADA, drive.raiz_id)


def _correr(drive, db):
    return diario.ejecutar(drive, db, hoy=HOY)


def test_archivo_valido_queda_oficial_y_carga_contenido(drive, db, tmp_path):
    fid = drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), NOMBRE, dueno=TOPOGRAFO)
    c = _correr(drive, db)
    assert c["oficializados"] == 1 and c["errores"] == 0
    oficial = [m for m in drive.items.values() if m["name"] == NOMBRE and m["owners"][0]["me"]][0]
    assert drive.ruta_de(oficial["id"]) == f"P001 Alejandría/E01 Redes sanitarias/CAR Cartera de campo/{NOMBRE}"
    # Lo subió otra persona: lo oficial es una copia a nombre de la empresa
    assert oficial["owners"][0]["me"] and oficial["id"] != fid
    assert drive.ruta_de(fid).startswith(config.CARPETA_ORIGINALES)
    fila = db.leer_sql("SELECT * FROM reporte.v_buscador").iloc[0]
    assert fila["documento"] == NOMBRE[:-4] and fila["version"] == 1 and fila["contratista_frente"] == "Obras Dos"  # a cargo desde julio de 2026
    assert db.leer_sql("SELECT COUNT(*) n FROM tecnico.mediciones_topograficas").n[0] == 6
    assert db.leer_sql("SELECT estado FROM ctrl.ejecucion").estado[0] == "exitosa"


def test_nombre_invalido_va_a_rechazados_con_motivo(drive, db, tmp_path):
    fid = drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), "POLIGONO5.TXT", dueno=TOPOGRAFO)
    c = _correr(drive, db)
    assert c["rechazados"] == 1
    assert drive.ruta_de(fid) == f"{config.CARPETA_RECHAZADOS}/POLIGONO5.TXT"
    assert "9 partes" in drive.items[fid]["description"]
    r = db.leer_sql("SELECT * FROM reporte.v_rechazos").iloc[0]
    assert r["subido_por"] == TOPOGRAFO


def test_origen_que_no_corresponde_se_rechaza(drive, db, tmp_path):
    nombre = "P001-OTR-E01-F01-CNT-14-03-2026-01.xlsx"
    fid = drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), nombre, dueno=CONTRATISTA)
    _correr(drive, db)
    assert "era CON" in drive.items[fid]["description"]


def test_misma_persona_crea_version_y_la_anterior_va_a_historico(drive, db, tmp_path):
    drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), NOMBRE, dueno=TOPOGRAFO)
    _correr(drive, db)
    drive.subir_como(cartera_txt(tmp_path / "b.txt", desplazamiento=0.5), _entrada(drive), NOMBRE, dueno=TOPOGRAFO)
    c = _correr(drive, db)
    assert c["versionados"] == 1
    v = db.leer_sql("SELECT version, estado FROM reporte.v_versiones ORDER BY version")
    assert list(v.estado) == ["REEMPLAZADO", "VIGENTE"]
    historico = [m for m in drive.items.values() if m["name"].endswith("_V01.txt")][0]
    assert "/_HISTORICO/" in drive.ruta_de(historico["id"])
    # Las vistas técnicas solo muestran la versión vigente
    assert db.leer_sql("SELECT COUNT(*) n FROM reporte.v_buscador").n[0] == 1


def test_otra_persona_con_el_mismo_nombre_queda_por_revisar(drive, db, tmp_path):
    drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), NOMBRE, dueno=TOPOGRAFO)
    _correr(drive, db)
    fid = drive.subir_como(cartera_txt(tmp_path / "b.txt", 0.7), _entrada(drive), NOMBRE, dueno=TOPOGRAFO2)
    c = _correr(drive, db)
    assert c["por_revisar"] == 1
    assert drive.ruta_de(fid).startswith(config.CARPETA_POR_REVISAR)
    # El director sí puede reemplazarlo
    drive.subir_como(cartera_txt(tmp_path / "c.txt", 0.9), _entrada(drive), NOMBRE, dueno=DIRECTOR)
    assert _correr(drive, db)["versionados"] == 1


def test_contenido_identico_es_duplicado(drive, db, tmp_path):
    ruta = cartera_txt(tmp_path / "a.txt")
    drive.subir_como(ruta, _entrada(drive), NOMBRE, dueno=TOPOGRAFO)
    _correr(drive, db)
    drive.subir_como(ruta, _entrada(drive), NOMBRE.replace("-01.txt", "-02.txt"), dueno=TOPOGRAFO)
    c = _correr(drive, db)
    assert c["duplicados"] == 1
    assert db.leer_sql("SELECT * FROM reporte.v_indicadores").documentos_oficiales[0] == 1


def test_plano_no_se_descarga(drive, db, tmp_path, monkeypatch):
    plano = tmp_path / "x.dwg"
    plano.write_bytes(b"AC1032" + b"\0" * 100)
    drive.subir_como(plano, _entrada(drive), "P001-PEI-ZZ-ZZ-PLA-14-10-2026-01.dwg", dueno=TOPOGRAFO)

    def prohibido(*a, **k):
        raise AssertionError("no debería descargar un plano")
    monkeypatch.setattr(drive, "descargar", prohibido)
    assert _correr(drive, db)["oficializados"] == 1


def test_indicadores_y_panel(drive, db, tmp_path):
    drive.subir_como(cartera_txt(tmp_path / "a.txt"), _entrada(drive), NOMBRE, dueno=TOPOGRAFO)
    drive.subir_como(cartera_txt(tmp_path / "b.txt", 2), _entrada(drive), "mal nombre.txt", dueno=TOPOGRAFO)
    _correr(drive, db)
    ind = db.leer_sql("SELECT * FROM reporte.v_indicadores").iloc[0]
    assert ind["documentos_oficiales"] == 1
    mensual = db.leer_sql("SELECT * FROM reporte.v_cumplimiento_mensual").iloc[0]
    assert mensual["recibidos"] == 2 and float(mensual["pct_conformidad"]) == 50.0
    for vista in ("v_inventario", "v_ejecuciones", "v_control_mh", "v_cantidades_abscisa", "v_cartera_nivelacion"):
        db.leer_sql(f"SELECT * FROM reporte.{vista}")
