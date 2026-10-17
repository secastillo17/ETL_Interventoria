# Reportes en Looker Studio

Los reportes se conectan a Neon con el usuario **`lector_looker`**, que solo puede leer las vistas del esquema `reporte`. Nadie del equipo entra a la base directamente.

## Conexión (una vez por fuente de datos)

1. Entre a <https://lookerstudio.google.com> con la cuenta de la empresa y vaya a **Crear → Fuente de datos → PostgreSQL**.
2. Llene los datos tomados de la cadena de conexión de Neon (rol `lector_looker`):
   - **Host**: `ep-xxxx.us-east-2.aws.neon.tech`.
   - **Puerto**: vacío.
   - **Base de datos**: `neondb`.
   - **Usuario**: `lector_looker` y su clave.
3. Marque **Habilitar SSL** y deje sin marcar "autenticación de cliente".
4. En **Certificado del servidor**, suba `isrgrootx1.pem`, que se descarga de <https://letsencrypt.org/certs/isrgrootx1.pem>.
5. Pulse **Autenticar** y elija la vista. El usuario tiene `search_path = reporte`, así que las vistas aparecen como tablas.

Cree una fuente de datos por vista: `v_buscador`, `v_indicadores`, `v_cumplimiento_mensual`, `v_rechazos`, `v_inventario`, `v_ejecuciones` y las técnicas que se usen.

En cada fuente, vaya a **Recurso → Administrar fuentes → Editar** y ponga la **actualización de datos** en 1 hora. Para que el enlace se pueda abrir con un clic, cambie el tipo del campo `abrir_en_drive` a **URL**.

## Reporte 1. Buscador de archivos (para todo el equipo)

Fuente `v_buscador`.

| Elemento | Configuración |
|---|---|
| Controles de filtro (desplegables) | `proyecto`, `etapa`, `frente`, `tipo`, `producido_por` |
| Control de período | `fecha_documento` |
| Cuadro de búsqueda | `documento` (busca por cualquier parte del nombre) |
| Tabla | `documento`, `tipo`, `etapa`, `fecha_documento`, `version`, `producido_por`, `tamano_mb`, `abrir_en_drive` (URL) |
| Orden | `fecha_documento` descendente |

Compártalo como **lector** con el equipo. Como el reporte usa las credenciales del propietario, nadie necesita la clave de la base.

## Reporte 2. Panel de gobierno (para el director)

| Sección | Fuente | Gráfico |
|---|---|---|
| Tarjetas | `v_indicadores` | Documentos oficiales, GB oficiales, % de conformidad (30 días), pendientes por revisar, % de ejecuciones exitosas, última ejecución diaria, archivos migrados y migración pendiente |
| Cumplimiento del estándar | `v_cumplimiento_mensual` | Columnas apiladas por `mes` (conformes, rechazados, por revisar) y línea `pct_conformidad`; filtro `via` = DIARIO |
| Motivos de rechazo | `v_rechazos` | Barras por `motivo_principal` y tabla por `subido_por` |
| Inventario | `v_inventario` | Tabla dinámica proyecto × etapa × tipo con `documentos` y `ultima_carga` |
| Salud de la ETL | `v_ejecuciones` | Tabla de las últimas 30 corridas con `estado`, `duracion_seg`, contadores y `run_url` (URL) |
| Datos técnicos | `v_control_mh`, `v_cantidades_abscisa` | Diferencia de cota de tapa por MH; volúmenes de corte y lleno por abscisa |

Estos indicadores son los que se reportan en la tesis para evaluar la solución durante la operación asistida (cumplimiento del estándar, rechazos, tiempo de respuesta y disponibilidad de la ETL).
