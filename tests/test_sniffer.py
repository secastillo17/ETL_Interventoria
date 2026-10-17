"""
Prueba del sniffer de contenido: los dos casos reales que motivaron su
creación — un .xlsx guardado con extensión .csv, y un archivo sin
extensión (reenvío de WhatsApp) que en realidad es una cartera de texto.
"""

from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.sniffer import clasificar_archivo


def test_xlsx_con_extension_csv_se_reclasifica_como_excel(tmp_path):
    archivo = tmp_path / "reporte.csv"  # extensión mentirosa
    pd.DataFrame({"a": [1, 2]}).to_excel(archivo, index=False)  # contenido real: xlsx

    tipo, aviso = clasificar_archivo(archivo)

    assert tipo == "excel"
    assert aviso is not None and "mal renombrado" in aviso


def test_archivo_sin_extension_se_clasifica_por_contenido(tmp_path):
    archivo = tmp_path / "DOC-20260707-WA0000_"  # sin extensión, como WhatsApp
    archivo.write_text("1,D1,1710940.907,916898.705,57.602\n2,D2,1710917.223,916745.348,48.315\n")

    tipo, aviso = clasificar_archivo(archivo)

    assert tipo == "txt"
    assert aviso is not None and "sin extensión" in aviso


def test_archivo_con_extension_correcta_no_genera_aviso(tmp_path):
    archivo = tmp_path / "cartera.txt"
    archivo.write_text("1,D1,1710940.907,916898.705,57.602\n")

    tipo, aviso = clasificar_archivo(archivo)

    assert tipo == "txt"
    assert aviso is None
