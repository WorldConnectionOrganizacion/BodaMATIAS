import secrets
import string
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel, Session, create_engine

from app import config

_archivo_base = make_url(config.DB_URL).database
if _archivo_base and _archivo_base != ":memory:":
    Path(_archivo_base).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(config.DB_URL, connect_args={"check_same_thread": False, "timeout": 15})


@event.listens_for(engine, "connect")
def _pragmas_sqlite(conexion, _registro) -> None:
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")   # SQLite no valida claves foraneas si no se pide
    cursor.execute("PRAGMA journal_mode=WAL")  # leer no bloquea al que escribe (RSVP simultaneos)
    cursor.close()

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
