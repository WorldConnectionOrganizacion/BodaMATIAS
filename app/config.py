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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "boda2026")  # solo se usa si falta ADMIN_USUARIOS
SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esta-clave-en-produccion")


def _leer_usuarios(crudo: str, clave_compartida: str) -> dict:
    """ADMIN_USUARIOS=Nombre:clave,Nombre:clave  (una cuenta por persona del staff).

    La clave puede tener ':' pero no ','. Sin ADMIN_USUARIOS queda una sola cuenta 'admin'
    con ADMIN_PASSWORD, para no dejar afuera a nadie mientras se configura.
    """
    usuarios = {}
    for numero, par in enumerate(crudo.split(","), start=1):
        if not par.strip():
            continue
        nombre, separador, clave = par.partition(":")
        nombre, clave = " ".join(nombre.split()), clave.strip()
        if not separador or not nombre or not clave:
            # sin mostrar el texto: podria contener una clave
            raise ValueError(f"ADMIN_USUARIOS: la entrada número {numero} no tiene el formato Nombre:clave.")
        if nombre.casefold() in (n.casefold() for n in usuarios):
            raise ValueError(f"ADMIN_USUARIOS: el usuario '{nombre}' está repetido.")
        usuarios[nombre] = clave
    return usuarios or {"admin": clave_compartida}


ADMIN_USUARIOS_DEFINIDOS = bool(os.getenv("ADMIN_USUARIOS", "").strip())
try:
    ADMIN_USUARIOS = _leer_usuarios(os.getenv("ADMIN_USUARIOS", ""), ADMIN_PASSWORD)
except ValueError as e:
    raise SystemExit(f"Error de configuracion en .env: {e}")
EN_RAILWAY = any(os.getenv(v) for v in (
    "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"))
RAILWAY_VOLUMEN = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
# En Railway el disco del contenedor se borra en cada deploy: si hay un Volume montado, la base va ahi.
CARPETA_DATOS = Path(RAILWAY_VOLUMEN) if RAILWAY_VOLUMEN else RAIZ / "data"
DB_URL = os.getenv("DB_URL", "sqlite:///" + (CARPETA_DATOS / "boda.db").as_posix())
# Detras de un proxy (Railway) la IP real del cliente llega en X-Forwarded-For.
DETRAS_DE_PROXY = os.getenv("DETRAS_DE_PROXY", "1" if EN_RAILWAY else "0") == "1"
FECHA_LIMITE_RSVP = "2026-11-20"
