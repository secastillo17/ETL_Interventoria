"""
Modo DIARIO: procesa lo que el equipo subió a 01_ENTRADA.

Por cada archivo:
  1. Valida el nombre contra el estándar (forma, lista cerrada, fechas).
  2. Valida proyecto, etapa, frente y origen contra la tabla maestra.
  3. Revisa si el contenido ya existe en lo oficial (md5 de Drive).
  4. Si el documento es nuevo lo oficializa; si ya existe y lo sube la
     misma persona (o el director) crea la versión siguiente; si lo sube
     otra persona lo deja en 99_POR_REVISAR.
  5. Si es Excel, CSV o TXT, lee el contenido y lo carga en el esquema
     tecnico. Los planos, PDF y fotos no se descargan.
Todo queda en ctrl.archivo y ctrl.evento.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from etl import config
from etl.contenido import leer_contenido, revisar_coherencia
from etl.db import BaseDatos, quien_subio
from etl.drive import Drive
from etl.modos.comun import Carpetas, cargar_tabla_maestra, carpeta_temporal, ejecucion
from etl.nomenclatura import validar_nombre

log = logging.getLogger("etl")
ROLES_QUE_VERSIONAN = {"director", "suplente", "administrador"}


class ProcesadorEntrada:
    def __init__(self, drive: Drive, db: BaseDatos, tm, raiz_id: str, ej_id: int, contadores,
                 tmp: Path, hoy: Optional[date] = None, mover_apartados: bool = True):
        self.d, self.db, self.tm, self.ej, self.c, self.tmp = drive, db, tm, ej_id, contadores, tmp
        self.carpetas = Carpetas(drive, raiz_id, tm)
        self.hoy = hoy or date.today()
        # En la migración un archivo que no pasa se queda donde está y el
        # motivo vuelve a la hoja de revisión; en el modo diario se aparta.
        self.mover_apartados = mover_apartados

    # ----------------------------------------------------------- salidas
    def _apartar(self, archivo: dict, carpeta: str, estado: str, motivo: str, avisos: str = ""):
        etiqueta = "RECHAZADO" if estado in ("RECHAZADO", "DUPLICADO") else "POR REVISAR"
        destino = None
        if self.mover_apartados:
            destino = self.carpetas.control(carpeta)
            self.d.mover(archivo, destino, descripcion=f"{etiqueta} {self.hoy:%d-%m-%Y}: {motivo}")
        self.db.registrar_archivo(self.ej, archivo, estado, motivo=motivo, avisos=avisos,
                                  carpeta_id=destino, via=self.via)
        self.db.evento(self.ej, estado.lower(), archivo["id"], archivo["name"], motivo)
        clave = {"RECHAZADO": "rechazados", "DUPLICADO": "duplicados", "POR_REVISAR": "por_revisar"}[estado]
        self.c[clave] += 1
        self.ultimo_motivo = motivo
        log.debug("  %s: %s (%s)", estado, archivo["name"], motivo)

    # ----------------------------------------------------------- un archivo
    def procesar(self, archivo: dict, via: str = "DIARIO", nombre_forzado: Optional[str] = None) -> str:
        """Devuelve el estado final. `nombre_forzado` lo usa la migración,
        que ya trae el nombre estándar aprobado en la hoja de revisión."""
        self.c["revisados"] += 1
        self.via = via
        self.ultimo_motivo = ""
        nombre = nombre_forzado or archivo["name"]

        if archivo["mimeType"].startswith("application/vnd.google-apps."):
            self._apartar(archivo, config.CARPETA_RECHAZADOS, "RECHAZADO",
                          "es un documento nativo de Google; descárguelo como PDF o Excel y súbalo de nuevo")
            return "RECHAZADO"

        n = validar_nombre(nombre, hoy=self.hoy)
        if not n.valido:
            self._apartar(archivo, config.CARPETA_RECHAZADOS, "RECHAZADO", "; ".join(n.motivos))
            return "RECHAZADO"

        motivos, avisos_tm, contratista = self.tm.validar(n)
        avisos = n.avisos + avisos_tm
        if motivos:
            self._apartar(archivo, config.CARPETA_RECHAZADOS, "RECHAZADO", "; ".join(motivos), "; ".join(avisos))
            return "RECHAZADO"

        igual = self.db.oficial_por_md5(archivo.get("md5Checksum"))
        if igual:
            self._apartar(archivo, config.CARPETA_RECHAZADOS, "DUPLICADO",
                          f"contenido idéntico al documento oficial {igual['nombre_base'] or igual['nombre_drive']}")
            return "DUPLICADO"

        subio = quien_subio(archivo)
        vigente = self.db.vigente_por_nombre_base(n.nombre_base)
        version = 1
        if vigente:
            rol = (self.tm.personas.get(subio or "", {}) or {}).get("rol", "").lower()
            if via == "DIARIO" and vigente["subido_por"] != subio and rol not in ROLES_QUE_VERSIONAN:
                self._apartar(
                    archivo, config.CARPETA_POR_REVISAR, "POR_REVISAR",
                    f"ya existe {n.nombre_base} versión {vigente['version_vigente']}, subido por "
                    f"{vigente['subido_por']}; una corrección la sube la misma persona o la aprueba el director",
                    "; ".join(avisos))
                return "POR_REVISAR"
            version = vigente["version_vigente"] + 1

        carpeta_tipo = self.carpetas.tipo(n.proyecto, n.etapa, n.tipo)
        nombre_oficial = n.nombre_base + n.extension
        propiedades = {"pei_version": version, "pei_documento": n.nombre_base}

        nombre_anterior = None
        if vigente and vigente.get("drive_id"):
            # La versión anterior se conserva, renombrada, en _HISTORICO
            nombre_anterior = f"{n.nombre_base}_V{vigente['version_vigente']:02d}{n.extension}"
            try:
                anterior = self.d.obtener(vigente["drive_id"])
                self.d.mover(anterior, self.carpetas.historico(carpeta_tipo), nombre_anterior,
                             {"pei_version": vigente["version_vigente"], "pei_estado": "REEMPLAZADO"})
            except Exception as exc:  # noqa: BLE001
                avisos.append(f"no se pudo mover la versión anterior a _HISTORICO: {exc}")

        oficial = self.d.oficializar(archivo, carpeta_tipo, nombre_oficial, propiedades,
                                     self.carpetas.control(config.CARPETA_ORIGINALES))

        if vigente:
            documento_id = vigente["documento_id"]
            self.db.nueva_version(documento_id, vigente.get("archivo_id"), version, nombre_anterior)
            accion, clave = "versionado", "versionados"
        else:
            documento_id = self.db.crear_documento(n, contratista)
            accion, clave = "oficializado", "oficializados"

        archivo_reg = dict(archivo, md5Checksum=archivo.get("md5Checksum") or oficial.get("md5Checksum"))
        archivo_id = self.db.registrar_archivo(
            self.ej, archivo_reg, "VIGENTE", documento_id=documento_id, version=version,
            avisos="; ".join(avisos), nombre_drive=nombre_oficial, carpeta_id=carpeta_tipo,
            enlace=oficial.get("webViewLink"), via=via, drive_id=oficial["id"])
        self.db.evento(self.ej, accion, oficial["id"], nombre_oficial,
                       f"versión {version}" + (f"; recibido como {archivo['name']}" if archivo["name"] != nombre_oficial else ""))
        self.c[clave] += 1
        log.debug("  %s v%s: %s", accion.upper(), version, nombre_oficial)

        self._cargar_contenido(oficial, archivo_id, n, nombre_oficial)
        return "VIGENTE"

    def _cargar_contenido(self, oficial: dict, archivo_id: int, n, nombre_oficial: str):
        tam = int(oficial.get("size") or 0)
        if n.extension not in config.EXTENSIONES_A_TRANSFORMAR:
            return
        if tam > config.TAMANO_MAX_DESCARGA:
            self.db.actualizar_filas(archivo_id, 0, "contenido no leído: supera el tamaño máximo de descarga")
            return
        try:
            ruta = self.d.descargar(oficial, self.tmp / f"{archivo_id}{n.extension}")
            leido = leer_contenido(ruta, nombre_oficial)
            avisos = leido.avisos + revisar_coherencia(n.tipo, leido)
            filas = sum(self.db.cargar_dataframe(df, tabla, archivo_id) for df, tabla in leido.tablas)
            self.db.actualizar_filas(archivo_id, filas, "; ".join(avisos))
            self.c["filas_cargadas"] += filas
            self.db.evento(self.ej, "carga_tecnica", oficial["id"], nombre_oficial,
                           f"{filas} filas en {', '.join(sorted({t for _, t in leido.tablas})) or 'ninguna tabla'}")
            ruta.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            # El documento ya es oficial; solo falló la lectura del contenido
            self.db.actualizar_filas(archivo_id, 0, f"no se pudo leer el contenido: {exc}")
            self.db.evento(self.ej, "error", oficial["id"], nombre_oficial, f"lectura de contenido: {exc}")


def ejecutar(drive: Optional[Drive] = None, db: Optional[BaseDatos] = None, hoy: Optional[date] = None):
    drive = drive or Drive()
    db = db or BaseDatos()
    with ejecucion(db, "diario") as (ej_id, c), carpeta_temporal() as tmp:
        tmp = Path(tmp)
        raiz = drive.raiz()
        tm = cargar_tabla_maestra(drive, raiz, tmp, db, ej_id)
        db.sincronizar_tabla_maestra(tm)
        proc = ProcesadorEntrada(drive, db, tm, raiz, ej_id, c, tmp, hoy)
        entrada = proc.carpetas.control(config.CARPETA_ENTRADA)
        archivos = drive.listar_archivos(entrada)
        log.info("01_ENTRADA: %d archivo(s)", len(archivos))
        for a in sorted(archivos, key=lambda x: x.get("createdTime", "")):
            try:
                proc.procesar(a)
            except Exception as exc:  # noqa: BLE001
                c["errores"] += 1
                db.evento(ej_id, "error", a.get("id"), a.get("name"), f"{type(exc).__name__}: {exc}")
                # En el registro público solo el tipo de error; el detalle queda en ctrl.evento
                log.error("  ERROR en un archivo (%s); detalle en ctrl.evento", type(exc).__name__)
                log.debug("  detalle", exc_info=True)
    return c
