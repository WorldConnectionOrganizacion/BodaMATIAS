from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


class Estado(str, Enum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    parcial = "parcial"
    rechazada = "rechazada"


class Tipo(str, Enum):
    adulto = "adulto"
    nino = "nino"


class Invitacion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(index=True, unique=True)
    nombre_grupo: str
    cupo_adultos: int = 0
    cupo_ninos: int = 0
    telefono: Optional[str] = None
    email: Optional[str] = None
    tarjeta_fisica: bool = Field(default=False)  # se entrega impresa, no solo por link
    estado: Estado = Field(default=Estado.pendiente)
    mensaje: Optional[str] = None
    notas: Optional[str] = None
    creada_at: datetime = Field(default_factory=datetime.utcnow)
    respondida_at: Optional[datetime] = None

    invitados: List["Invitado"] = Relationship(
        back_populates="invitacion",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    checkins: List["Checkin"] = Relationship(
        back_populates="invitacion",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # --- helpers ---
    @property
    def cupo_total(self) -> int:
        return self.cupo_adultos + self.cupo_ninos

    @property
    def confirmados(self) -> int:
        return sum(1 for i in self.invitados if i.asiste is True)

    @property
    def ingresados(self) -> int:
        return sum(c.personas for c in self.checkins)

    @property
    def respondio(self) -> bool:
        return self.estado != Estado.pendiente


class Invitado(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invitacion_id: int = Field(foreign_key="invitacion.id", index=True)
    nombre: str = ""
    tipo: Tipo = Field(default=Tipo.adulto)
    asiste: Optional[bool] = None
    restriccion: Optional[str] = None

    invitacion: Optional[Invitacion] = Relationship(back_populates="invitados")


class Checkin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invitacion_id: int = Field(foreign_key="invitacion.id", index=True)
    personas: int = 1
    at: datetime = Field(default_factory=datetime.utcnow)
    operador: Optional[str] = None

    invitacion: Optional[Invitacion] = Relationship(back_populates="checkins")
