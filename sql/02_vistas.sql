-- ============================================================================
-- Vistas para Looker Studio. El usuario lector_looker solo ve este esquema.
-- Se pueden volver a crear en cualquier momento (CREATE OR REPLACE).
-- ============================================================================

-- 1. Buscador de archivos (reporte del equipo): solo lo oficial y vigente
CREATE OR REPLACE VIEW reporte.v_buscador AS
SELECT
    d.nombre_base                           AS documento,
    d.proyecto                              AS cod_proyecto,
    p.nombre                                AS proyecto,
    d.etapa                                 AS cod_etapa,
    COALESCE(e.nombre, CASE WHEN d.etapa = 'ZZ' THEN 'General' END) AS etapa,
    d.frente,
    d.tipo                                  AS cod_tipo,
    t.descripcion                           AS tipo,
    d.origen,
    COALESCE(c.nombre, CASE WHEN d.origen = 'PEI' THEN 'Interventoría PEI' END) AS producido_por,
    cc.nombre                               AS contratista_frente,
    d.fecha_documento,
    a.version,
    a.extension,
    ROUND(a.tamano_bytes / 1048576.0, 2)    AS tamano_mb,
    a.subido_por,
    a.registrado_en                         AS fecha_carga,
    a.enlace                                AS abrir_en_drive
FROM ctrl.documento d
JOIN ctrl.archivo a        ON a.documento_id = d.id AND a.estado = 'VIGENTE'
LEFT JOIN ctrl.proyecto p  ON p.codigo = d.proyecto
LEFT JOIN ctrl.etapa e     ON e.proyecto = d.proyecto AND e.etapa = d.etapa
LEFT JOIN ctrl.tipo_documento t ON t.codigo = d.tipo
LEFT JOIN ctrl.contratista c    ON c.codigo = d.origen
LEFT JOIN ctrl.contratista cc   ON cc.codigo = d.contratista;

-- 2. Historial de versiones de cada documento
CREATE OR REPLACE VIEW reporte.v_versiones AS
SELECT d.nombre_base AS documento, a.version, a.estado, a.subido_por,
       a.registrado_en AS fecha_carga, a.md5, a.enlace
FROM ctrl.archivo a
JOIN ctrl.documento d ON d.id = a.documento_id
WHERE a.estado IN ('VIGENTE', 'REEMPLAZADO');

-- 3. Todo lo que llegó, con su resultado (base de los indicadores)
CREATE OR REPLACE VIEW reporte.v_recepcion AS
SELECT
    a.id, a.registrado_en::date AS fecha_carga,
    date_trunc('month', a.registrado_en)::date AS mes,
    a.via, a.estado, a.nombre_recibido, a.subido_por,
    split_part(a.nombre_recibido, '-', 1) AS cod_proyecto_declarado,
    a.motivo, a.avisos,
    CASE WHEN a.estado IN ('VIGENTE', 'REEMPLAZADO') THEN 1 ELSE 0 END AS conforme,
    CASE WHEN a.estado = 'RECHAZADO' THEN 1 ELSE 0 END AS rechazado,
    CASE WHEN a.estado = 'POR_REVISAR' THEN 1 ELSE 0 END AS por_revisar,
    CASE WHEN a.estado = 'DUPLICADO' THEN 1 ELSE 0 END AS duplicado
FROM ctrl.archivo a;

-- 4. Cumplimiento del estándar por mes (panel del director)
CREATE OR REPLACE VIEW reporte.v_cumplimiento_mensual AS
SELECT mes, via,
       COUNT(*)                         AS recibidos,
       SUM(conforme)                    AS conformes,
       SUM(rechazado)                   AS rechazados,
       SUM(por_revisar)                 AS por_revisar,
       SUM(duplicado)                   AS duplicados,
       ROUND(100.0 * SUM(conforme) / NULLIF(COUNT(*) - SUM(duplicado), 0), 1) AS pct_conformidad
FROM reporte.v_recepcion
GROUP BY mes, via;

-- 5. Motivos de rechazo más frecuentes y quién los comete
CREATE OR REPLACE VIEW reporte.v_rechazos AS
SELECT fecha_carga, subido_por, nombre_recibido,
       split_part(motivo, ';', 1) AS motivo_principal, motivo
FROM reporte.v_recepcion
WHERE estado IN ('RECHAZADO', 'POR_REVISAR');

-- 6. Documentos oficiales por proyecto, etapa y tipo
CREATE OR REPLACE VIEW reporte.v_inventario AS
SELECT cod_proyecto, proyecto, cod_etapa, etapa, cod_tipo, tipo,
       COUNT(*)                AS documentos,
       SUM(tamano_mb)          AS tamano_mb,
       MAX(fecha_documento)    AS ultimo_documento,
       MAX(fecha_carga)        AS ultima_carga
FROM reporte.v_buscador
GROUP BY cod_proyecto, proyecto, cod_etapa, etapa, cod_tipo, tipo;

-- 7. Corridas de la ETL
CREATE OR REPLACE VIEW reporte.v_ejecuciones AS
SELECT id, modo, inicio, fin, estado,
       ROUND(EXTRACT(EPOCH FROM (fin - inicio))::numeric, 1) AS duracion_seg,
       revisados, oficializados, versionados, rechazados, por_revisar,
       duplicados, errores, filas_cargadas, run_url
FROM ctrl.ejecucion;

-- 8. Indicadores en una sola fila (tarjetas del panel)
CREATE OR REPLACE VIEW reporte.v_indicadores AS
SELECT
    (SELECT COUNT(*) FROM ctrl.documento)                                     AS documentos_oficiales,
    (SELECT COUNT(*) FROM ctrl.archivo WHERE estado = 'REEMPLAZADO')          AS versiones_anteriores,
    (SELECT ROUND(SUM(tamano_bytes) / 1073741824.0, 2)
       FROM ctrl.archivo WHERE estado IN ('VIGENTE', 'REEMPLAZADO'))          AS gb_oficiales,
    (SELECT ROUND(100.0 * SUM(conforme) / NULLIF(COUNT(*) - SUM(duplicado), 0), 1)
       FROM reporte.v_recepcion
      WHERE fecha_carga >= current_date - 30 AND via = 'DIARIO')              AS pct_conformidad_30d,
    (SELECT COUNT(*) FROM ctrl.archivo a
      WHERE a.estado = 'POR_REVISAR'
        AND NOT EXISTS (SELECT 1 FROM ctrl.archivo b
                         WHERE b.drive_id = a.drive_id AND b.id > a.id))      AS pendientes_por_revisar,
    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE estado = 'exitosa') / NULLIF(COUNT(*), 0), 1)
       FROM ctrl.ejecucion WHERE inicio >= now() - interval '30 days')        AS pct_ejecuciones_ok_30d,
    (SELECT MAX(fin) FROM ctrl.ejecucion WHERE modo = 'diario' AND estado <> 'fallida') AS ultima_ejecucion_diaria,
    (SELECT COUNT(*) FROM ctrl.migracion_item WHERE estado = 'MIGRADO')       AS archivos_migrados,
    (SELECT COUNT(*) FROM ctrl.migracion_item WHERE estado = 'PROPUESTO')     AS migracion_pendiente;

-- 9. Datos técnicos con su contexto documental
CREATE OR REPLACE VIEW reporte.v_control_mh AS
SELECT b.cod_proyecto, b.proyecto, b.cod_etapa, b.etapa, b.frente, b.documento,
       b.fecha_documento, m.seccion, m.mh, m.c_batea, m.c_actual,
       m.c_tapa_diseno, m.batea_diseno, m.estado_tapa,
       m.c_actual - m.c_tapa_diseno AS diferencia_tapa
FROM tecnico.control_mh m
JOIN ctrl.archivo a ON a.id = m.archivo_id AND a.estado = 'VIGENTE'
JOIN ctrl.documento d ON d.id = a.documento_id
JOIN reporte.v_buscador b ON b.documento = d.nombre_base;

CREATE OR REPLACE VIEW reporte.v_cantidades_abscisa AS
SELECT b.cod_proyecto, b.proyecto, b.cod_etapa, b.etapa, b.documento, b.fecha_documento,
       q.abscisa, q.volumen_corte, q.volumen_lleno, q.volumen_lleno_sel, q.volumen_subbase
FROM tecnico.cantidades_abscisa q
JOIN ctrl.archivo a ON a.id = q.archivo_id AND a.estado = 'VIGENTE'
JOIN ctrl.documento d ON d.id = a.documento_id
JOIN reporte.v_buscador b ON b.documento = d.nombre_base;

CREATE OR REPLACE VIEW reporte.v_cartera_nivelacion AS
SELECT b.cod_proyecto, b.proyecto, b.cod_etapa, b.etapa, b.documento, b.fecha_documento,
       c.tuberia, c.progresiva, c.cota_terreno, c.cota_batea, c.corte, c.longitud
FROM tecnico.cartera_nivelacion c
JOIN ctrl.archivo a ON a.id = c.archivo_id AND a.estado = 'VIGENTE'
JOIN ctrl.documento d ON d.id = a.documento_id
JOIN reporte.v_buscador b ON b.documento = d.nombre_base;
