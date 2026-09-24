"""Carga directa de invitaciones exportadas (con codigo, estado y fechas ya definidos).

A diferencia de la importacion del panel (que siempre genera codigo nuevo y estado
pendiente), este script preserva los datos tal cual vienen en el CSV: pensado para migrar
o restaurar invitaciones ya existentes.

Uso:  python scripts/importar_invitaciones.py data/importar/invitaciones.csv
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Estado, Invitacion, Invitado, Tipo


def _fecha(texto: str) -> datetime:
    return datetime.strptime(texto.strip(), "%Y-%m-%d %H:%M:%S.%f")


def _opcional(texto: str) -> str | None:
    texto = (texto or "").strip()
    return texto or None


def cargar(ruta: Path) -> None:
    init_db()
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))

    creadas = omitidas = 0
    with Session(engine) as s:
        for fila in filas:
            codigo = fila["codigo"].strip().upper()
            if s.exec(select(Invitacion).where(Invitacion.codigo == codigo)).first():
                omitidas += 1
                print(f"  ya existe, se omite: {codigo} {fila['nombre_grupo']}")
                continue

            inv = Invitacion(
                codigo=codigo,
                nombre_grupo=fila["nombre_grupo"].strip(),
                cupo_adultos=int(fila["cupo_adultos"]),
                cupo_ninos=int(fila["cupo_ninos"]),
                telefono=_opcional(fila["telefono"]),
                email=_opcional(fila["email"]),
                estado=Estado(fila["estado"].strip()),
                mensaje=_opcional(fila["mensaje"]),
                notas=_opcional(fila["notas"]),
                creada_at=_fecha(fila["creada_at"]),
                respondida_at=_fecha(fila["respondida_at"]) if _opcional(fila["respondida_at"]) else None,
                tarjeta_fisica=fila["tarjeta_fisica"].strip() == "1",
            )
            s.add(inv)
            s.commit()
            s.refresh(inv)
            for _ in range(inv.cupo_adultos):
                s.add(Invitado(invitacion_id=inv.id, tipo=Tipo.adulto))
            for _ in range(inv.cupo_ninos):
                s.add(Invitado(invitacion_id=inv.id, tipo=Tipo.nino))
            s.commit()
            creadas += 1
            print(f"  creada: {codigo} {inv.nombre_grupo} -> /i/{codigo}")

    print(f"\nListo. {creadas} creadas, {omitidas} omitidas (ya existian).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/importar_invitaciones.py <archivo.csv>")
    cargar(Path(sys.argv[1]))
