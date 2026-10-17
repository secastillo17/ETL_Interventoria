"""
Inventario LOCAL (se corre en el computador, no en Actions).

Antes de la migración, cada persona corre esto sobre sus discos, USB o
carpetas del computador. Genera un CSV con ruta, tamaño, fechas y md5 de
cada archivo, y marca los duplicados. El md5 es el mismo que calcula
Google Drive, así que después se puede saber qué ya está en la nube.

    python -m etl inventario "D:/Proyectos" --salida inventario_disco_D.csv
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path

IGNORAR = {"thumbs.db", "desktop.ini", ".ds_store"}


def md5_de(ruta: Path) -> str:
    h = hashlib.md5()  # noqa: S324  (se usa como huella, igual que Drive)
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def ejecutar(carpeta: Path, salida: Path) -> Path:
    filas = []
    for ruta in sorted(Path(carpeta).rglob("*")):
        if not ruta.is_file() or ruta.name.lower() in IGNORAR or ruta.name.startswith("~$"):
            continue
        st = ruta.stat()
        try:
            huella = md5_de(ruta)
        except OSError as exc:
            huella = f"ERROR: {exc}"
        filas.append({"ruta": str(ruta.parent.relative_to(carpeta)), "nombre": ruta.name,
                      "extension": ruta.suffix.lower(), "tamano_mb": round(st.st_size / 1048576, 3),
                      "modificado": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                      "md5": huella})
    grupos = defaultdict(list)
    for f in filas:
        grupos[f["md5"]].append(f)
    for f in filas:
        g = grupos[f["md5"]]
        f["duplicados"] = len(g) - 1
        f["primera_copia"] = "" if g[0] is f else f"{g[0]['ruta']}/{g[0]['nombre']}"
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]) if filas else ["ruta"], delimiter=";")
        w.writeheader()
        w.writerows(filas)
    unicos = len(grupos)
    print(f"{len(filas)} archivos, {unicos} contenidos distintos, "
          f"{len(filas) - unicos} copias repetidas. Inventario en {salida}")
    return salida
