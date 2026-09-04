from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException

from app import config


class NoAutorizado(HTTPException):
    def __init__(self, destino: str = "/admin/login"):
        super().__init__(status_code=307, detail="login")
        self.destino = destino


def es_staff(request: Request) -> bool:
    return bool(request.session.get("staff"))


def requiere_staff(request: Request):
    """Dependencia FastAPI: corta con redirect a login si no hay sesión staff."""
    if not es_staff(request):
        raise NoAutorizado(destino=f"/admin/login?next={request.url.path}")
    return True


def login(request: Request, password: str, operador: str = "") -> bool:
    if password == config.ADMIN_PASSWORD:
        request.session["staff"] = True
        request.session["operador"] = operador or "staff"
        return True
    return False


def logout(request: Request) -> None:
    request.session.clear()


def redirect_login(exc: NoAutorizado) -> RedirectResponse:
    return RedirectResponse(exc.destino, status_code=303)
