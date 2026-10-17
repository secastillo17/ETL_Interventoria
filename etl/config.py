"""
Configuración central. Todo sale de variables de entorno, que en
GitHub Actions vienen de los Secrets del repositorio y en un computador
local vienen de un archivo .env (nunca se sube al repositorio).
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = BASE_DIR / "sql"

# --- Google Drive (OAuth con refresh token, sin navegador) -----------------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Carpeta raíz del repositorio documental en Drive y archivo de la tabla
# maestra. Se pueden dar por ID (recomendado) o dejar que se busquen por
# nombre.
DRIVE_RAIZ_ID = os.getenv("DRIVE_RAIZ_ID", "")
DRIVE_RAIZ_NOMBRE = os.getenv("DRIVE_RAIZ_NOMBRE", "PEI_REPOSITORIO")
TABLA_MAESTRA_ID = os.getenv("TABLA_MAESTRA_ID", "")
TABLA_MAESTRA_NOMBRE = os.getenv("TABLA_MAESTRA_NOMBRE", "TABLA_MAESTRA_PEI")

# Carpetas de control (hijas directas de la raíz)
CARPETA_MIGRACION = "00_MIGRACION"
CARPETA_ENTRADA = "01_ENTRADA"
CARPETA_REVISION_MIGRACION = "02_REVISION_MIGRACION"
CARPETA_RESPALDOS = "98_RESPALDOS"
CARPETA_RECHAZADOS = "99_RECHAZADOS"
CARPETA_POR_REVISAR = "99_POR_REVISAR"
CARPETA_ORIGINALES = "99_ORIGINALES_RECIBIDOS"  # originales de terceros ya copiados a lo oficial
CARPETA_HISTORICO = "_HISTORICO"  # dentro de cada carpeta de tipo

# --- Base de datos ----------------------------------------------------------
# Cadena de conexión de Neon, ej.
# postgresql://etl_escritura:****@ep-xxx.us-east-2.aws.neon.tech/pei?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- Límites ----------------------------------------------------------------
# Solo se descargan los archivos cuyo contenido se transforma en tablas.
# Los planos, PDF y fotos se catalogan con los metadatos que Drive ya
# entrega (md5Checksum, tamaño, fechas), sin bajar un solo byte.
EXTENSIONES_A_TRANSFORMAR = {".xlsx", ".xls", ".csv", ".txt"}
TAMANO_MAX_DESCARGA = int(os.getenv("TAMANO_MAX_DESCARGA_MB", "50")) * 1024 * 1024

# Enlace a la corrida de GitHub Actions, para dejarlo en la bitácora
RUN_URL = (
    f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}"
    f"/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
    if os.getenv("GITHUB_RUN_ID") else ""
)
