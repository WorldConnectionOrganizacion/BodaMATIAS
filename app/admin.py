import csv
import io
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlmodel import Session, select

from app import config, security
from app.db import get_session, nuevo_codigo
from app.models import Estado, Invitacion, Invitado, Tipo
from app.security import requiere_staff
from app.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _inv(session: Session, inv_id: int) -> Optional[Invitacion]:
    return session.get(Invitacion, inv_id)


def _sincronizar_slots(session: Session, inv: Invitacion) -> None:
    """Deja tantas filas de Invitado como cupo declarado (adultos + ninos)."""
    adultos = [i for i in inv.invitados if i.tipo == Tipo.adulto]
    ninos = [i for i in inv.invitados if i.tipo == Tipo.nino]
    pares = ((adultos, Tipo.adulto, inv.cupo_adultos), (ninos, Tipo.nino, inv.cupo_ninos))
    for lista, tipo, cupo in pares:
        while len(lista) < cupo:
            nuevo = Invitado(invitacion_id=inv.id, tipo=tipo, nombre="")
            session.add(nuevo)
            lista.append(nuevo)
        while len(lista) > cupo:
            session.delete(lista.pop())


# --- Sesion -----------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/admin", error: int = 0):
    return templates.TemplateResponse(
        "admin/login.html", {"request": request, "next": next, "error": bool(error)}
    )


@router.post("/login")
def login_post(
    request: Request,
    password: str = Form(...),
    operador: str = Form(default=""),
    next: str = Form(default="/admin"),
):
    if security.login(request, password, operador):
        return RedirectResponse(next or "/admin", status_code=303)
    return RedirectResponse("/admin/login?error=1&next=" + quote(next), status_code=303)


@router.get("/logout")
def logout(request: Request):
    security.logout(request)
    return RedirectResponse("/admin/login", status_code=303)


# --- Tablero ----------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def tablero(request: Request, _: bool = Depends(requiere_staff), session: Session = Depends(get_session)):
    invs = session.exec(select(Invitacion).order_by(Invitacion.nombre_grupo)).all()
    stats = {
        "invitaciones": len(invs),
        "cupo": sum(i.cupo_total for i in invs),
        "confirmados": sum(i.confirmados for i in invs),
        "pendientes": sum(1 for i in invs if i.estado == Estado.pendiente),
        "rechazadas": sum(1 for i in invs if i.estado == Estado.rechazada),
        "ingresados": sum(i.ingresados for i in invs),
        "fisicas": sum(1 for i in invs if i.tarjeta_fisica),
        "virtuales": sum(1 for i in invs if not i.tarjeta_fisica),
        "restricciones": [
            (i.nombre_grupo, g.nombre, g.restriccion)
            for i in invs
            for g in i.invitados
            if g.restriccion
        ],
    }
    return templates.TemplateResponse(
        "admin/tablero.html", {"request": request, "stats": stats, "invitaciones": invs}
    )


@router.get("/invitaciones", response_class=HTMLResponse)
def listado(
    request: Request,
    q: str = "",
    estado: str = "",
    formato: str = "",
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    consulta = select(Invitacion).order_by(Invitacion.nombre_grupo)
    if q:
        patron = "%" + q.strip() + "%"
        consulta = consulta.where(
            (Invitacion.nombre_grupo.ilike(patron)) | (Invitacion.codigo.ilike(patron))
        )
    if estado:
        consulta = consulta.where(Invitacion.estado == Estado(estado))
    if formato == "fisica":
        consulta = consulta.where(Invitacion.tarjeta_fisica == True)  # noqa: E712
    elif formato == "virtual":
        consulta = consulta.where(Invitacion.tarjeta_fisica == False)  # noqa: E712
    invs = session.exec(consulta).all()
    return templates.TemplateResponse(
        "admin/listado.html",
        {"request": request, "invitaciones": invs, "q": q, "estado": estado, "formato": formato},
    )


# --- Alta / edicion ---------------------------------------------------------
@router.get("/invitaciones/nueva", response_class=HTMLResponse)
def nueva_form(request: Request, _: bool = Depends(requiere_staff)):
    return templates.TemplateResponse("admin/form.html", {"request": request, "inv": None})


@router.post("/invitaciones/nueva")
def nueva_post(
    request: Request,
    nombre_grupo: str = Form(...),
    cupo_adultos: int = Form(2),
    cupo_ninos: int = Form(0),
    telefono: str = Form(default=""),
    email: str = Form(default=""),
    notas: str = Form(default=""),
    tarjeta_fisica: str = Form(default=""),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    inv = Invitacion(
        codigo=nuevo_codigo(session),
        nombre_grupo=nombre_grupo.strip(),
        cupo_adultos=max(0, cupo_adultos),
        cupo_ninos=max(0, cupo_ninos),
        telefono=telefono.strip() or None,
        email=email.strip() or None,
        notas=notas.strip() or None,
        tarjeta_fisica=bool(tarjeta_fisica),
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)
    _sincronizar_slots(session, inv)
    session.commit()
    return RedirectResponse("/admin/invitaciones/" + str(inv.id), status_code=303)


@router.get("/invitaciones/{inv_id}", response_class=HTMLResponse)
def detalle(
    request: Request,
    inv_id: int,
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    inv = _inv(session, inv_id)
    if not inv:
        return RedirectResponse("/admin/invitaciones", status_code=303)
    wa = ""
    if inv.telefono:
        tel = "".join(c for c in inv.telefono if c.isdigit())
        texto = (
            "Hola " + inv.nombre_grupo + "! Nos casamos y queremos que esten con nosotros. "
            "Aca esta su invitacion: " + config.BASE_URL + "/i/" + inv.codigo
        )
        wa = "https://wa.me/" + tel + "?text=" + quote(texto)
    return templates.TemplateResponse(
        "admin/detalle.html", {"request": request, "inv": inv, "wa": wa}
    )


@router.post("/invitaciones/{inv_id}")
def editar(
    request: Request,
    inv_id: int,
    nombre_grupo: str = Form(...),
    cupo_adultos: int = Form(0),
    cupo_ninos: int = Form(0),
    telefono: str = Form(default=""),
    email: str = Form(default=""),
    notas: str = Form(default=""),
    estado: str = Form(default=""),
    tarjeta_fisica: str = Form(default=""),
    invitado_id: List[str] = Form(default=[]),
    nombre: List[str] = Form(default=[]),
    asiste: List[str] = Form(default=[]),
    restriccion: List[str] = Form(default=[]),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    inv = _inv(session, inv_id)
    if not inv:
        return RedirectResponse("/admin/invitaciones", status_code=303)

    inv.nombre_grupo = nombre_grupo.strip()
    inv.cupo_adultos = max(0, cupo_adultos)
    inv.cupo_ninos = max(0, cupo_ninos)
    inv.telefono = telefono.strip() or None
    inv.email = email.strip() or None
    inv.notas = notas.strip() or None
    inv.tarjeta_fisica = bool(tarjeta_fisica)
    if estado:
        inv.estado = Estado(estado)

    for pos, ident in enumerate(invitado_id):
        g = session.get(Invitado, int(ident)) if ident.isdigit() else None
        if not g or g.invitacion_id != inv.id:
            continue
        g.nombre = (nombre[pos] if pos < len(nombre) else "").strip()
        g.restriccion = (restriccion[pos].strip() or None) if pos < len(restriccion) else None
        marca = asiste[pos] if pos < len(asiste) else "sin"
        g.asiste = True if marca == "si" else (False if marca == "no" else None)
        session.add(g)

    session.add(inv)
    session.commit()
    session.refresh(inv)
    _sincronizar_slots(session, inv)
    session.commit()
    return RedirectResponse("/admin/invitaciones/" + str(inv.id), status_code=303)


@router.post("/invitaciones/{inv_id}/eliminar")
def eliminar(
    inv_id: int, _: bool = Depends(requiere_staff), session: Session = Depends(get_session)
):
    inv = _inv(session, inv_id)
    if inv:
        session.delete(inv)
        session.commit()
    return RedirectResponse("/admin/invitaciones", status_code=303)


@router.post("/invitaciones/{inv_id}/deshacer-ingreso")
def deshacer_ingreso(
    inv_id: int, _: bool = Depends(requiere_staff), session: Session = Depends(get_session)
):
    inv = _inv(session, inv_id)
    if inv and inv.checkins:
        ultimo = sorted(inv.checkins, key=lambda c: c.at)[-1]
        session.delete(ultimo)
        session.commit()
    return RedirectResponse("/admin/invitaciones/" + str(inv_id), status_code=303)


# --- Tarjeta imprimible con QR ----------------------------------------------
@router.get("/invitaciones/{inv_id}/tarjeta", response_class=HTMLResponse)
def tarjeta(
    request: Request,
    inv_id: int,
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    inv = _inv(session, inv_id)
    if not inv:
        return RedirectResponse("/admin/invitaciones", status_code=303)
    return templates.TemplateResponse("admin/tarjeta.html", {"request": request, "inv": inv})


# --- Escaner de puerta ------------------------------------------------------
@router.get("/escaner", response_class=HTMLResponse)
def escaner(request: Request, _: bool = Depends(requiere_staff)):
    return templates.TemplateResponse("admin/escaner.html", {"request": request})


# --- CSV --------------------------------------------------------------------
@router.get("/export.csv")
def exportar(_: bool = Depends(requiere_staff), session: Session = Depends(get_session)):
    invs = session.exec(select(Invitacion).order_by(Invitacion.nombre_grupo)).all()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow([
        "codigo", "grupo", "formato", "cupo_adultos", "cupo_ninos", "estado", "confirmados",
        "ingresados", "telefono", "email", "invitados", "restricciones", "mensaje", "link",
    ])
    for i in invs:
        detalle_invitados = []
        for g in i.invitados:
            marca = "si" if g.asiste else ("no" if g.asiste is False else "-")
            detalle_invitados.append((g.nombre or "(sin nombre)") + ":" + marca)
        restricciones = [g.nombre + ": " + g.restriccion for g in i.invitados if g.restriccion]
        w.writerow([
            i.codigo, i.nombre_grupo, "fisica" if i.tarjeta_fisica else "virtual",
            i.cupo_adultos, i.cupo_ninos, i.estado.value,
            i.confirmados, i.ingresados, i.telefono or "", i.email or "",
            " | ".join(detalle_invitados), " | ".join(restricciones),
            (i.mensaje or "").replace("\n", " "),
            config.BASE_URL + "/i/" + i.codigo,
        ])
    datos = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(datos),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="invitaciones.csv"'},
    )


@router.post("/importar")
async def importar(
    archivo: UploadFile = File(...),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    """CSV con columnas: grupo;adultos;ninos;telefono;email;fisica (separador ; o ,).

    En `fisica` vale si / 1 / x / fisica para marcar la tarjeta impresa.
    """
    crudo = (await archivo.read()).decode("utf-8-sig", errors="replace")
    separador = ";" if crudo.count(";") >= crudo.count(",") else ","
    lector = csv.DictReader(io.StringIO(crudo), delimiter=separador)
    for fila in lector:
        grupo = (fila.get("grupo") or fila.get("nombre_grupo") or "").strip()
        if not grupo:
            continue
        inv = Invitacion(
            codigo=nuevo_codigo(session),
            nombre_grupo=grupo,
            cupo_adultos=int(fila.get("adultos") or fila.get("cupo_adultos") or 0),
            cupo_ninos=int(fila.get("ninos") or fila.get("cupo_ninos") or 0),
            telefono=(fila.get("telefono") or "").strip() or None,
            email=(fila.get("email") or "").strip() or None,
            tarjeta_fisica=(fila.get("fisica") or fila.get("formato") or "").strip().lower()
            in ("si", "sí", "1", "x", "true", "fisica", "física"),
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)
        _sincronizar_slots(session, inv)
        session.commit()
    return RedirectResponse("/admin/invitaciones", status_code=303)
