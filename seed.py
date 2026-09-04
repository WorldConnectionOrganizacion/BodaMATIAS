"""Carga datos de ejemplo para probar el sistema.

Uso:  python seed.py
"""
from sqlmodel import Session, select

from app.db import engine, init_db, nuevo_codigo
from app.models import Invitacion, Invitado, Tipo

EJEMPLOS = [
    ("Familia Pérez", 2, 1, "5492611111111"),
    ("Juan y Carla", 2, 0, "5492612222222"),
    ("Tíos de Mendoza", 4, 2, ""),
    ("Lucía Gómez", 1, 0, ""),
]


def main() -> None:
    init_db()
    with Session(engine) as s:
        for nombre, adultos, ninos, tel in EJEMPLOS:
            existe = s.exec(select(Invitacion).where(Invitacion.nombre_grupo == nombre)).first()
            if existe:
                continue
            inv = Invitacion(
                codigo=nuevo_codigo(s),
                nombre_grupo=nombre,
                cupo_adultos=adultos,
                cupo_ninos=ninos,
                telefono=tel or None,
            )
            s.add(inv)
            s.commit()
            s.refresh(inv)
            for _ in range(adultos):
                s.add(Invitado(invitacion_id=inv.id, tipo=Tipo.adulto))
            for _ in range(ninos):
                s.add(Invitado(invitacion_id=inv.id, tipo=Tipo.nino))
            s.commit()
            print(f"{inv.nombre_grupo}: /i/{inv.codigo}")


if __name__ == "__main__":
    main()
