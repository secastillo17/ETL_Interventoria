-- ============================================================================
-- Permisos de los tres usuarios de la base (principio de mínimo privilegio)
--
--   neondb_owner   administración (lo crea Neon). Solo el estudiante y el
--                  director tienen esta clave. Crea el esquema y los roles.
--   etl_escritura  el que usa GitHub Actions. Lee y escribe ctrl y tecnico;
--                  no puede crear ni borrar tablas.
--   lector_looker  el que usa Looker Studio. Solo lee las vistas de reporte.
--
-- Antes de ejecutar esto, cree los dos roles en la consola de Neon
-- (Branches > main > Roles > New role). Neon genera las claves; no se
-- escriben en ningún archivo del repositorio.
-- ============================================================================

-- Nadie más puede crear objetos en el esquema público
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- ETL ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA ctrl, tecnico, reporte TO etl_escritura;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA ctrl TO etl_escritura;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tecnico TO etl_escritura;
GRANT DELETE ON ctrl.proyecto, ctrl.etapa, ctrl.contratista, ctrl.frente_asignacion,
               ctrl.tipo_documento TO etl_escritura;     -- se refrescan desde la tabla maestra
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ctrl, tecnico TO etl_escritura;
GRANT SELECT ON ALL TABLES IN SCHEMA reporte TO etl_escritura;

-- Looker ------------------------------------------------------------------
GRANT USAGE ON SCHEMA reporte TO lector_looker;
GRANT SELECT ON ALL TABLES IN SCHEMA reporte TO lector_looker;
REVOKE ALL ON SCHEMA ctrl, tecnico FROM lector_looker;
-- Las vistas leen ctrl y tecnico con los permisos de su dueño, así que
-- lector_looker no necesita acceso a esas tablas.

-- Lo que se cree después hereda los mismos permisos
ALTER DEFAULT PRIVILEGES IN SCHEMA ctrl GRANT SELECT, INSERT, UPDATE ON TABLES TO etl_escritura;
ALTER DEFAULT PRIVILEGES IN SCHEMA tecnico GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO etl_escritura;
ALTER DEFAULT PRIVILEGES IN SCHEMA ctrl, tecnico GRANT USAGE, SELECT ON SEQUENCES TO etl_escritura;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporte GRANT SELECT ON TABLES TO lector_looker, etl_escritura;

-- Looker lista las tablas del search_path: así ve directamente las vistas
ALTER ROLE lector_looker SET search_path = reporte;
ALTER ROLE etl_escritura SET search_path = ctrl, tecnico, public;
