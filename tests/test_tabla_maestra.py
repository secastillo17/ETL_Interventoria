from datetime import date

from etl.nomenclatura import validar_nombre
from etl.tabla_maestra import abscisa_a_metros, generar_plantilla, TablaMaestra

HOY = date(2026, 10, 30)


def _v(tabla, nombre):
    n = validar_nombre(nombre, hoy=HOY)
    assert n.valido, n.motivos
    return tabla.validar(n)


def test_carga_hojas(tabla):
    assert set(tabla.proyectos) == {"P001", "P002", "P009"}
    assert tabla.etapas[("P001", "E01")].abscisa_fin == 500
    assert tabla.origen_de_correo("OBRA@constructora.com") == "CON"
    assert not tabla.problemas


def test_contratista_segun_fecha(tabla):
    assert tabla.contratista_en("P001", "E01", "F01", date(2026, 3, 1)) == "CON"
    assert tabla.contratista_en("P001", "E01", "F01", date(2026, 8, 1)) == "OTR"


def test_pei_siempre_puede_producir(tabla):
    motivos, _, contratista = _v(tabla, "P001-PEI-E01-F01-CAR-14-08-2026-01.txt")
    assert motivos == [] and contratista == "OTR"


def test_origen_debe_ser_el_contratista_del_frente_en_esa_fecha(tabla):
    assert _v(tabla, "P001-CON-E01-F01-CNT-14-03-2026-01.xlsx")[0] == []
    motivos, _, _ = _v(tabla, "P001-CON-E01-F01-CNT-14-08-2026-01.xlsx")
    assert "era OTR" in motivos[0]


def test_frente_y_etapa_no_registrados(tabla):
    assert "frente no registrado" in _v(tabla, "P001-PEI-E01-F07-CAR-14-08-2026-01.txt")[0][0]
    assert "etapa P001-E09" in _v(tabla, "P001-PEI-E09-F01-CAR-14-08-2026-01.txt")[0][0]
    assert "proyecto P777" in _v(tabla, "P777-PEI-E01-F01-CAR-14-08-2026-01.txt")[0][0]
    assert "ZZ" in _v(tabla, "P001-PEI-ZZ-F01-INF-14-08-2026-01.pdf")[0][0]


def test_contratista_en_frente_general(tabla):
    assert _v(tabla, "P001-CON-E02-ZZ-INF-14-08-2026-01.pdf")[0] == []
    assert _v(tabla, "P002-CON-ZZ-ZZ-INF-14-08-2026-01.pdf")[0] != []


def test_abscisas():
    assert abscisa_a_metros("K0+470") == 470
    assert abscisa_a_metros("k1+020,5") == 1020.5
    assert abscisa_a_metros(None) is None


def test_plantilla_se_puede_leer(tmp_path):
    t = TablaMaestra.desde_excel(generar_plantilla(tmp_path / "p.xlsx"))
    assert "P003" in t.proyectos and not t.problemas
