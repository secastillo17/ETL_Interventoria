# Credenciales y puesta en marcha

Todo se hace con la **cuenta de Google de la empresa**, no con cuentas personales. Así lo oficial queda a nombre de PEI y no depende de nadie del equipo. Ninguna clave se escribe en el repositorio. Las claves van solo en GitHub Secrets y en un `.env` local, que no se sube.

Tiempo estimado: unos 45 minutos.

---

## 1. Base de datos en Neon

1. Entre a <https://neon.tech> con la cuenta de la empresa. Cree un proyecto `pei` con Postgres 16 o 17, región **AWS US East**, que es la más cercana a los servidores de GitHub y de Looker. El plan gratuito tiene 0,5 GB, que alcanza de sobra para los metadatos y las tablas técnicas. Los archivos siguen en Drive.
2. Cree los usuarios `etl_escritura` y `lector_looker` **por SQL, no desde la consola**. Neon les da a los usuarios creados en la consola la membresía `neon_superuser`, que incluye `pg_read_all_data` y `pg_write_all_data`: el usuario de Looker podría escribir y borrar en todas las tablas, y eso rompe el mínimo privilegio. Los usuarios creados con `CREATE ROLE` no reciben esa membresía. En el **SQL Editor**, con el rol `neondb_owner`, ejecute (con una clave temporal cualquiera de más de 12 caracteres):
   ```sql
   CREATE ROLE etl_escritura WITH LOGIN PASSWORD '<clave temporal>';
   CREATE ROLE lector_looker WITH LOGIN PASSWORD '<clave temporal>';
   GRANT CONNECT ON DATABASE neondb TO etl_escritura, lector_looker;
   ```
   Después, en **Postgres database → Roles**, use **Reset password** en cada uno para que Neon genere la clave definitiva. Así la clave no queda escrita en ningún lado.
3. Abra **SQL Editor** con el rol dueño (`neondb_owner`) y ejecute en orden:
   - `sql/01_esquema.sql`
   - `sql/02_vistas.sql`
   - `sql/03_permisos.sql`
4. Vaya a **Dashboard → Connect**, elija el rol `etl_escritura` y copie la cadena de conexión. Esa cadena es el secreto `DATABASE_URL`. Debe terminar en `?sslmode=require`.

> El cómputo gratuito de Neon se suspende tras 5 minutos sin uso y despierta en unos segundos con la primera conexión. La ETL lo maneja sola. En Looker, la primera consulta del día puede tardar un poco más.

## 2. Carpeta raíz y tabla maestra en Drive

1. En el Drive de la empresa cree la carpeta `PEI_REPOSITORIO`. Copie su ID desde la URL `drive.google.com/drive/folders/<ID>`. Esa es la variable `DRIVE_RAIZ_ID`.
2. En su computador ejecute `python -m etl plantilla`. Suba `TABLA_MAESTRA_PEI.xlsx` dentro de `PEI_REPOSITORIO` y ábrala con **Abrir con → Hojas de cálculo de Google**. Luego use **Archivo → Guardar como Hojas de cálculo de Google** y borre el .xlsx.
3. Llene la hoja con los proyectos, etapas, frentes y contratistas reales, y borre las filas de ejemplo. Copie el ID desde la URL `docs.google.com/spreadsheets/d/<ID>/edit`. Esa es la variable `TABLA_MAESTRA_ID`.
4. Comparta la tabla maestra solo como **lector** con el equipo. Solo el director y el suplente la editan.

## 3. Cliente OAuth en Google Cloud

1. Entre a <https://console.cloud.google.com> con la cuenta de la empresa y cree el proyecto `PEI-ETL`.
2. Vaya a **APIs y servicios → Biblioteca**, busque **Google Drive API** y actívela.
3. Vaya a **Google Auth Platform**. En versiones anteriores de la consola se llama "Pantalla de consentimiento de OAuth".
   - **Branding**: nombre `PEI ETL`, correo de soporte y correo de contacto del desarrollador de la empresa. Google no deja publicar una app externa sin página principal, política de privacidad y dominio autorizado, aunque la pantalla no los marque como obligatorios. Se usó el repositorio público: página principal `https://github.com/secastillo17/ETL_Interventoria`, política y condiciones con enlaces a documentos del repositorio, y dominio autorizado `github.com`. No suba logotipo: con logotipo Google exige verificar la app.
   - **Audience**: tipo **External**. Luego pulse **Publish app** para que quede **In production**.
     - **Esto es obligatorio.** En modo *Testing* el refresh token caduca a los 7 días y la ETL dejaría de funcionar sola.
     - Google mostrará que la app "no está verificada". Para una app interna con un solo usuario, que es la propia empresa, no hace falta verificarla.
   - **Data access**: agregue el alcance `https://www.googleapis.com/auth/drive`.
4. Vaya a **Clients → Create client** y llénelo así:
   - **Tipo**: Aplicación web.
   - **Nombre**: `ETL GitHub`.
   - **URI de redirección autorizado**: `https://developers.google.com/oauthplayground`.
   - Copie el **Client ID** y el **Client secret**. Son los secretos `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.

## 4. Refresh token (una sola vez, sin programar nada)

1. Abra <https://developers.google.com/oauthplayground>.
2. Pulse el engranaje ⚙ (arriba a la derecha) y marque **Use your own OAuth credentials**. Pegue el Client ID y el Client secret del paso anterior.
   - Con credenciales propias el token no caduca a las 24 horas, como sí ocurre con las del Playground.
3. En **Step 1**, escriba en el cuadro `https://www.googleapis.com/auth/drive` y pulse **Authorize APIs**.
4. Inicie sesión **con la cuenta de la empresa**. Ante el aviso de app no verificada, pulse **Configuración avanzada → Ir a PEI ETL** y luego **Permitir**.
5. En **Step 2**, pulse **Exchange authorization code for tokens** y copie el **Refresh token**. Es el secreto `GOOGLE_REFRESH_TOKEN`.
6. Cierre la pestaña. No guarde el token en ningún documento ni chat.

El token deja de servir si alguien lo revoca en <https://myaccount.google.com/permissions>, si pasan seis meses sin usarse (la ETL diaria lo evita) o si se cambia la contraseña con ciertas políticas. En ese caso repita solo este paso 4 y actualice el secreto.

## 5. Repositorio y Secrets de GitHub

1. Cree el repositorio **público** `ETL_Interventoria`. Cualquiera puede ver el código y las ejecuciones sin invitación, pero nadie puede cambiarlo ni ejecutarlo. Los Secrets no son visibles, y en los registros solo aparecen conteos, nunca nombres de archivos ni correos.
2. En el repositorio, vaya a **Settings → Secrets and variables → Actions**.
   - En la pestaña **Secrets → New repository secret**, cree:

     | Nombre | Valor |
     |---|---|
     | `GOOGLE_CLIENT_ID` | paso 3 |
     | `GOOGLE_CLIENT_SECRET` | paso 3 |
     | `GOOGLE_REFRESH_TOKEN` | paso 4 |
     | `DATABASE_URL` | paso 1 (rol `etl_escritura`) |

     | `DRIVE_RAIZ_ID` | paso 2 |
     | `TABLA_MAESTRA_ID` | paso 2 |

     Los dos IDs no dan acceso por sí solos, pero se guardan como Secrets para que no aparezcan en los registros públicos.

3. Vaya a la pestaña **Actions** y ejecute en este orden con **Run workflow**:
   1. **Crear carpetas**. Revise en Drive que aparezcan `01_ENTRADA`, los proyectos y sus etapas.
   2. **ETL diaria**. Con `01_ENTRADA` vacía debe terminar en verde y dejar una fila en `ctrl.ejecucion`.
4. Suba a `01_ENTRADA` un archivo bien nombrado y otro mal nombrado, y vuelva a correr **ETL diaria**. El primero debe quedar en su carpeta oficial y el segundo en `99_RECHAZADOS`, con el motivo en **Detalles → Descripción**.

En repositorios públicos los minutos de Actions son gratuitos y sin límite. GitHub apaga los workflows programados de un repositorio público después de 60 días sin actividad, así que el workflow **Mantener activo** deja una marca cada mes para evitarlo.

**Seguridad del repositorio público**
- En **Settings → Actions → General**, marque **Require approval for all outside collaborators** en "Fork pull request workflows".
- En **Settings → Branches**, proteja `main` para que nadie más pueda hacer push.

## 6. Permisos en Drive

| Carpeta | Equipo de obra | Contratistas | Director y suplente |
|---|---|---|---|
| `01_ENTRADA`, `00_MIGRACION` | Editor | Editor (solo estas) | Editor |
| Carpetas oficiales (`P...`) | Lector | Sin acceso, o lector de su proyecto | Editor |
| `99_RECHAZADOS`, `99_POR_REVISAR` | Lector | Sin acceso | Editor |
| `TABLA_MAESTRA_PEI` | Lector | Sin acceso | Editor |
| `98_RESPALDOS` | Sin acceso | Sin acceso | Editor |

En **Compartir**, desactive "Cualquier persona con el enlace" en todas las carpetas.

## 7. Correr en su computador

La migración se recomienda correrla en el computador (ver `migracion_local.md`).

```bash
cp .env.example .env        # y llene los valores
pip install -r requirements.txt
python -m etl validar P003-PEI-E02-F01-CAR-25-10-2026-01.txt
python -m etl diario
```
