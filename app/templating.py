import os
from typing import List, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import config, security, servicios
from app.models import Estado, Tipo

templates = Jinja2Templates(directory=str(config.RAIZ / "app" / "templates"))


def estatico(ruta: str) -> str:
    """Agrega ?v=<fecha de modificacion> para que el navegador no sirva CSS/JS viejo."""
    limpio = ruta.lstrip("/")
    local = os.path.join(config.RAIZ, "app", limpio)
    try:
        marca = int(os.path.getmtime(local))
    except OSError:
        marca = 0
    return "/" + limpio + "?v=" + str(marca)


MAX_DETALLES_AVISO = 10  # la sesion viaja en una cookie: no guardar listas largas


def avisar(request: Request, texto: str, tipo: str = "error", detalles: Optional[List[str]] = None) -> None:
    """Deja un mensaje para la proxima pagina que se muestre (sobrevive al redirect)."""
    detalles = list(detalles or [])
    if len(detalles) > MAX_DETALLES_AVISO:
        resto = len(detalles) - MAX_DETALLES_AVISO
        detalles = detalles[:MAX_DETALLES_AVISO] + [f"… y {resto} más."]
    pendientes = request.session.get("avisos", [])
    pendientes.append({"tipo": tipo, "texto": texto, "detalles": detalles})
    request.session["avisos"] = pendientes


def avisos(request: Request) -> List[dict]:
    """Devuelve y consume los mensajes pendientes (se llama desde los templates)."""
    if "session" not in request.scope:
        return []
    return request.session.pop("avisos", [])


templates.env.globals["cfg"] = config
templates.env.globals["Estado"] = Estado
templates.env.globals["Tipo"] = Tipo
templates.env.globals["estatico"] = estatico
templates.env.globals["avisos"] = avisos
templates.env.globals["largo"] = servicios.LARGO_MAX
templates.env.globals["rsvp_abierto"] = servicios.rsvp_abierto
templates.env.globals["fecha_limite_rsvp"] = servicios.fecha_limite_texto
templates.env.globals["es_staff"] = security.es_staff
