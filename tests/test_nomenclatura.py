from datetime import date

import pytest

from etl.nomenclatura import construir_nombre, validar_nombre

HOY = date(2026, 10, 30)


def test_nombre_valido_se_descompone():
    n = validar_nombre("P003-PEI-E02-F01-CAR-25-10-2026-01.txt", hoy=HOY)
    assert n.valido, n.motivos
    assert (n.proyecto, n.origen, n.etapa, n.frente, n.tipo) == ("P003", "PEI", "E02", "F01", "CAR")
    assert n.fecha == date(2026, 10, 25) and n.consecutivo == 1
    assert n.nombre_base == "P003-PEI-E02-F01-CAR-25-10-2026-01"


def test_general_zz_es_valido():
    assert validar_nombre("P003-PEI-ZZ-ZZ-INF-25-10-2026-01.pdf", hoy=HOY).valido


def test_extension_en_mayusculas_se_acepta():
    assert validar_nombre("P003-CON-E01-F01-PLA-25-10-2026-02.DWG", hoy=HOY).valido


@pytest.mark.parametrize("nombre, fragmento", [
    ("P003-PEI-E02-F01-CAR-25-10-2026.txt", "9 partes"),
    ("p003-pei-e02-f01-car-25-10-2026-01.txt", "mayúsculas"),
    ("P003-PEI-E02-F01-XYZ-25-10-2026-01.txt", "lista cerrada"),
    ("P003-PEI-E02-F01-CAR-31-02-2026-01.txt", "no existe"),
    ("P003-PEI-E02-F01-CAR-25-12-2026-01.txt", "futura"),
    ("P003-PEI-E2-F01-CAR-25-10-2026-01.txt", "etapa"),
    ("P3-PEI-E02-F01-CAR-25-10-2026-01.txt", "proyecto"),
    ("P003-PEI-E02-F01-FOT-25-10-2026-01.txt", "no corresponde al tipo"),
    ("P003-PEI-E02-F01-CAR-25-10-2026-00.txt", "empieza en 01"),
    ("P003-PEI-E02-F01-CAR-25-10-2026-01", "extensión"),
    ("ALEJANDRIA (1).CSV", "9 partes"),
    ("P003 PEI E02 F01 CAR 25 10 2026 01.txt", "espacios"),
])
def test_nombres_invalidos_explican_el_motivo(nombre, fragmento):
    n = validar_nombre(nombre, hoy=HOY)
    assert not n.valido
    assert any(fragmento in m for m in n.motivos), n.motivos


def test_fecha_antigua_es_aviso_no_rechazo():
    n = validar_nombre("P003-PEI-E02-F01-CAR-05-03-2026-01.txt", hoy=HOY)
    assert n.valido and any("invertidos" in a for a in n.avisos)


def test_construir_nombre_es_inverso_de_validar():
    nombre = construir_nombre("P001", "CON", "E01", "F01", "CMH", date(2026, 7, 14), 3, ".xlsx")
    assert nombre == "P001-CON-E01-F01-CMH-14-07-2026-03.xlsx"
    assert validar_nombre(nombre, hoy=HOY).valido
