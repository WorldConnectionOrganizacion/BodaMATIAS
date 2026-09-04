from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app import config, qrgen, security
from app.admin import router as admin_router
from app.db import get_session, init_db
from app.models import Checkin, Estado, Invitacion, Invitado, Tipo
from app.security import NoAutorizado, requiere_staff
from app.templating import templates

app = FastAPI(title="Boda Sofía & Matías", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=60 * 60 * 12)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(admin_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    print(f"BASE_URL en uso: {config.BASE_URL}  (los QR codifican {config.BASE_URL}/i/CODIGO)")
    publico = not any(x in config.BASE_URL for x in ("localhost", "127.0.0.1", "192.168.", "10.0."))
    if publico and config.ADMIN_PASSWORD == "boda2026":
        print("AVISO: la app esta publicada y ADMIN_PASSWORD sigue siendo la de ejemplo. Cambiala.")
    if publico and config.SECRET_KEY == "cambiar-esta-clave-en-produccion":
        print("AVISO: SECRET_KEY es la de ejemplo: las sesiones del panel se pueden falsificar.")
    if config.BASE_URL.startswith("http://") and publico:
        print("AVISO: sin HTTPS el escaner por camara no funciona (usar carga manual del codigo).")


@app.exception_handler(NoAutorizado)
async def _no_autorizado(request: Request, exc: NoAutorizado):
    return security.redirect_login(exc)


def _buscar(session: Session, codigo: str) -> Optional[Invitacion]:
    return session.exec(
        select(Invitacion).where(Invitacion.codigo == codigo.strip().upper())
    ).first()


# --- Invitación pública -----------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Invitación general, sin datos personales ni RSVP."""
    return templates.TemplateResponse(
        "invitacion.html",
        {"request": request, "inv": None, "url_qr": None, "enviado": False,
         "editar": False, "staff": security.es_staff(request)},
    )


@app.get("/i/{codigo}", response_class=HTMLResponse)
def invitacion(
    request: Request,
    codigo: str,
    ok: int = 0,
    puerta: int = 0,
    editar: int = 0,
    session: Session = Depends(get_session),
):
    """Link unico por grupo.

    Por defecto SIEMPRE muestra la invitacion, tambien para el staff: asi nadie
    se cruza por accidente con la pantalla de puerta. El control de ingreso solo
    aparece con `?puerta=1` y sesion de staff (es a donde manda el escaner).
    """
    inv = _buscar(session, codigo)
    if not inv:
        return templates.TemplateResponse(
            "no_encontrada.html", {"request": request, "codigo": codigo}, status_code=404
        )
    if puerta and security.es_staff(request):
        return templates.TemplateResponse(
            "puerta.html", {"request": request, "inv": inv, "hecho": False}
        )
    return templates.TemplateResponse(
        "invitacion.html",
        {
            "request": request,
            "inv": inv,
            "url_qr": f"/i/{inv.codigo}/qr.png",
            "enviado": bool(ok),
            "editar": bool(editar),
            "staff": security.es_staff(request),
        },
    )


@app.post("/i/{codigo}/rsvp")
def rsvp(
    request: Request,
    codigo: str,
    nombre: List[str] = Form(default=[]),
    tipo: List[str] = Form(default=[]),
    asiste: List[str] = Form(default=[]),
    restriccion: List[str] = Form(default=[]),
    mensaje: str = Form(default=""),
    telefono: str = Form(default=""),
    session: Session = Depends(get_session),
):
    inv = _buscar(session, codigo)
    if not inv:
        return RedirectResponse("/", status_code=303)

    for viejo in list(inv.invitados):
        session.delete(viejo)
    session.flush()

    total = len(nombre)
    for idx in range(total):
        nom = (nombre[idx] or "").strip()
        va = (asiste[idx] if idx < len(asiste) else "no") == "si"
        if not nom and not va:
            continue
        session.add(
            Invitado(
                invitacion_id=inv.id,
                nombre=nom or f"Invitado {idx + 1}",
                tipo=Tipo(tipo[idx]) if idx < len(tipo) and tipo[idx] in ("adulto", "nino") else Tipo.adulto,
                asiste=va,
                restriccion=(restriccion[idx].strip() or None) if idx < len(restriccion) else None,
            )
        )

    session.flush()
    session.refresh(inv)
    van = [i for i in inv.invitados if i.asiste]
    if not van:
        inv.estado = Estado.rechazada
    elif len(van) == inv.cupo_total:
        inv.estado = Estado.confirmada
    else:
        inv.estado = Estado.parcial

    inv.mensaje = mensaje.strip() or None
    inv.telefono = telefono.strip() or inv.telefono
    inv.respondida_at = datetime.utcnow()
    session.add(inv)
    session.commit()
    return RedirectResponse(f"/i/{inv.codigo}?ok=1#rsvp", status_code=303)


@app.get("/i/{codigo}/qr.png")
def qr_png(codigo: str, session: Session = Depends(get_session)):
    inv = _buscar(session, codigo)
    if not inv:
        return Response(status_code=404)
    return Response(qrgen.png_pase(inv.codigo), media_type="image/png")


# --- Control de ingreso ------------------------------------------------------
@app.get("/pase/{codigo}")
def pase_viejo(codigo: str):
    """Compatibilidad: los QR viejos apuntaban a /pase/{codigo}."""
    return RedirectResponse(f"/i/{codigo}", status_code=301)


@app.post("/i/{codigo}/ingreso", response_class=HTMLResponse)
def registrar_ingreso(
    request: Request,
    codigo: str,
    personas: int = Form(...),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    inv = _buscar(session, codigo)
    if not inv:
        return RedirectResponse("/admin/escaner", status_code=303)
    session.add(
        Checkin(
            invitacion_id=inv.id,
            personas=max(1, personas),
            operador=request.session.get("operador", "staff"),
        )
    )
    session.commit()
    session.refresh(inv)
    return templates.TemplateResponse("puerta.html", {"request": request, "inv": inv, "hecho": True})
