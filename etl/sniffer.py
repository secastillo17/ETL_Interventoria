"""
Clasificación por CONTENIDO real del archivo, como respaldo/verificación
de la clasificación por extensión (extract/clasificador.py).

Dos patrones reales del cliente que la sola extensión no detecta:

  1. Archivos que llegan con la extensión equivocada. Ej: un .xlsx
     exportado/guardado con extensión ".CSV" — sigue siendo un ZIP con
     estructura de Excel por dentro (todo .xlsx es un ZIP), pero
     confiar en la extensión lo mandaría al transformador de CSV, que
     fallaría al intentar leerlo como texto plano delimitado.

  2. Archivos reenviados por WhatsApp u otros medios que llegan SIN
     extensión (ej. "DOC-20260707-WA0000_"). La extensión no existe,
     así que no hay nada que mapear — hay que mirar el contenido para
     saber qué es.

Este módulo no reemplaza a clasificador.py: se usa como verificación
posterior en extract/local_extractor.py y extract/google_drive_extractor.py,
una vez que el archivo ya está disponible en disco para leer sus bytes.
"""

from pathlib import Path
from typing import Optional
import zipfile

FIRMAS_DWG_VALIDAS = (b"AC10", b"AC15", b"AC18", b"AC21", b"AC24", b"AC32")


def _es_xlsx_real(path: Path) -> bool:
    """Todo .xlsx es un ZIP; para no confundirlo con cualquier otro ZIP,
    se confirma que además tenga la carpeta interna 'xl/' que solo traen
    los libros de Excel."""
    try:
        with zipfile.ZipFile(path) as z:
            return any(nombre.startswith("xl/") for nombre in z.namelist())
    except zipfile.BadZipFile:
        return False


def _parece_cartera_delimitada(muestra_texto: str) -> Optional[str]:
    """Distingue entre los dos formatos de texto delimitado que maneja
    el cliente, por su separador: ';' (formato regional, como
    alejandria_calle_100_CARTERA.csv) vs ',' (formato AutoCAD, como
    POLIGONO5.TXT o los archivos reenviados por WhatsApp sin extensión)."""
    primera_linea = next((l for l in muestra_texto.splitlines() if l.strip()), "")
    if primera_linea.count(";") >= 2:
        return "csv"
    if len(primera_linea.split(",")) == 5:
        return "txt"
    return None


def clasificar_por_contenido(path: Path) -> Optional[str]:
    """Devuelve el tipo de fuente según el contenido real del archivo,
    o None si no se reconoce ningún patrón conocido."""
    with open(path, "rb") as f:
        cabecera = f.read(8)

    if cabecera[:4] == b"PK\x03\x04" and _es_xlsx_real(path):
        return "excel"
    if cabecera[:4] in FIRMAS_DWG_VALIDAS:
        return "dwg"
    if cabecera[:4] == b"%PDF":
        return "pdf"
    if cabecera[:4] == b"\x89PNG":
        return "images"
    if cabecera[:3] == b"\xff\xd8\xff":
        return "images"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            muestra = f.read(2000)
    except Exception:  # noqa: BLE001
        return None

    return _parece_cartera_delimitada(muestra)


def clasificar_archivo(path: Path, nombre_original: Optional[str] = None):
    """Combina extensión + contenido y devuelve (tipo, aviso_opcional).

    - Si la extensión y el contenido coinciden (o el contenido no es
      concluyente), se usa el tipo por extensión sin aviso.
    - Si no hay extensión reconocible (archivo sin extensión, típico de
      reenvíos por WhatsApp), se clasifica por contenido y se avisa.
    - Si la extensión y el contenido NO coinciden (archivo mal
      renombrado), se confía en el contenido -es lo que de verdad se
      puede leer- y se avisa del desajuste para que quede en el log.
    """
    from etl.clasificador import clasificar_por_extension

    nombre_para_extension = Path(nombre_original) if nombre_original else path
    tipo_extension = clasificar_por_extension(nombre_para_extension)
    tipo_contenido = clasificar_por_contenido(path)

    nombre_mostrar = nombre_original or path.name

    if tipo_extension is None:
        if tipo_contenido is None:
            return None, None
        return tipo_contenido, (
            f"{nombre_mostrar}: sin extensión reconocible; clasificado por "
            f"su contenido real como '{tipo_contenido}'."
        )

    if tipo_contenido is not None and tipo_contenido != tipo_extension:
        return tipo_contenido, (
            f"{nombre_mostrar}: la extensión sugiere '{tipo_extension}' pero "
            f"el contenido real es '{tipo_contenido}' (archivo probablemente "
            f"mal renombrado); se procesa como '{tipo_contenido}'."
        )

    return tipo_extension, None
