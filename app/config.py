import os
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_ENV = RAIZ / ".env"


def _cargar_env(ruta: Path = ARCHIVO_ENV) -> None:
    """Lee el .env de la raiz del proyecto. Una variable ya definida en el sistema gana."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave, valor)


_cargar_env()

# --- Datos del evento -------------------------------------------------------
NOVIA = "Sofía"
NOVIO = "Matías"
HASHTAG = "#SofiYMati2026"

TZ = ZoneInfo("America/Argentina/Mendoza")
FECHA_ISO = "2026-12-20T16:45:00-03:00"
FECHA_TEXTO = "Domingo 20 de diciembre de 2026"

CEREMONIA = {
    "titulo": "Ceremonia religiosa",
    "hora": "16:45",
    "lugar": "Parroquia Sagrado Corazón de Jesús",
    "direccion": "Videla Aranda, Cruz de Piedra, Maipú, Mendoza",
    "maps": "https://maps.google.com/?q=Parroquia+Sagrado+Corazon+de+Jesus+Cruz+de+Piedra+Maipu+Mendoza",
}
RECEPCION = {
    "titulo": "Recepción",
    "hora": "18:30",
    "lugar": "Luna India",
    "direccion": "Castro Barros, Mendoza",
    "maps": "https://maps.google.com/?q=Luna+India+Castro+Barros+Mendoza",
}
ITINERARIO = [
    ("16:45", "Ceremonia religiosa"),
    ("18:30", "Recepción y brindis de bienvenida"),
    ("20:00", "Cena"),
    ("22:30", "Baile y fiesta"),
    ("02:30", "Fin de fiesta"),
]
DRESS_CODE = "Formal elegante, fresco y cómodo para festejar al aire libre."
REGALOS_ALIAS = "Bodasofi.mati"
REGALOS_URL = "https://link.mercadopago.com.ar/bodasofimati"

# --- Configuración técnica --------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
PUERTO = int(os.getenv("PUERTO", "8000"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "boda2026")
SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esta-clave-en-produccion")
DB_URL = os.getenv("DB_URL", "sqlite:///data/boda.db")
FECHA_LIMITE_RSVP = "2026-11-20"
