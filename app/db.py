import secrets
import string
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from app import config

Path("data").mkdir(exist_ok=True)
engine = create_engine(config.DB_URL, connect_args={"check_same_thread": False})

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I, O, 0, 1


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrar()


def _migrar() -> None:
    """Agrega columnas nuevas a bases ya creadas (SQLite no lo hace solo)."""
    from sqlalchemy import text

    nuevas = {
        "tarjeta_fisica": "BOOLEAN NOT NULL DEFAULT 0",
    }
    with engine.begin() as con:
        existentes = {fila[1] for fila in con.execute(text("PRAGMA table_info(invitacion)"))}
        for columna, tipo in nuevas.items():
            if columna not in existentes:
                con.execute(text(f"ALTER TABLE invitacion ADD COLUMN {columna} {tipo}"))


def get_session():
    with Session(engine) as session:
        yield session


def nuevo_codigo(session: Session) -> str:
    from app.models import Invitacion
    from sqlmodel import select

    while True:
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(6))
        existe = session.exec(select(Invitacion).where(Invitacion.codigo == codigo)).first()
        if not existe:
            return codigo
