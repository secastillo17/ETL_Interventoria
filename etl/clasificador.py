"""
Clasifica un archivo por su extensión. El cliente no organiza los
archivos por tipo en la nube — todo llega revuelto en un mismo lugar —
así que la ETL debe reconocer el tipo sola en vez de depender de en
qué carpeta vive el archivo.
"""

from pathlib import Path
from typing import Optional

EXTENSION_A_TIPO = {
    ".xlsx": "excel",
    ".xls": "excel",
    ".csv": "csv",
    ".txt": "txt",
    ".dwg": "dwg",
    ".pdf": "pdf",
    ".jpg": "images",
    ".jpeg": "images",
    ".png": "images",
}


def clasificar_por_extension(path: Path) -> Optional[str]:
    """Devuelve el tipo_fuente según la extensión, o None si no se reconoce."""
    return EXTENSION_A_TIPO.get(path.suffix.lower())
