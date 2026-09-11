import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import config, qrgen, security, servicios
from app.admin import router as admin_router
from app.db import get_session, init_db
from app.models import Checkin, Invitacion
from app.security import NoAutorizado, requiere_staff
from app.servicios import ErrorValidacion
from app.templating import avisar, templates

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Boda Sofía & Matías", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=config.BASE_URL.startswith("https://"),  # cookie Secure cuando hay HTTPS
)
LIMITE_CUERPO = 2_000_000  # el CSV mas grande (1 MB) con margen; frena formularios gigantes
app.mount("/static", StaticFiles(directory=config.RAIZ / "app" / "static"), name="static")

app.include_router(admin_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    print(f"BASE_URL en uso: {config.BASE_URL}  (los QR codifican {config.BASE_URL}/i/CODIGO)")
    publico = not any(x in config.BASE_URL for x in ("localhost", "127.0.0.1", "192.168.", "10.0."))
    if not config.ADMIN_USUARIOS_DEFINIDOS:
        print("AVISO: falta ADMIN_USUARIOS en .env: queda una sola cuenta 'admin' con ADMIN_PASSWORD.")
    if len(config.ADMIN_USUARIOS) > 4:
        print(f"AVISO: hay {len(config.ADMIN_USUARIOS)} cuentas de staff; el panel esta pensado para 3-4.")
    for usuario, clave in config.ADMIN_USUARIOS.items():
        if publico and (len(clave) < 8 or clave == "boda2026"):
            print(f"AVISO: la app esta publicada y la clave de '{usuario}' es corta o de ejemplo. Cambiala.")
    if publico and config.SECRET_KEY == "cambiar-esta-clave-en-produccion":
        print("AVISO: SECRET_KEY es la de ejemplo: las sesiones del panel se pueden falsificar.")
    if config.BASE_URL.startswith("http://") and publico:
        print("AVISO: sin HTTPS el escaner por camara no funciona (usar carga manual del codigo).")
    if config.EN_RAILWAY and config.DB_URL.startswith("sqlite"):
        base = Path(make_url(config.DB_URL).database or "").resolve()
        volumen = Path(config.RAILWAY_VOLUMEN).resolve() if config.RAILWAY_VOLUMEN else None
        if volumen is None or volumen not in base.parents:
            print("AVISO GRAVE: la base SQLite no esta en un Volume de Railway y se BORRA en cada deploy. "
                  "Agregar un Volume al servicio y no definir DB_URL (ver README).")
    if config.EN_RAILWAY and not publico:
        print("AVISO: BASE_URL no es publica: definila con la URL https de Railway o del dominio propio.")


# --- Manejo de errores ------------------------------------------------------
def _pagina_error(request: Request, status: int, titulo: str, mensaje: str,
                  detalles: Optional[List[str]] = None, headers: Optional[dict] = None):
    ruta = request.url.path
    admin = "session" in request.scope and (ruta.startswith("/admin") or ruta.endswith("/ingreso"))
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "admin": admin, "titulo": titulo, "mensaje": mensaje,
         "detalles": detalles or []},
        status_code=status,
        headers=headers,
    )


@app.middleware("http")
async def _limitar_cuerpo(request: Request, call_next):
    largo = request.headers.get("content-length", "")
    if largo.isdigit() and int(largo) > LIMITE_CUERPO:
        return _pagina_error(request, 413, "Demasiado grande",
                             "El formulario o el archivo que enviaste es demasiado grande.")
    return await call_next(request)


@app.exception_handler(NoAutorizado)
async def _no_autorizado(request: Request, exc: NoAutorizado):
    return security.redirect_login(exc)


@app.exception_handler(StarletteHTTPException)
async def _error_http(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return _pagina_error(request, 404, "No encontramos esa página",
                             "El link no existe o está incompleto. Revisalo y probá de nuevo.")
    return _pagina_error(request, exc.status_code, "No pudimos procesar el pedido",
                         "Volvé atrás y probá de nuevo.", headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def _datos_invalidos(request: Request, exc: RequestValidationError):
    log.warning("Datos invalidos en %s %s: %s", request.method, request.url.path, exc.errors())
    return _pagina_error(request, 400, "Datos inválidos",
                         "Algún dato del formulario no tiene el formato esperado. "
                         "Volvé atrás, revisalo y probá de nuevo.")


@app.exception_handler(ErrorValidacion)
async def _error_validacion(request: Request, exc: ErrorValidacion):
    return _pagina_error(request, 400, "Datos inválidos", exc.mensaje, exc.detalles)


@app.exception_handler(SQLAlchemyError)
async def _error_base(request: Request, exc: SQLAlchemyError):
    # La sesion ya hizo rollback al cerrarse en get_session: no quedo nada a medio guardar.
    log.error("Error de base de datos en %s %s", request.method, request.url.path, exc_info=exc)
    if isinstance(exc, OperationalError) and "locked" in str(exc).lower():
        return _pagina_error(request, 503, "Estamos con mucha actividad",
                             "No se guardó nada. Esperá unos segundos y volvé a intentar.")
    return _pagina_error(request, 500, "No pudimos guardar los datos",
                         "Ocurrió un error inesperado y no se guardó nada. Probá de nuevo en un rato.")


@app.exception_handler(Exception)
async def _error_inesperado(request: Request, exc: Exception):
    # Starlette vuelve a lanzar la excepcion despues de este handler: uvicorn la registra con traceback.
    return _pagina_error(request, 500, "Algo salió mal",
                         "Ocurrió un error inesperado. Probá de nuevo en un rato.")


def _buscar(session: Session, codigo: str) -> Optional[Invitacion]:
    return session.exec(
        select(Invitacion).where(Invitacion.codigo == codigo.strip().upper())
    ).first()


@app.get("/salud")
def salud(session: Session = Depends(get_session)):
    """Healthcheck de Railway: responde solo si la base contesta."""
    session.connection().exec_driver_sql("SELECT 1")
    return {"ok": True}


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
    hecho: int = 0,
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
    if puerta:
        # Viene del escaner. Sin sesion (p. ej. vencida) se pide login y se vuelve aca, en vez de
        # mostrar la invitacion y que el de la puerta no se de cuenta.
        security.requiere_staff(request)
        return templates.TemplateResponse(
            "puerta.html", {"request": request, "inv": inv, "hecho": bool(hecho)}
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
    invitado_id: List[str] = Form(default=[]),
    nombre: List[str] = Form(default=[]),
    asiste: List[str] = Form(default=[]),
    restriccion: List[str] = Form(default=[]),
    mensaje: str = Form(default=""),
    telefono: str = Form(default=""),
    session: Session = Depends(get_session),
):
    inv = _buscar(session, codigo)
    if not inv:
        return RedirectResponse("/", status_code=303)

    if not servicios.rsvp_abierto():
        avisar(request, f"La confirmación de asistencia cerró el {servicios.fecha_limite_texto()}. "
                        "Si necesitás cambiar algo, escribinos.")
        return RedirectResponse(f"/i/{inv.codigo}#rsvp", status_code=303)

    try:
        mensaje_limpio = servicios.texto_opcional(mensaje, "mensaje", "Mensaje")
        telefono_limpio = servicios.texto_opcional(telefono, "telefono", "Teléfono")
        servicios.aplicar_rsvp(inv, invitado_id, nombre, asiste, restriccion)
    except ErrorValidacion as e:
        avisar(request, e.mensaje)
        return RedirectResponse(f"/i/{inv.codigo}?editar=1#rsvp", status_code=303)

    servicios.recalcular_estado(inv)
    inv.mensaje = mensaje_limpio
    inv.telefono = telefono_limpio or inv.telefono
    inv.respondida_at = datetime.utcnow()
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


@app.post("/i/{codigo}/ingreso")
def registrar_ingreso(
    request: Request,
    codigo: str,
    personas: str = Form(default=""),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    inv = _buscar(session, codigo)
    if not inv:
        avisar(request, f"No existe una invitación con el código {codigo}.")
        return RedirectResponse("/admin/escaner", status_code=303)
    destino = f"/i/{inv.codigo}?puerta=1"
    try:
        cantidad = servicios.validar_ingreso(inv, personas)
    except ErrorValidacion as e:
        avisar(request, e.mensaje)
        return RedirectResponse(destino, status_code=303)
    session.add(
        Checkin(
            invitacion_id=inv.id,
            personas=cantidad,
            operador=request.session.get("operador", "staff"),
        )
    )
    session.commit()
    # Redirect (PRG): recargar la pantalla de puerta no vuelve a registrar el ingreso.
    return RedirectResponse(destino + "&hecho=1", status_code=303)
