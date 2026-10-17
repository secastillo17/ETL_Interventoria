-- ============================================================================
-- Base de datos PEI (PostgreSQL 16+, Neon)
-- Planialtimetría e Ingeniería del Caribe S.A.S.
--
-- Tres esquemas:
--   ctrl     control documental: tabla maestra, documentos, versiones,
--            bitácora de ejecuciones y eventos
--   tecnico  datos extraídos del contenido de carteras, cantidades, MH...
--   reporte  vistas de solo lectura para Looker Studio (ver 02_vistas.sql)
--
-- Lo ejecuta UNA VEZ el administrador (rol dueño de la base en Neon),
-- desde el SQL Editor de Neon o con `python -m etl bd-inicializar`.
-- Es idempotente: se puede volver a ejecutar sin perder datos.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ctrl;
CREATE SCHEMA IF NOT EXISTS tecnico;
CREATE SCHEMA IF NOT EXISTS reporte;

-- ---------------------------------------------------------------------------
-- Copia de la tabla maestra (se refresca en cada corrida; la fuente de
-- verdad es la hoja de Drive que mantiene el director)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ctrl.proyecto (
    codigo         VARCHAR(4) PRIMARY KEY,
    nombre         TEXT NOT NULL,
    estado         VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
    fecha_inicio   DATE,
    fecha_fin      DATE
);

CREATE TABLE IF NOT EXISTS ctrl.etapa (
    proyecto       VARCHAR(4) NOT NULL,
    etapa          VARCHAR(3) NOT NULL,
    nombre         TEXT,
    fecha_inicio   DATE,
    fecha_fin      DATE,
    PRIMARY KEY (proyecto, etapa)
);

CREATE TABLE IF NOT EXISTS ctrl.contratista (
    codigo         VARCHAR(3) PRIMARY KEY,
    nombre         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ctrl.frente_asignacion (
    id             SERIAL PRIMARY KEY,
    proyecto       VARCHAR(4) NOT NULL,
    etapa          VARCHAR(3) NOT NULL,
    frente         VARCHAR(3) NOT NULL,
    nombre         TEXT,
    contratista    VARCHAR(3),
    fecha_inicio   DATE,
    fecha_fin      DATE
);

CREATE TABLE IF NOT EXISTS ctrl.tipo_documento (
    codigo         VARCHAR(3) PRIMARY KEY,
    descripcion    TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Bitácora de ejecuciones de la ETL (una fila por corrida de Actions)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ctrl.ejecucion (
    id                  SERIAL PRIMARY KEY,
    modo                VARCHAR(30) NOT NULL,       -- diario | migracion-propuesta | migracion-aplicar | respaldo | carpetas
    inicio              TIMESTAMPTZ NOT NULL DEFAULT now(),
    fin                 TIMESTAMPTZ,
    estado              VARCHAR(20) NOT NULL DEFAULT 'en_curso',  -- en_curso | exitosa | con_errores | fallida
    revisados           INT NOT NULL DEFAULT 0,
    oficializados       INT NOT NULL DEFAULT 0,
    versionados         INT NOT NULL DEFAULT 0,
    rechazados          INT NOT NULL DEFAULT 0,
    por_revisar         INT NOT NULL DEFAULT 0,
    duplicados          INT NOT NULL DEFAULT 0,
    errores             INT NOT NULL DEFAULT 0,
    filas_cargadas      INT NOT NULL DEFAULT 0,
    run_url             TEXT,
    mensaje             TEXT
);

-- ---------------------------------------------------------------------------
-- Documento: la unidad que el equipo reconoce por su nombre estándar.
-- Archivo: cada versión física de un documento en Drive.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ctrl.documento (
    id                  SERIAL PRIMARY KEY,
    nombre_base         VARCHAR(60) NOT NULL UNIQUE,  -- P003-PEI-E02-F01-CAR-25-10-2026-01
    proyecto            VARCHAR(4) NOT NULL,
    origen              VARCHAR(3) NOT NULL,
    etapa               VARCHAR(3) NOT NULL,
    frente              VARCHAR(3) NOT NULL,
    tipo                VARCHAR(3) NOT NULL,
    fecha_documento     DATE NOT NULL,
    consecutivo         SMALLINT NOT NULL,
    contratista         VARCHAR(3),                  -- asignado según frente y fecha
    version_vigente     SMALLINT NOT NULL DEFAULT 1,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_documento_pet ON ctrl.documento (proyecto, etapa, tipo);

CREATE TABLE IF NOT EXISTS ctrl.archivo (
    id                  SERIAL PRIMARY KEY,
    documento_id        INT REFERENCES ctrl.documento(id),
    drive_id            VARCHAR(80) NOT NULL,
    nombre_recibido     TEXT NOT NULL,              -- como lo subió la persona
    nombre_drive        TEXT,                       -- como quedó en Drive
    extension           VARCHAR(10),
    version             SMALLINT,
    estado              VARCHAR(20) NOT NULL,       -- VIGENTE | REEMPLAZADO | RECHAZADO | POR_REVISAR | DUPLICADO
    motivo              TEXT,
    avisos              TEXT,
    md5                 VARCHAR(32),                -- huella de Drive; NULL en archivos nativos de Google
    tamano_bytes        BIGINT,
    mime                TEXT,
    subido_por          TEXT,
    ruta_recibida       TEXT,
    carpeta_drive_id    VARCHAR(80),
    enlace              TEXT,
    via                 VARCHAR(12) NOT NULL DEFAULT 'DIARIO',   -- DIARIO | MIGRACION
    tipo_detectado      VARCHAR(20),                -- lo que dice el contenido (sniffer)
    filas_cargadas      INT NOT NULL DEFAULT 0,
    fecha_modificacion_drive TIMESTAMPTZ,
    registrado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    ejecucion_id        INT REFERENCES ctrl.ejecucion(id)
);
CREATE INDEX IF NOT EXISTS ix_archivo_md5 ON ctrl.archivo (md5);
CREATE INDEX IF NOT EXISTS ix_archivo_drive ON ctrl.archivo (drive_id);
CREATE INDEX IF NOT EXISTS ix_archivo_estado ON ctrl.archivo (estado, registrado_en);

CREATE TABLE IF NOT EXISTS ctrl.evento (
    id                  BIGSERIAL PRIMARY KEY,
    ejecucion_id        INT REFERENCES ctrl.ejecucion(id),
    fecha               TIMESTAMPTZ NOT NULL DEFAULT now(),
    drive_id            VARCHAR(80),
    nombre              TEXT,
    accion              VARCHAR(30) NOT NULL,       -- oficializado | versionado | rechazado | por_revisar | duplicado | carga_tecnica | error | migrado | carpeta_creada
    detalle             TEXT
);
CREATE INDEX IF NOT EXISTS ix_evento_fecha ON ctrl.evento (fecha);

-- Propuestas de clasificación de la migración (cada fila de la hoja de revisión)
CREATE TABLE IF NOT EXISTS ctrl.migracion_item (
    id                  SERIAL PRIMARY KEY,
    ejecucion_id        INT REFERENCES ctrl.ejecucion(id),
    drive_id            VARCHAR(80) NOT NULL,
    ruta                TEXT,
    nombre_actual       TEXT,
    md5                 VARCHAR(32),
    tamano_bytes        BIGINT,
    propietario         TEXT,
    nombre_sugerido     TEXT,
    confianza           VARCHAR(10),
    pistas              TEXT,
    estado              VARCHAR(20) NOT NULL DEFAULT 'PROPUESTO',  -- PROPUESTO | MIGRADO | DESCARTADO | ERROR
    nombre_final        TEXT,
    aprobado_por        TEXT,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_migracion_drive ON ctrl.migracion_item (drive_id);

-- ---------------------------------------------------------------------------
-- Datos técnicos extraídos del contenido (mismas columnas que la v2.4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tecnico.cantidades_ejecutadas (
    id SERIAL PRIMARY KEY,
    archivo_id INT NOT NULL REFERENCES ctrl.archivo(id) ON DELETE CASCADE,
    proyecto TEXT, item TEXT, unidad VARCHAR(20),
    cantidad_ejecutada NUMERIC(18,3), fecha_registro DATE
);

CREATE TABLE IF NOT EXISTS tecnico.mediciones_topograficas (
    id SERIAL PRIMARY KEY,
    archivo_id INT NOT NULL REFERENCES ctrl.archivo(id) ON DELETE CASCADE,
    punto TEXT, norte NUMERIC(18,6), este NUMERIC(18,6),
    elevacion NUMERIC(18,6), descripcion TEXT
);

CREATE TABLE IF NOT EXISTS tecnico.control_mh (
    id SERIAL PRIMARY KEY,
    archivo_id INT NOT NULL REFERENCES ctrl.archivo(id) ON DELETE CASCADE,
    seccion TEXT, mh TEXT,
    c_batea NUMERIC(18,3), c_actual NUMERIC(18,3),
    c_tapa_diseno NUMERIC(18,3), batea_diseno NUMERIC(18,3),
    estado_tapa TEXT, codigo_proyecto TEXT
);

CREATE TABLE IF NOT EXISTS tecnico.cartera_nivelacion (
    id SERIAL PRIMARY KEY,
    archivo_id INT NOT NULL REFERENCES ctrl.archivo(id) ON DELETE CASCADE,
    tuberia TEXT, progresiva TEXT,
    corte NUMERIC(18,3), vista_intermedia NUMERIC(18,3),
    cota_batea NUMERIC(18,3), cota_terreno NUMERIC(18,3),
    longitud NUMERIC(18,3), vista_mas NUMERIC(18,3),
    altura_instrumental NUMERIC(18,3), bm NUMERIC(18,3), ancho NUMERIC(18,3)
);

CREATE TABLE IF NOT EXISTS tecnico.presupuesto_cantidades (
    id SERIAL PRIMARY KEY,
    archivo_id INT NOT NULL REFERENCES ctrl.archivo(id) ON DELETE CASCADE,
    seccion TEXT, codigo TEXT, descripcion TEXT,
    unidad VARCHAR(20), cantidad NUMERIC(18,4)
);

CREATE TABLE IF NOT EXISTS tecnico.cantidades_abscisa (
    id SERIAL PRIMARY KEY,
    archivo_id INT NOT NULL REFERENCES ctrl.archivo(id) ON DELETE CASCADE,
    abscisa TEXT,
    area_corte NUMERIC(18,4), area_promedio_corte NUMERIC(18,4), volumen_corte NUMERIC(18,4),
    area_lleno NUMERIC(18,4), area_promedio_lleno NUMERIC(18,4), volumen_lleno NUMERIC(18,4),
    area_lleno_sel NUMERIC(18,4), area_promedio_lleno_sel NUMERIC(18,4), volumen_lleno_sel NUMERIC(18,4),
    area_subbase NUMERIC(18,4), area_promedio_subbase NUMERIC(18,4), volumen_subbase NUMERIC(18,4)
);
