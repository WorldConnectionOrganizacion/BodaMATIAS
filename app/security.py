import hashlib
import hmac
import secrets
import threading
import time
from collections import deque
from typing import Deque, Dict
from urllib.parse import quote, urlsplit

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException

from app import config

MAX_INTENTOS = 5            # contraseñas incorrectas seguidas por IP...
BLOQUEO_SEG = 5 * 60        # ...dentro de esta ventana, y el bloqueo que generan

_fallidos: Dict[str, Deque[float]] = {}
_candado = threading.Lock()  # los endpoints sync corren en varios hilos


class NoAutorizado(HTTPException):
    def __init__(self, destino: str = "/admin/login"):
        super().__init__(status_code=307, detail="login")
        self.destino = destino


def _huella() -> str:
    """Firma de la contraseña guardada en la sesion: si se cambia, todas las sesiones dejan de valer."""
    datos = config.ADMIN_PASSWORD.encode("utf-8")
    return hmac.new(config.SECRET_KEY.encode("utf-8"), datos, hashlib.sha256).hexdigest()[:32]


def es_staff(request: Request) -> bool:
    sesion = request.session
    return (
        bool(sesion.get("staff"))
        and bool(config.ADMIN_PASSWORD)
        and hmac.compare_digest(sesion.get("huella", ""), _huella())
    )


def _volver_a(request: Request) -> str:
    """Pagina a la que volver despues del login."""
    if request.method in ("GET", "HEAD"):
        url = request.url
        return destino_seguro(url.path + (f"?{url.query}" if url.query else ""))
    # Un formulario enviado con la sesion vencida no se puede repetir despues del login (seria un
    # GET a una ruta que solo acepta POST): se vuelve a la pagina desde la que se envio.
    origen = urlsplit(request.headers.get("referer", ""))
    if origen.netloc == request.url.netloc and origen.path:
        return destino_seguro(origen.path + (f"?{origen.query}" if origen.query else ""))
    return "/admin"


def requiere_staff(request: Request):
    """Dependencia FastAPI: corta con redirect a login si no hay sesión staff."""
    if not es_staff(request):
        destino = "/admin/login?next=" + quote(_volver_a(request), safe="")
        if request.method not in ("GET", "HEAD"):
            destino += "&vencida=1"  # lo enviado no se guardo: el login lo avisa
        raise NoAutorizado(destino=destino)
    return True


def destino_seguro(destino: str) -> str:
    """Solo rutas internas: evita que ?next= mande a otro sitio despues del login."""
    if (
        destino.startswith("/")
        and not destino.startswith("//")
        and "\\" not in destino
        and all(ord(c) > 32 for c in destino)  # el navegador descarta tabs/saltos: "/\t/x" = "//x"
    ):
        return destino
    return "/admin"


def _ip(request: Request) -> str:
    if config.DETRAS_DE_PROXY:
        # El proxy agrega la IP que ve al final de X-Forwarded-For. Lo anterior lo puede
        # inventar el cliente para esquivar el bloqueo, asi que se toma solo el ultimo valor.
        reenviadas = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
        if reenviadas:
            return reenviadas[-1]
    return request.client.host if request.client else "desconocida"


def _recientes(ip: str, ahora: float) -> Deque[float]:
    """Fallos de esa IP dentro de la ventana. Llamar con el candado tomado."""
    cola = _fallidos.get(ip, deque())
    while cola and ahora - cola[0] > BLOQUEO_SEG:
        cola.popleft()
    if not cola:
        _fallidos.pop(ip, None)
    return cola


def bloqueado(request: Request) -> bool:
    with _candado:
        return len(_recientes(_ip(request), time.monotonic())) >= MAX_INTENTOS


def login(request: Request, password: str) -> bool:
    esperada = config.ADMIN_PASSWORD
    # Sin contraseña configurada nadie entra (ni siquiera enviando una vacia).
    ok = bool(esperada) and secrets.compare_digest(password.encode("utf-8"), esperada.encode("utf-8"))
    ip, ahora = _ip(request), time.monotonic()
    with _candado:
        if ok:
            _fallidos.pop(ip, None)
        else:
            cola = _recientes(ip, ahora)
            cola.append(ahora)
            _fallidos[ip] = cola
            if len(_fallidos) > 10_000:  # no acumular IPs viejas en memoria
                for otra in list(_fallidos):
                    _recientes(otra, ahora)
    if not ok:
        return False
    request.session.clear()  # no arrastrar nada de una sesion anterior
    request.session["staff"] = True
    request.session["huella"] = _huella()
    return True


def logout(request: Request) -> None:
    request.session.clear()


def redirect_login(exc: NoAutorizado) -> RedirectResponse:
    return RedirectResponse(exc.destino, status_code=303)
