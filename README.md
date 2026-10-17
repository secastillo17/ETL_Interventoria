# ETL de gobierno de datos PEI

Sistema de gestión centralizada de la información de interventoría de **Planialtimetría e Ingeniería del Caribe S.A.S.** (PEI). Trabajo de grado, Desarrollo Tecnológico, Universidad El Bosque.

La información de obra (carteras, control de pozos, cantidades, planos, informes) llega a una carpeta de Google Drive. Esta ETL valida cada archivo contra el estándar de nombres y la tabla maestra, lo lleva a su carpeta oficial con versión y huella digital, extrae los datos de las carteras y cantidades a PostgreSQL y deja todo listo para los reportes de Looker Studio. El marco de gobierno es DAMA-DMBOK.

```
 Equipo de obra            Google Drive (cuenta de la empresa)            GitHub Actions            Neon (PostgreSQL)       Looker Studio
 ─────────────             ───────────────────────────────────            ──────────────            ─────────────────       ─────────────
 topógrafos ──sube──▶ 01_ENTRADA ──┐                                   ┌─ diario (cron) ─┐         ctrl     (control)      Buscador de
 residente                          │◀── mueve / copia / renombra ──────┤  migración      ├──────▶  tecnico  (datos)   ──▶  archivos
 contratistas                       │    (en los servidores de Google)  │  carpetas       │         reporte  (vistas)       Panel del
 director ──mantiene──▶ TABLA_MAESTRA_PEI ──────── lee ───────────────▶ └─ respaldo ──────┘                                 director
                         P001 Alejandría/E01 .../CAR .../  ◀── oficial
                         99_RECHAZADOS / 99_POR_REVISAR    ◀── con motivo
```

## Qué hace

| Control | Cómo lo hace |
|---|---|
| Estándar de nombres | `PROYECTO-ORIGEN-ETAPA-FRENTE-TIPO-DD-MM-AAAA-NN.ext`, ej. `P003-PEI-E02-F01-CAR-25-10-2026-01.txt`. Nueve partes, lista cerrada de tipos, fecha real y no futura, extensión coherente con el tipo (`etl/nomenclatura.py`). |
| Tabla maestra | El proyecto, la etapa y el frente deben existir, y el origen debe ser PEI o el contratista a cargo del frente **en la fecha del documento** (`etl/tabla_maestra.py`). |
| Versiones | Mismo nombre y misma persona (o el director) crea la versión siguiente; la anterior pasa a `_HISTORICO`. Otra persona con el mismo nombre va a `99_POR_REVISAR`. |
| Duplicados | Contenido idéntico (md5 de Drive) a algo oficial se rechaza como duplicado. |
| Archivos grandes | Planos, PDF y fotos no se descargan; se usan los metadatos y el md5 que Drive ya calcula. Mover y copiar ocurre en los servidores de Google. Solo Excel, CSV y TXT se descargan para leer su contenido. |
| Propiedad | Lo oficial siempre queda a nombre de la cuenta de la empresa. Si el archivo lo subió otra persona se copia y el original se aparta en `99_ORIGINALES_RECIBIDOS`. |
| Trazabilidad | Cada archivo, evento y ejecución queda en `ctrl.archivo`, `ctrl.evento` y `ctrl.ejecucion`, con el enlace a la corrida de Actions. |
| Integridad y respaldo | Cada semana se comprueba que lo oficial siga en Drive con el mismo md5 y se respalda la base en `98_RESPALDOS`. Cada mes el director hace una copia fuera de Google con Takeout. |
| Repositorio público sin datos | El código es público; los registros de Actions solo muestran conteos, los IDs y claves van como Secrets y los datos de la empresa no se suben. |
| Mínimo privilegio | Tres usuarios de base: administración, escritura para la ETL y lectura de vistas para Looker (`sql/03_permisos.sql`). |

## Modos (un solo programa)

| Modo | Cuándo | Workflow |
|---|---|---|
| `python -m etl diario` | Lunes a sábado, 6:47 p. m. | `diario.yml` (automático) |
| `python -m etl migracion-propuesta` | Una vez por lote de archivos antiguos | Se recomienda en el computador (`docs/migracion_local.md`); también `migracion-propuesta.yml` |
| `python -m etl migracion-aplicar` | Cuando la hoja de revisión está aprobada | Se recomienda en el computador; también `migracion-aplicar.yml` (pide escribir APLICAR) |
| `python -m etl carpetas` | Al iniciar y cuando se registra una etapa nueva | `carpetas.yml` (manual) |
| `python -m etl respaldo` | Domingos, 8:13 p. m. | `respaldo.yml` (automático) |
| `python -m etl inventario CARPETA` | En el computador, sobre discos y USB, antes de migrar | local |
| `python -m etl validar NOMBRE` | Para revisar un nombre sin tocar nada | local |
| `python -m etl plantilla` | Genera la tabla maestra vacía | local |
| `python -m etl leer CARPETA` | Prueba los transformadores con archivos locales | local |
| `python -m pytest` | En cada push | `pruebas.yml` (automático) |
| (marca mensual) | Día 1 de cada mes | `mantener-activo.yml`, para que GitHub no apague los workflows programados |

### Migración de lo existente (ISO 13008)

1. Cada persona sube sus archivos antiguos a `00_MIGRACION` (puede usar `python -m etl inventario` antes para ver qué tiene repetido).
2. **Migración 1 - propuesta** genera `02_REVISION_MIGRACION/REVISION_MIGRACION_<fecha>`, una hoja con el nombre sugerido para cada archivo. Las pistas son la carpeta, el nombre, la extensión, el dueño y, para carteras y cantidades, las abscisas y coordenadas del contenido. Marca las copias idénticas y los nombres parecidos.
3. Cada productor filtra por su correo y corrige; el director escribe `SI` en `aprobado_director`.
4. **Migración 2 - aplicar** migra solo las filas `MIGRAR` + `SI`, con las mismas validaciones del modo diario, y deja una hoja `RESULTADO_...`.

Los proyectos `TERMINADO` se clasifican solo hasta proyecto (`ZZ-ZZ`).

## Estructura

```
etl/
  __main__.py          punto de entrada y modos
  config.py            variables de entorno
  nomenclatura.py      validador del estándar
  tabla_maestra.py     lectura y validación contra la tabla maestra
  drive.py             Google Drive (refresh token, md5, mover y copiar en servidor)
  db.py                PostgreSQL
  contenido.py         lectura de Excel/CSV/TXT con los transformadores
  sniffer.py, clasificador.py   tipo real del archivo (v2.4)
  transform/           transformadores de la v2.4 (MH, carteras, cantidades, presupuesto...)
  modos/               diario, migracion, carpetas, respaldo, inventario_local
sql/
  01_esquema.sql       esquemas ctrl, tecnico, reporte
  02_vistas.sql        vistas para Looker
  03_permisos.sql      permisos de los tres usuarios
tests/                 57 pruebas con Drive simulado y Postgres real
docs/
  credenciales.md      Google Cloud, refresh token, Neon y Secrets paso a paso
  looker.md            los dos reportes de Looker Studio
  operacion.md         procedimientos de seguridad y operación
  migracion_local.md   migración desde el computador, por lotes
.github/workflows/     pruebas, diario, migración, carpetas, respaldo, mantener activo
```

## Puesta en marcha

Siga `docs/credenciales.md`. En resumen:

1. Crear en Neon la base, los roles `etl_escritura` y `lector_looker` y ejecutar `sql/01`, `02` y `03`.
2. Crear en Drive (cuenta de la empresa) la carpeta `PEI_REPOSITORIO` y subir la tabla maestra (`python -m etl plantilla`) abierta como Hoja de cálculo de Google.
3. Crear el cliente OAuth en Google Cloud, publicarlo en modo **Producción** y obtener el refresh token en OAuth Playground.
4. Cargar en GitHub los Secrets `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `DATABASE_URL`, `DRIVE_RAIZ_ID` y `TABLA_MAESTRA_ID`.
5. Ejecutar **Crear carpetas** y luego **ETL diaria** desde la pestaña Actions.
6. Conectar Looker Studio con el usuario `lector_looker` (`docs/looker.md`).
7. Migrar lo existente desde el computador (`docs/migracion_local.md`).

## Pruebas

```bash
pip install -r requirements.txt
python -m pytest                       # sin base: corren las pruebas puras
TEST_DATABASE_URL=postgresql://... python -m pytest     # completas (¡nunca la base de producción!)
PEI_DATOS_REALES=/ruta/a/archivos python -m pytest      # agrega las pruebas con archivos reales de la empresa
```

Los archivos reales de la empresa no se suben al repositorio (`tests/datos_reales/` está en `.gitignore`).

## Origen

Los transformadores (`etl/transform/`) y el detector de tipo por contenido (`etl/sniffer.py`) vienen de la versión 2.4 del ETL local. Esta versión agrega la validación del estándar y la tabla maestra, el versionado, la escritura en Drive sin descargas, PostgreSQL, la migración, los respaldos y la ejecución en GitHub Actions.
