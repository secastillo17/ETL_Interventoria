"""
Drive en memoria para las pruebas. Implementa las mismas operaciones que
etl.drive.Drive (listar, mover, copiar, descargar...) sobre archivos
locales, para probar los modos de la ETL sin cuenta de Google.
"""

from __future__ import annotations

import hashlib
import itertools
import shutil
from pathlib import Path
from typing import Optional

from etl.drive import CARPETA_MIME, HOJA_MIME, XLSX_MIME, Drive


class FakeDrive(Drive):
    def __init__(self, base: Path, yo: str = "empresa@pei.com"):
        self.s = None
        self._cache_carpetas = {}
        self._yo = yo
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)
        self.items = {}
        self._ids = itertools.count(1)
        self.raiz_id = self._nuevo("PEI_REPOSITORIO", CARPETA_MIME, None)

    # ------------------------------------------------------------ internos
    def _nuevo(self, nombre, mime, padre, ruta_local: Optional[Path] = None, dueno=None) -> str:
        fid = f"id{next(self._ids):04d}"
        meta = {"id": fid, "name": nombre, "mimeType": mime, "parents": [padre] if padre else [],
                "createdTime": f"2026-10-01T00:00:{len(self.items) % 60:02d}Z",
                "modifiedTime": "2026-10-01T00:00:00Z", "webViewLink": f"https://drive.fake/{fid}",
                "owners": [{"emailAddress": dueno or self._yo, "me": (dueno or self._yo) == self._yo}],
                "lastModifyingUser": {"emailAddress": dueno or self._yo}, "appProperties": {}}
        if ruta_local is not None:
            destino = self.base / fid
            shutil.copy(ruta_local, destino)
            datos = destino.read_bytes()
            meta.update(size=str(len(datos)), md5Checksum=hashlib.md5(datos).hexdigest(),  # noqa: S324
                        _local=destino)
        self.items[fid] = meta
        return fid

    def _publico(self, meta):
        return {k: v for k, v in meta.items() if not k.startswith("_")}

    # ------------------------------------------------------- para las pruebas
    def subir_como(self, ruta_local: Path, carpeta_id: str, nombre: Optional[str] = None,
                   dueno: Optional[str] = None) -> str:
        return self._nuevo(nombre or ruta_local.name, "application/octet-stream", carpeta_id,
                           ruta_local, dueno)

    def hijos(self, padre_id):
        return [self._publico(m) for m in self.items.values() if padre_id in m["parents"]]

    def ruta_de(self, fid) -> str:
        partes, m = [], self.items[fid]
        while m["parents"]:
            partes.append(m["name"])
            m = self.items[m["parents"][0]]
        return "/".join(reversed(partes))

    # ------------------------------------------------------------- interfaz
    def raiz(self):
        return self.raiz_id

    def buscar_por_nombre(self, nombre, padre_id=None, mime=None):
        for m in self.items.values():
            if m["name"] == nombre and (not padre_id or padre_id in m["parents"]) and (not mime or m["mimeType"] == mime):
                return self._publico(m)
        return None

    def hijos_carpetas(self, padre_id):
        return [h for h in self.hijos(padre_id) if h["mimeType"] == CARPETA_MIME]

    def asegurar_carpeta(self, nombre, padre_id, prefijo=None):
        for c in self.hijos_carpetas(padre_id):
            if (prefijo and (c["name"] == prefijo or c["name"].startswith(prefijo + " "))) or c["name"] == nombre:
                return c["id"]
        return self._nuevo(nombre, CARPETA_MIME, padre_id)

    def listar_archivos(self, carpeta_id, recursivo=True, ruta="", excluir=()):
        salida = []
        for h in self.hijos(carpeta_id):
            if h["mimeType"] == CARPETA_MIME:
                if recursivo and h["name"] not in excluir:
                    salida += self.listar_archivos(h["id"], True, f"{ruta}{h['name']}/", excluir)
            else:
                h["ruta"] = ruta
                salida.append(h)
        return salida

    def obtener(self, file_id):
        return self._publico(self.items[file_id])

    def mover(self, archivo, destino_id, nuevo_nombre=None, app_properties=None, descripcion=None):
        m = self.items[archivo["id"]]
        m["parents"] = [destino_id]
        if nuevo_nombre:
            m["name"] = nuevo_nombre
        if app_properties:
            m["appProperties"].update({k: str(v) for k, v in app_properties.items()})
        if descripcion is not None:
            m["description"] = descripcion
        return self._publico(m)

    def copiar(self, archivo, destino_id, nombre, app_properties=None):
        origen = self.items[archivo["id"]]
        fid = self._nuevo(nombre, origen["mimeType"], destino_id, origen.get("_local"))
        if app_properties:
            self.items[fid]["appProperties"].update({k: str(v) for k, v in app_properties.items()})
        return self._publico(self.items[fid])

    def renombrar(self, archivo, nombre, app_properties=None):
        return self.mover(archivo, self.items[archivo["id"]]["parents"][0], nombre, app_properties)

    def descargar(self, archivo, destino: Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.items[archivo["id"]]["_local"], destino)
        return destino

    def exportar_xlsx(self, archivo, destino: Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.items[archivo["id"]]["_local"], destino)
        return destino

    def subir(self, ruta, padre_id, nombre=None, como_hoja=False, reemplazar=None, mime=None):
        fid = self._nuevo(nombre or ruta.name, HOJA_MIME if como_hoja else (mime or XLSX_MIME), padre_id, ruta)
        return self._publico(self.items[fid])
