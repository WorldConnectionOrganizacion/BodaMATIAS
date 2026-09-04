import os

from fastapi.templating import Jinja2Templates

from app import config
from app.models import Estado, Tipo

templates = Jinja2Templates(directory="app/templates")


def estatico(ruta: str) -> str:
    """Agrega ?v=<fecha de modificacion> para que el navegador no sirva CSS/JS viejo."""
    limpio = ruta.lstrip("/")
    local = os.path.join("app", limpio)
    try:
        marca = int(os.path.getmtime(local))
    except OSError:
        marca = 0
    return "/" + limpio + "?v=" + str(marca)


templates.env.globals["cfg"] = config
templates.env.globals["Estado"] = Estado
templates.env.globals["Tipo"] = Tipo
templates.env.globals["estatico"] = estatico
