"""
Acceso a PostgreSQL (Neon). Toda la escritura de la ETL pasa por aquí.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from etl import config
from etl.nomenclatura import TIPOS


def _url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class BaseDatos:
    def __init__(self, url: Optional[str] = None):
        url = url or config.DATABASE_URL
        if not url:
            raise RuntimeError("Falta DATABASE_URL (cadena de conexión de Neon). Ver docs/credenciales.md.")
        self.engine: Engine = create_engine(_url(url), pool_pre_ping=True)

    # ------------------------------------------------------------ esquema
    def inicializar(self, incluir_permisos: bool = False):
        archivos = ["01_esquema.sql", "02_vistas.sql"] + (["03_permisos.sql"] if incluir_permisos else [])
        with self.engine.begin() as c:
            for nombre in archivos:
                c.exec_driver_sql((config.SQL_DIR / nombre).read_text(encoding="utf-8"))

    # --------------------------------------------------------- ejecuciones
    def iniciar_ejecucion(self, modo: str) -> int:
        with self.engine.begin() as c:
            return c.execute(text(
                "INSERT INTO ctrl.ejecucion (modo, run_url) VALUES (:m, :u) RETURNING id"),
                {"m": modo, "u": config.RUN_URL}).scalar_one()

    def cerrar_ejecucion(self, ejecucion_id: int, contadores: dict, estado: str, mensaje: str = ""):
        campos = ["revisados", "oficializados", "versionados", "rechazados",
                  "por_revisar", "duplicados", "errores", "filas_cargadas"]
        valores = {k: int(contadores.get(k, 0)) for k in campos}
        sets = ", ".join(f"{k} = :{k}" for k in campos)
        with self.engine.begin() as c:
            c.execute(text(f"UPDATE ctrl.ejecucion SET fin = now(), estado = :estado, "
                           f"mensaje = :mensaje, {sets} WHERE id = :id"),
                      {**valores, "estado": estado, "mensaje": mensaje[:4000], "id": ejecucion_id})

    def evento(self, ejecucion_id: int, accion: str, drive_id: str = None, nombre: str = None,
               detalle: str = ""):
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO ctrl.evento (ejecucion_id, drive_id, nombre, accion, detalle) "
                           "VALUES (:e, :d, :n, :a, :t)"),
                      {"e": ejecucion_id, "d": drive_id, "n": nombre, "a": accion, "t": (detalle or "")[:4000]})

    # ------------------------------------------------------- tabla maestra
    def sincronizar_tabla_maestra(self, tm):
        """Deja en la base una copia exacta de la tabla maestra de Drive."""
        with self.engine.begin() as c:
            for t in ("frente_asignacion", "etapa", "proyecto", "contratista", "tipo_documento"):
                c.execute(text(f"DELETE FROM ctrl.{t}"))
            if tm.proyectos:
                c.execute(text("INSERT INTO ctrl.proyecto VALUES (:codigo, :nombre, :estado, :fi, :ff)"),
                          [{"codigo": p.codigo, "nombre": p.nombre, "estado": p.estado,
                            "fi": p.fecha_inicio, "ff": p.fecha_fin} for p in tm.proyectos.values()])
            if tm.etapas:
                c.execute(text("INSERT INTO ctrl.etapa VALUES (:p, :e, :n, :fi, :ff)"),
                          [{"p": e.proyecto, "e": e.etapa, "n": e.nombre, "fi": e.fecha_inicio,
                            "ff": e.fecha_fin} for e in tm.etapas.values()])
            if tm.contratistas:
                c.execute(text("INSERT INTO ctrl.contratista VALUES (:c, :n)"),
                          [{"c": k, "n": v["nombre"]} for k, v in tm.contratistas.items()])
            if tm.frentes:
                c.execute(text("INSERT INTO ctrl.frente_asignacion (proyecto, etapa, frente, nombre, "
                               "contratista, fecha_inicio, fecha_fin) VALUES (:p, :e, :f, :n, :c, :fi, :ff)"),
                          [{"p": a.proyecto, "e": a.etapa, "f": a.frente, "n": a.nombre,
                            "c": a.contratista or None, "fi": a.fecha_inicio, "ff": a.fecha_fin}
                           for a in tm.frentes])
            c.execute(text("INSERT INTO ctrl.tipo_documento VALUES (:c, :d)"),
                      [{"c": k, "d": v} for k, v in TIPOS.items()])

    # ---------------------------------------------------------- consultas
    def vigente_por_nombre_base(self, nombre_base: str) -> Optional[dict]:
        with self.engine.begin() as c:
            fila = c.execute(text("""
                SELECT d.id AS documento_id, d.version_vigente, a.id AS archivo_id, a.drive_id,
                       a.subido_por, a.md5, a.nombre_drive, a.carpeta_drive_id
                FROM ctrl.documento d
                LEFT JOIN ctrl.archivo a ON a.documento_id = d.id AND a.estado = 'VIGENTE'
                WHERE d.nombre_base = :n"""), {"n": nombre_base}).mappings().first()
        return dict(fila) if fila else None

    def oficial_por_md5(self, md5: Optional[str]) -> Optional[dict]:
        if not md5:
            return None
        with self.engine.begin() as c:
            fila = c.execute(text("""
                SELECT a.id, a.nombre_drive, a.estado, d.nombre_base
                FROM ctrl.archivo a LEFT JOIN ctrl.documento d ON d.id = a.documento_id
                WHERE a.md5 = :m AND a.estado IN ('VIGENTE', 'REEMPLAZADO')
                ORDER BY a.id LIMIT 1"""), {"m": md5}).mappings().first()
        return dict(fila) if fila else None

    def siguiente_consecutivo(self, proyecto, origen, etapa, frente, tipo, fecha) -> int:
        """Para la migración: el primer consecutivo libre de ese día."""
        with self.engine.begin() as c:
            n = c.execute(text("""
                SELECT COALESCE(MAX(consecutivo), 0) FROM ctrl.documento
                WHERE proyecto = :p AND origen = :o AND etapa = :e AND frente = :f
                  AND tipo = :t AND fecha_documento = :d"""),
                {"p": proyecto, "o": origen, "e": etapa, "f": frente, "t": tipo, "d": fecha}).scalar_one()
        return int(n) + 1

    # ------------------------------------------------------------ escritura
    def crear_documento(self, n, contratista: Optional[str]) -> int:
        with self.engine.begin() as c:
            return c.execute(text("""
                INSERT INTO ctrl.documento (nombre_base, proyecto, origen, etapa, frente, tipo,
                    fecha_documento, consecutivo, contratista)
                VALUES (:b, :p, :o, :e, :f, :t, :d, :c, :ct) RETURNING id"""),
                {"b": n.nombre_base, "p": n.proyecto, "o": n.origen, "e": n.etapa, "f": n.frente,
                 "t": n.tipo, "d": n.fecha, "c": n.consecutivo, "ct": contratista}).scalar_one()

    def nueva_version(self, documento_id: int, archivo_anterior_id: Optional[int], version: int,
                      nombre_anterior: Optional[str] = None):
        with self.engine.begin() as c:
            if archivo_anterior_id:
                c.execute(text("UPDATE ctrl.archivo SET estado = 'REEMPLAZADO', "
                               "nombre_drive = COALESCE(:nom, nombre_drive) WHERE id = :id"),
                          {"id": archivo_anterior_id, "nom": nombre_anterior})
            c.execute(text("UPDATE ctrl.documento SET version_vigente = :v, actualizado_en = now() "
                           "WHERE id = :id"), {"v": version, "id": documento_id})

    def registrar_archivo(self, ejecucion_id: int, archivo: dict, estado: str, *,
                          documento_id=None, version=None, motivo="", avisos="", nombre_drive=None,
                          carpeta_id=None, enlace=None, via="DIARIO", tipo_detectado=None,
                          drive_id=None) -> int:
        tam = archivo.get("size")
        modif = archivo.get("modifiedTime")
        with self.engine.begin() as c:
            return c.execute(text("""
                INSERT INTO ctrl.archivo (documento_id, drive_id, nombre_recibido, nombre_drive,
                    extension, version, estado, motivo, avisos, md5, tamano_bytes, mime, subido_por,
                    ruta_recibida, carpeta_drive_id, enlace, via, tipo_detectado,
                    fecha_modificacion_drive, ejecucion_id)
                VALUES (:doc, :did, :nr, :nd, :ext, :ver, :est, :mot, :avi, :md5, :tam, :mime, :sub,
                    :ruta, :car, :enl, :via, :td, :fm, :ej) RETURNING id"""), {
                "doc": documento_id, "did": drive_id or archivo["id"], "nr": archivo["name"],
                "nd": nombre_drive or archivo["name"],
                "ext": ("." + archivo["name"].rsplit(".", 1)[-1].lower()) if "." in archivo["name"] else "",
                "ver": version, "est": estado, "mot": motivo[:4000] if motivo else None,
                "avi": avisos[:4000] if avisos else None, "md5": archivo.get("md5Checksum"),
                "tam": int(tam) if tam else None, "mime": archivo.get("mimeType"),
                "sub": quien_subio(archivo), "ruta": archivo.get("ruta", ""), "car": carpeta_id,
                "enl": enlace or archivo.get("webViewLink"), "via": via, "td": tipo_detectado,
                "fm": datetime.fromisoformat(modif.replace("Z", "+00:00")) if modif else None,
                "ej": ejecucion_id,
            }).scalar_one()

    def actualizar_filas(self, archivo_id: int, filas: int, avisos_extra: str = ""):
        with self.engine.begin() as c:
            c.execute(text("""UPDATE ctrl.archivo SET filas_cargadas = :f,
                avisos = NULLIF(CONCAT_WS('; ', NULLIF(avisos, ''), NULLIF(:a, '')), '')
                WHERE id = :id"""), {"f": filas, "a": avisos_extra[:2000], "id": archivo_id})

    def cargar_dataframe(self, df: pd.DataFrame, tabla: str, archivo_id: int) -> int:
        if df is None or df.empty:
            return 0
        df = df.copy()
        df["archivo_id"] = archivo_id
        df.to_sql(tabla, self.engine, schema="tecnico", if_exists="append", index=False,
                  method="multi", chunksize=500)
        return len(df)

    # --------------------------------------------------------- migración
    def registrar_migracion_item(self, ejecucion_id, item: dict) -> int:
        with self.engine.begin() as c:
            return c.execute(text("""
                INSERT INTO ctrl.migracion_item (ejecucion_id, drive_id, ruta, nombre_actual, md5,
                    tamano_bytes, propietario, nombre_sugerido, confianza, pistas)
                VALUES (:e, :d, :r, :n, :m, :t, :p, :s, :c, :pi) RETURNING id"""),
                {"e": ejecucion_id, **item}).scalar_one()

    def actualizar_migracion_item(self, drive_id: str, estado: str, nombre_final=None, aprobado_por=None):
        with self.engine.begin() as c:
            c.execute(text("""UPDATE ctrl.migracion_item SET estado = :e, nombre_final = :n,
                aprobado_por = :a, actualizado_en = now()
                WHERE id = (SELECT MAX(id) FROM ctrl.migracion_item WHERE drive_id = :d)"""),
                {"e": estado, "n": nombre_final, "a": aprobado_por, "d": drive_id})

    def leer_sql(self, consulta: str) -> pd.DataFrame:
        return pd.read_sql(text(consulta), self.engine)


def quien_subio(archivo: dict) -> Optional[str]:
    """El correo de quien subió el archivo. En un archivo recién subido es
    el último que lo modificó; si no viene, se toma el dueño."""
    usuario = (archivo.get("lastModifyingUser") or {}).get("emailAddress")
    if not usuario:
        duenos = archivo.get("owners") or []
        usuario = duenos[0].get("emailAddress") if duenos else None
    return usuario.lower() if usuario else None
