# Operación y seguridad

Los controles se basan en CIS Controls v8.1 (grupo IG1), NIST CSF 2.0 (guía para pequeñas empresas) y la Ley 1581 de 2012.

## Controles básicos de la cuenta de la empresa

- **Verificación en dos pasos** activa en la cuenta de Google de la empresa, con códigos de respaldo guardados por el director.
- **Contraseñas** de Neon, Google y GitHub en un gestor de contraseñas, nunca en documentos, chats ni el repositorio.
- **Enlaces públicos.** Ninguna carpeta se comparte con "Cualquier persona con el enlace".
- **Revisión trimestral de accesos.** El director revisa quién tiene acceso a las carpetas de Drive, a la tabla maestra, a la organización de GitHub y a Neon, y retira a quien ya no trabaja con PEI.

## Retiro de una persona del equipo o de un contratista

1. Quítela de las carpetas compartidas de Drive.
2. En la tabla maestra, deje su fila de PERSONAS o CONTRATISTAS, porque conserva la trazabilidad. Cierre los frentes con fecha fin.
3. Retírela de la organización de GitHub, si estaba.
4. Lo que subió sigue siendo oficial, porque es una copia a nombre de la empresa.

## Si se sospecha que un secreto se filtró

1. **Refresh token de Google.**
   - Revóquelo en <https://myaccount.google.com/permissions> (PEI ETL → Quitar acceso).
   - Genere uno nuevo con el paso 4 de `credenciales.md`.
   - Actualice el secreto `GOOGLE_REFRESH_TOKEN`.
2. **Client secret.** En Google Cloud, vaya a **Clients → ETL GitHub**, agregue un secreto nuevo, borre el anterior y actualice `GOOGLE_CLIENT_SECRET`.
3. **Clave de Neon.** En Neon, vaya a **Roles → etl_escritura → Reset password** y actualice `DATABASE_URL`. Si se trata de `lector_looker`, actualice la clave en las fuentes de Looker.
4. Revise en `ctrl.evento` y en el historial de versiones de Drive si hubo cambios no esperados.
5. Registre el incidente en la bitácora de incidencias del proyecto.

## Respaldo y recuperación

- **Semanal y automático.** El respaldo guarda la base en CSV, la tabla maestra y el inventario de integridad en `98_RESPALDOS` y como artefacto de GitHub, que se conserva 90 días.
- **Mensual y manual.** El director descarga con **Google Takeout** la carpeta `PEI_REPOSITORIO` a un disco externo que no quede conectado al computador, para tener una copia fuera de Google.
- **Recuperar un archivo.** Las versiones anteriores están en `_HISTORICO` de cada carpeta de tipo. Lo borrado está 30 días en la papelera de Drive.
- **Recuperar la base.** Hay dos caminos. Neon permite restaurar la rama a un punto anterior, dentro de la ventana de historial del plan. Los CSV del respaldo también se pueden volver a cargar.

## Alertas del respaldo de integridad

Si el respaldo reporta `MD5 DISTINTO`, `EN PAPELERA` o `NO ENCONTRADO`, un archivo oficial cambió por fuera del flujo. El caso queda en `ctrl.evento` con acción `integridad` y la corrida de Actions termina en rojo.

1. Busque el archivo en Drive.
2. Restáurelo desde la papelera o desde el historial de versiones de Drive.
3. Si el cambio era legítimo, súbalo de nuevo por `01_ENTRADA` como versión nueva.

## Si la ETL diaria falla

GitHub envía un correo al dueño del repositorio cuando una corrida termina en rojo.

1. Abra la corrida en **Actions** y revise el registro.
2. Errores frecuentes:
   - **Credenciales vencidas.** Repita el paso 4 de `credenciales.md`.
   - **Tabla maestra con errores.** El registro dice qué hoja o columna falta.
   - **Neon suspendido.** Vuelva a correr la ETL.
3. Los archivos que fallaron siguen en `01_ENTRADA` y se procesan en la siguiente corrida. No se pierde nada.
