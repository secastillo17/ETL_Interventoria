# Migración desde el computador

La migración de lo existente se corre en el computador con el mismo programa. El trabajo diario lo sigue haciendo GitHub Actions. No es otra ETL: son los modos `inventario`, `migracion-propuesta` y `migracion-aplicar` del mismo código, con las mismas validaciones.

**Por qué en el computador**
- Los archivos antiguos están en discos, USB y computadores. Desde ahí se suben a Drive, cosa que GitHub no puede hacer.
- La migración recorre cientos de archivos históricos. Corriéndola en local, sus registros no quedan en las ejecuciones públicas del repositorio.
- Se puede hacer por lotes, pausar y retomar sin el límite de 6 horas por ejecución de Actions.

Los gigas no pasan por GitHub en ningún caso. Mover y copiar dentro de Drive ocurre en los servidores de Google, y solo se descargan las carteras y cantidades pequeñas para leer pistas.

## 1. Preparar el computador (una vez)

En Windows, desde PowerShell:

```powershell
git clone https://github.com/<organizacion>/pei-etl.git
cd pei-etl
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**Credencial propia para la migración.** No use el mismo token de GitHub.
1. En Google Cloud, vaya a **Clients → Create client** y cree un segundo cliente web llamado `ETL local`, con la misma URI de redirección del Playground.
2. Saque su refresh token con el paso 4 de `credenciales.md`.
3. Llene el `.env` con ese cliente, la misma `DATABASE_URL` del rol `etl_escritura`, `DRIVE_RAIZ_ID` y `TABLA_MAESTRA_ID`.

Al terminar la migración se borra ese cliente y el `.env`, y la ETL diaria sigue funcionando con el suyo.

## 2. Inventario de cada disco o USB

```powershell
python -m etl inventario "E:\" --salida inventario_USB_topografo1.csv
```

El CSV muestra ruta, tamaño, fecha y huella (md5) de cada archivo, y marca las copias repetidas. Así cada persona sube una sola copia de cada archivo.

## 3. Subir a 00_MIGRACION

Use **Google Drive para escritorio** con la cuenta de la empresa. Reanuda solo si se corta la conexión, cosa importante con planos de varios GB.

Cree una subcarpeta por persona y origen, por ejemplo `00_MIGRACION/Topografo1_USB/`. Los nombres de carpeta también sirven de pista para la clasificación.

## 4. Propuesta

```powershell
python -m etl migracion-propuesta
```

Deja en `02_REVISION_MIGRACION` la hoja `REVISION_MIGRACION_<fecha>`. Para ver el detalle archivo por archivo en pantalla, use `$env:LOG_NIVEL="DEBUG"` antes del comando.

## 5. Revisión

- Cada persona filtra la columna `responsable` por su correo, corrige y elige `MIGRAR`, `DESCARTAR` o `PENDIENTE`.
- El director escribe `SI` en `aprobado_director`.

## 6. Aplicar

```powershell
python -m etl migracion-aplicar
```

Solo mueve las filas con `MIGRAR` + `SI` y deja la hoja `RESULTADO_...` con lo que pasó en cada fila. Las filas con error se corrigen en la hoja y se vuelve a aplicar. Las ya migradas no se repiten, porque ya no están en `00_MIGRACION`.

No lo corra entre las 6:40 y las 7:00 p. m., que es cuando corre la ETL diaria.

## 7. Cierre

1. Repita los pasos 2 a 6 por lotes (un proyecto o una persona a la vez) hasta vaciar `00_MIGRACION`.
2. Borre el cliente `ETL local` en Google Cloud y el archivo `.env`.
3. Los indicadores de la migración quedan en `reporte.v_indicadores` (`archivos_migrados`, `migracion_pendiente`) y en `ctrl.migracion_item`.
