"""
Validador del estándar de nombres de PEI.

    PROYECTO-ORIGEN-ETAPA-FRENTE-TIPO-DD-MM-AAAA-NN.ext
    P003-PEI-E02-F01-CAR-25-10-2026-01.txt

Nueve partes separadas por guiones. ORIGEN es PEI cuando el archivo lo
produce la interventoría, o el código de tres letras del contratista
cuando lo entrega él. ZZ en ETAPA o FRENTE significa "general o varios"
(planos generales, informe mensual). La versión no va en el nombre: la
asigna la ETL.

Este módulo solo revisa la FORMA del nombre. Que el proyecto, la etapa,
el frente y el origen existan y concuerden lo revisa tabla_maestra.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePosixPath
from typing import List, Optional

TIPOS = {
    "CAR": "Cartera de campo",
    "MED": "Medición o levantamiento",
    "CMH": "Control de pozos (MH)",
    "CNT": "Cantidades de obra",
    "PRE": "Presupuesto",
    "FOT": "Registro fotográfico",
    "PLA": "Plano",
    "PAC": "Preacta",
    "INF": "Informe",
    "SOP": "Soporte de avance",
}

# Extensiones aceptadas por tipo. Un plano en .xlsx o una foto en .txt
# casi siempre es un error de nombre, así que se rechaza con el motivo.
EXTENSIONES_POR_TIPO = {
    "CAR": {".txt", ".csv", ".xlsx", ".xls", ".pdf"},
    "MED": {".txt", ".csv", ".xlsx", ".xls", ".pdf", ".dwg", ".dxf"},
    "CMH": {".xlsx", ".xls", ".csv", ".pdf"},
    "CNT": {".xlsx", ".xls", ".csv", ".pdf"},
    "PRE": {".xlsx", ".xls", ".pdf"},
    "FOT": {".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov"},
    "PLA": {".dwg", ".dxf", ".pdf"},
    "PAC": {".xlsx", ".xls", ".pdf", ".docx"},
    "INF": {".pdf", ".docx", ".xlsx"},
    "SOP": {".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls", ".docx", ".zip"},
}

GENERAL = "ZZ"
ORIGEN_INTERNO = "PEI"
DIAS_ALERTA_FECHA_ANTIGUA = 60

_PATRONES = [
    ("proyecto", re.compile(r"^P\d{3}$"), "el proyecto debe ser P y tres dígitos (P003)"),
    ("origen", re.compile(r"^[A-Z]{3}$"), "el origen debe ser PEI o el código de tres letras del contratista"),
    ("etapa", re.compile(r"^(E\d{2}|ZZ)$"), "la etapa debe ser E y dos dígitos (E02) o ZZ"),
    ("frente", re.compile(r"^(F\d{2}|ZZ)$"), "el frente debe ser F y dos dígitos (F01) o ZZ"),
    ("tipo", re.compile(r"^[A-Z]{3}$"), "el tipo debe ser un código de tres letras"),
    ("dia", re.compile(r"^\d{2}$"), "el día debe tener dos dígitos"),
    ("mes", re.compile(r"^\d{2}$"), "el mes debe tener dos dígitos"),
    ("anio", re.compile(r"^\d{4}$"), "el año debe tener cuatro dígitos"),
    ("consecutivo", re.compile(r"^\d{2}$"), "el consecutivo debe tener dos dígitos (01)"),
]


@dataclass
class NombreValidado:
    nombre_original: str
    valido: bool = False
    motivos: List[str] = field(default_factory=list)   # si no es válido, por qué
    avisos: List[str] = field(default_factory=list)    # válido, pero conviene revisar
    proyecto: Optional[str] = None
    origen: Optional[str] = None
    etapa: Optional[str] = None
    frente: Optional[str] = None
    tipo: Optional[str] = None
    fecha: Optional[date] = None
    consecutivo: Optional[int] = None
    extension: str = ""

    @property
    def nombre_base(self) -> str:
        """Los nueve campos sin extensión: es la llave que identifica al
        documento a lo largo de sus versiones."""
        if not self.valido:
            return ""
        return construir_nombre(self.proyecto, self.origen, self.etapa, self.frente,
                                self.tipo, self.fecha, self.consecutivo)


def construir_nombre(proyecto, origen, etapa, frente, tipo, fecha: date,
                     consecutivo: int, extension: str = "") -> str:
    return (f"{proyecto}-{origen}-{etapa}-{frente}-{tipo}-"
            f"{fecha:%d-%m-%Y}-{int(consecutivo):02d}{extension}")


def validar_nombre(nombre_archivo: str, hoy: Optional[date] = None) -> NombreValidado:
    hoy = hoy or date.today()
    r = NombreValidado(nombre_original=nombre_archivo)

    ruta = PurePosixPath(nombre_archivo.strip())
    r.extension = ruta.suffix.lower()
    base = ruta.stem if r.extension else ruta.name

    if not r.extension:
        r.motivos.append("el archivo no tiene extensión")

    if base != base.upper():
        r.motivos.append("el nombre debe ir en mayúsculas")
        base = base.upper()
    if " " in base or "_" in base:
        r.motivos.append("el nombre no debe tener espacios ni guiones bajos, solo guiones")

    partes = base.split("-")
    if len(partes) != 9:
        r.motivos.append(f"debe tener 9 partes separadas por guiones y tiene {len(partes)}")
        return r

    valores = {}
    for (campo, patron, mensaje), valor in zip(_PATRONES, partes):
        if not patron.match(valor):
            r.motivos.append(f"{mensaje}, se encontró '{valor}'")
        valores[campo] = valor

    if valores["tipo"] not in TIPOS and re.match(r"^[A-Z]{3}$", valores["tipo"]):
        r.motivos.append(f"el tipo '{valores['tipo']}' no está en la lista cerrada")

    fecha = None
    try:
        fecha = date(int(valores["anio"]), int(valores["mes"]), int(valores["dia"]))
    except ValueError:
        r.motivos.append(f"la fecha {valores['dia']}-{valores['mes']}-{valores['anio']} no existe")

    if fecha:
        if fecha > hoy:
            r.motivos.append(f"la fecha {fecha:%d-%m-%Y} es futura")
        elif (hoy - fecha).days > DIAS_ALERTA_FECHA_ANTIGUA:
            r.avisos.append(
                f"la fecha {fecha:%d-%m-%Y} tiene más de {DIAS_ALERTA_FECHA_ANTIGUA} días; "
                "confirmar que el día y el mes no estén invertidos"
            )

    if valores["consecutivo"] == "00":
        r.motivos.append("el consecutivo empieza en 01")

    tipo = valores["tipo"]
    if tipo in EXTENSIONES_POR_TIPO and r.extension and r.extension not in EXTENSIONES_POR_TIPO[tipo]:
        r.motivos.append(
            f"la extensión {r.extension} no corresponde al tipo {tipo} "
            f"(se esperan {', '.join(sorted(EXTENSIONES_POR_TIPO[tipo]))})"
        )

    if r.motivos:
        return r

    r.valido = True
    r.proyecto, r.origen, r.etapa, r.frente, r.tipo = (
        valores["proyecto"], valores["origen"], valores["etapa"], valores["frente"], tipo)
    r.fecha = fecha
    r.consecutivo = int(valores["consecutivo"])
    return r
