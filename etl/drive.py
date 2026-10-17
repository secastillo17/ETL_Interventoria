"""
Cliente de Google Drive para la ETL.

Diferencias con el extractor de la v2.4:
  - Se autentica con un refresh token guardado como secreto de GitHub, sin
    abrir navegador ni guardar archivos .pickle. Así corre en Actions.
  - Tiene permiso de escritura (scope drive) porque la ETL mueve, copia,
    renombra y crea carpetas.
  - No descarga archivos para saber si cambiaron: usa el md5Checksum que
    Drive ya calcula. Mover y copiar se hacen en los servidores de Google,
    así que un plano de 3 GB se mueve en segundos sin pasar por Actions.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from etl import config

CARPETA_MIME = "application/vnd.google-apps.folder"
HOJA_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CAMPOS_ARCHIVO = ("id, name, mimeType, md5Checksum, size, createdTime, modifiedTime, "
                  "parents, webViewLink, appProperties, description, trashed, "
                  "owners(emailAddress, me), lastModifyingUser(emailAddress)")


def _q(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("'", "\\'")


class Drive:
    def __init__(self, service=None):
        if service is None:
            service = self._construir_servicio()
        self.s = service
        self._cache_carpetas: Dict[tuple, str] = {}
        self._yo: Optional[str] = None

    @staticmethod
    def _construir_servicio():
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        faltan = [n for n in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
                  if not getattr(config, n)]
        if faltan:
            raise RuntimeError(
                "Faltan credenciales de Google: " + ", ".join(faltan) +
                ". En GitHub van en Settings > Secrets and variables > Actions (ver docs/credenciales.md).")
        creds = Credentials(
            token=None,
            refresh_token=config.GOOGLE_REFRESH_TOKEN,
            client_id=config.GOOGLE_CLIENT_ID,
            client_secret=config.GOOGLE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=config.SCOPES,
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    @staticmethod
    def _ejecutar(peticion, intentos: int = 4):
        espera = 2
        for i in range(intentos):
            try:
                return peticion.execute(num_retries=2)
            except Exception as exc:  # noqa: BLE001
                codigo = getattr(getattr(exc, "resp", None), "status", None)
                if codigo in (429, 500, 502, 503) and i < intentos - 1:
                    time.sleep(espera)
                    espera *= 2
                    continue
                raise

    # ------------------------------------------------------------ cuenta
    def yo(self) -> str:
        if self._yo is None:
            info = self._ejecutar(self.s.about().get(fields="user(emailAddress)"))
            self._yo = info["user"]["emailAddress"].lower()
        return self._yo

    # ---------------------------------------------------------- carpetas
    def buscar_por_nombre(self, nombre: str, padre_id: Optional[str] = None,
                          mime: Optional[str] = None) -> Optional[dict]:
        q = [f"name = '{_q(nombre)}'", "trashed = false"]
        if padre_id:
            q.append(f"'{padre_id}' in parents")
        if mime:
            q.append(f"mimeType = '{mime}'")
        r = self._ejecutar(self.s.files().list(q=" and ".join(q), fields=f"files({CAMPOS_ARCHIVO})",
                                               pageSize=10))
        archivos = r.get("files", [])
        return archivos[0] if archivos else None

    def hijos_carpetas(self, padre_id: str) -> List[dict]:
        return list(self._listar_directo(padre_id, solo_carpetas=True))

    def asegurar_carpeta(self, nombre: str, padre_id: str, prefijo: Optional[str] = None) -> str:
        """Devuelve el id de la carpeta y la crea si no existe. Con
        `prefijo` (ej. 'P003') busca por el código, para que el director
        pueda corregir el nombre visible sin que la ETL cree otra."""
        clave = (padre_id, prefijo or nombre)
        if clave in self._cache_carpetas:
            return self._cache_carpetas[clave]
        existente = None
        if prefijo:
            for c in self.hijos_carpetas(padre_id):
                if c["name"] == prefijo or c["name"].startswith(prefijo + " "):
                    existente = c
                    break
        else:
            existente = self.buscar_por_nombre(nombre, padre_id, CARPETA_MIME)
        if existente:
            cid = existente["id"]
        else:
            cid = self._ejecutar(self.s.files().create(
                body={"name": nombre, "mimeType": CARPETA_MIME, "parents": [padre_id]},
                fields="id"))["id"]
        self._cache_carpetas[clave] = cid
        return cid

    def raiz(self) -> str:
        if config.DRIVE_RAIZ_ID:
            return config.DRIVE_RAIZ_ID
        c = self.buscar_por_nombre(config.DRIVE_RAIZ_NOMBRE, mime=CARPETA_MIME)
        if not c:
            raise RuntimeError(f"No se encontró la carpeta raíz '{config.DRIVE_RAIZ_NOMBRE}' en Drive.")
        return c["id"]

    # ---------------------------------------------------------- listados
    def _listar_directo(self, carpeta_id: str, solo_carpetas: bool = False) -> Iterable[dict]:
        q = f"'{carpeta_id}' in parents and trashed = false"
        if solo_carpetas:
            q += f" and mimeType = '{CARPETA_MIME}'"
        token = None
        while True:
            r = self._ejecutar(self.s.files().list(
                q=q, fields=f"nextPageToken, files({CAMPOS_ARCHIVO})",
                pageSize=1000, pageToken=token))
            yield from r.get("files", [])
            token = r.get("nextPageToken")
            if not token:
                break

    def listar_archivos(self, carpeta_id: str, recursivo: bool = True, ruta: str = "",
                        excluir: Iterable[str] = ()) -> List[dict]:
        """Archivos (no carpetas) bajo una carpeta. Cada uno lleva 'ruta',
        la ruta de carpetas desde donde se empezó a listar."""
        salida = []
        for item in self._listar_directo(carpeta_id):
            if item["mimeType"] == CARPETA_MIME:
                if recursivo and item["name"] not in excluir:
                    salida.extend(self.listar_archivos(item["id"], True, f"{ruta}{item['name']}/", excluir))
            else:
                item["ruta"] = ruta
                salida.append(item)
        return salida

    def obtener(self, file_id: str) -> dict:
        return self._ejecutar(self.s.files().get(fileId=file_id, fields=CAMPOS_ARCHIVO))

    # ------------------------------------------------- operaciones de escritura
    def mover(self, archivo: dict, destino_id: str, nuevo_nombre: Optional[str] = None,
              app_properties: Optional[dict] = None, descripcion: Optional[str] = None) -> dict:
        body = {}
        if descripcion is not None:
            body["description"] = descripcion
        if nuevo_nombre:
            body["name"] = nuevo_nombre
        if app_properties:
            body["appProperties"] = {k: str(v) for k, v in app_properties.items()}
        anteriores = ",".join(archivo.get("parents", []))
        return self._ejecutar(self.s.files().update(
            fileId=archivo["id"], body=body, addParents=destino_id,
            removeParents=anteriores, fields=CAMPOS_ARCHIVO))

    def copiar(self, archivo: dict, destino_id: str, nombre: str,
               app_properties: Optional[dict] = None) -> dict:
        body = {"name": nombre, "parents": [destino_id]}
        if app_properties:
            body["appProperties"] = {k: str(v) for k, v in app_properties.items()}
        return self._ejecutar(self.s.files().copy(fileId=archivo["id"], body=body, fields=CAMPOS_ARCHIVO))

    def renombrar(self, archivo: dict, nombre: str, app_properties: Optional[dict] = None) -> dict:
        body = {"name": nombre}
        if app_properties:
            body["appProperties"] = {k: str(v) for k, v in app_properties.items()}
        return self._ejecutar(self.s.files().update(fileId=archivo["id"], body=body, fields=CAMPOS_ARCHIVO))

    def es_mio(self, archivo: dict) -> bool:
        return any(o.get("me") for o in archivo.get("owners", []))

    def oficializar(self, archivo: dict, destino_id: str, nombre: str,
                    app_properties: dict, carpeta_originales_id: Optional[str] = None) -> dict:
        """Lleva un archivo a su carpeta oficial. Si la cuenta de la empresa
        es dueña, lo mueve. Si lo subió otra persona, hace una copia (que
        queda a nombre de la empresa) y aparta el original, para que lo
        oficial nunca dependa de la cuenta personal de nadie."""
        if self.es_mio(archivo):
            return self.mover(archivo, destino_id, nombre, app_properties)
        copia = self.copiar(archivo, destino_id, nombre, app_properties)
        if carpeta_originales_id:
            try:
                self.mover(archivo, carpeta_originales_id)
            except Exception:  # noqa: BLE001  (sin permiso para moverlo: queda donde está)
                pass
        return copia

    # --------------------------------------------------- descargas y subidas
    def descargar(self, archivo: dict, destino: Path) -> Path:
        from googleapiclient.http import MediaIoBaseDownload
        destino.parent.mkdir(parents=True, exist_ok=True)
        peticion = self.s.files().get_media(fileId=archivo["id"])
        with io.FileIO(destino, "wb") as fh:
            d = MediaIoBaseDownload(fh, peticion, chunksize=10 * 1024 * 1024)
            listo = False
            while not listo:
                _, listo = d.next_chunk(num_retries=3)
        return destino

    def exportar_xlsx(self, archivo: dict, destino: Path) -> Path:
        """Descarga una Hoja de cálculo de Google como .xlsx (o el .xlsx tal
        cual si ya lo es)."""
        if archivo["mimeType"] != HOJA_MIME:
            return self.descargar(archivo, destino)
        from googleapiclient.http import MediaIoBaseDownload
        destino.parent.mkdir(parents=True, exist_ok=True)
        peticion = self.s.files().export_media(fileId=archivo["id"], mimeType=XLSX_MIME)
        with io.FileIO(destino, "wb") as fh:
            d = MediaIoBaseDownload(fh, peticion)
            listo = False
            while not listo:
                _, listo = d.next_chunk(num_retries=3)
        return destino

    def subir(self, ruta: Path, padre_id: str, nombre: Optional[str] = None,
              como_hoja: bool = False, reemplazar: Optional[dict] = None,
              mime: Optional[str] = None) -> dict:
        """Sube un archivo local. Con como_hoja=True un .xlsx se convierte en
        Hoja de cálculo de Google (conserva las listas desplegables)."""
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(str(ruta), mimetype=mime or XLSX_MIME, resumable=True)
        if reemplazar:
            return self._ejecutar(self.s.files().update(
                fileId=reemplazar["id"], media_body=media, fields=CAMPOS_ARCHIVO))
        body = {"name": nombre or ruta.name, "parents": [padre_id]}
        if como_hoja:
            body["mimeType"] = HOJA_MIME
        return self._ejecutar(self.s.files().create(body=body, media_body=media, fields=CAMPOS_ARCHIVO))
