import csv
import io
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.engine import make_url
from sqlmodel import Session, select
from starlette.exceptions import HTTPException

from app import config, excel, security, servicios
from app.db import get_session
from app.models import Estado, Invitacion
from app.security import requiere_staff
from app.servicios import ErrorValidacion
from app.templating import avisar, templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _inv(session: Session, inv_id: int) -> Optional[Invitacion]:
    return session.get(Invitacion, inv_id)


# --- Sesion -----------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/admin", error: int = 0, vencida: int = 0):
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "next": security.destino_seguro(next), "error": error,
         "vencida": bool(vencida), "minutos": security.BLOQUEO_SEG // 60},
    )


@router.post("/login")
def login_post(
    request: Request,
    password: str = Form(default=""),
    next: str = Form(default="/admin"),
):
    destino = security.destino_seguro(next)
    if not security.bloqueado(request) and security.login(request, password):
        return RedirectResponse(destino, status_code=303)
    error = 2 if security.bloqueado(request) else 1
    return RedirectResponse(f"/admin/login?error={error}&next=" + quote(destino), status_code=303)


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
    if estado in {e.value for e in Estado}:
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
    cupo_adultos: str = Form(default="2"),
    cupo_ninos: str = Form(default="0"),
    telefono: str = Form(default=""),
    email: str = Form(default=""),
    notas: str = Form(default=""),
    tarjeta_fisica: str = Form(default=""),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    try:
        adultos, ninos = servicios.validar_cupos(cupo_adultos, cupo_ninos)
        inv = servicios.crear_invitacion(
            session,
            nombre_grupo=servicios.validar_nombre_grupo(nombre_grupo),
            cupo_adultos=adultos,
            cupo_ninos=ninos,
            telefono=servicios.texto_opcional(telefono, "telefono", "Teléfono"),
            email=servicios.texto_opcional(email, "email", "Email"),
            notas=servicios.texto_opcional(notas, "notas", "Notas internas"),
            tarjeta_fisica=bool(tarjeta_fisica),
        )
    except ErrorValidacion as e:
        avisar(request, e.mensaje)
        return RedirectResponse("/admin/invitaciones/nueva", status_code=303)
    session.commit()  # invitacion y lugares en una sola transaccion
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
    cupo_adultos: str = Form(default="0"),
    cupo_ninos: str = Form(default="0"),
    telefono: str = Form(default=""),
    email: str = Form(default=""),
    notas: str = Form(default=""),
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
        avisar(request, "Esa invitación ya no existe.")
        return RedirectResponse("/admin/invitaciones", status_code=303)
    destino = "/admin/invitaciones/" + str(inv.id)

    try:
        inv.nombre_grupo = servicios.validar_nombre_grupo(nombre_grupo)
        inv.cupo_adultos, inv.cupo_ninos = servicios.validar_cupos(cupo_adultos, cupo_ninos)
        inv.telefono = servicios.texto_opcional(telefono, "telefono", "Teléfono")
        inv.email = servicios.texto_opcional(email, "email", "Email")
        inv.notas = servicios.texto_opcional(notas, "notas", "Notas internas")
        inv.tarjeta_fisica = bool(tarjeta_fisica)

        propios = {str(g.id): g for g in inv.invitados}
        for pos, ident in enumerate(invitado_id):
            g = propios.get(ident)
            if not g:  # fila que ya no existe (p. ej. el invitado respondio mientras tanto)
                continue
            g.nombre = servicios.texto_opcional(
                nombre[pos] if pos < len(nombre) else "", "nombre", "Nombre") or ""
            g.restriccion = servicios.texto_opcional(
                restriccion[pos] if pos < len(restriccion) else "", "restriccion", "Restricción")
            marca = asiste[pos] if pos < len(asiste) else "sin"
            g.asiste = True if marca == "si" else (False if marca == "no" else None)
            if g.asiste and not g.nombre:  # la lista de seguridad se arma con estos nombres
                raise ErrorValidacion(f"Invitado {pos + 1}: para marcar que asiste hay que completar el nombre.")

        servicios.sincronizar_slots(inv)
        servicios.recalcular_estado(inv)
    except ErrorValidacion as e:
        session.rollback()  # descarta lo que ya se habia modificado
        avisar(request, e.mensaje)
        return RedirectResponse(destino, status_code=303)

    session.commit()  # datos, invitados, cupo y estado en una sola transaccion
    return RedirectResponse(destino, status_code=303)


@router.post("/invitaciones/{inv_id}/eliminar")
def eliminar(
    inv_id: int, _: bool = Depends(requiere_staff), session: Session = Depends(get_session)
):
    inv = _inv(session, inv_id)
    if inv:
        session.delete(inv)
        session.commit()
    return RedirectResponse("/admin/invitaciones", status_code=303)


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


# --- Escaner de codigos ------------------------------------------------------
@router.get("/escaner", response_class=HTMLResponse)
def escaner(request: Request, _: bool = Depends(requiere_staff)):
    return templates.TemplateResponse("admin/escaner.html", {"request": request})


@router.get("/buscar/{codigo}")
def buscar_por_codigo(
    request: Request, codigo: str, _: bool = Depends(requiere_staff), session: Session = Depends(get_session)
):
    """Adonde manda el escaner: busca la invitacion por codigo y va directo a su ficha.

    Pensado para armar las tarjetas fisicas antes de la boda: confirma a que familia corresponde
    cada QR ya impreso, sin tener que escribir el codigo a mano en el listado.
    """
    inv = session.exec(select(Invitacion).where(Invitacion.codigo == codigo.strip().upper())).first()
    if not inv:
        avisar(request, f"No existe una invitación con el código {codigo}.")
        return RedirectResponse("/admin/escaner", status_code=303)
    return RedirectResponse("/admin/invitaciones/" + str(inv.id), status_code=303)


# --- CSV --------------------------------------------------------------------
def _celda_segura(valor):
    """Excel y LibreOffice ejecutan como formula un texto que empieza con = + - @.

    Nombres, restricciones y mensajes los escribe el invitado: se les antepone un apostrofe.
    """
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


@router.get("/export.csv")
def exportar(_: bool = Depends(requiere_staff), session: Session = Depends(get_session)):
    invs = session.exec(select(Invitacion).order_by(Invitacion.nombre_grupo)).all()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow([
        "codigo", "grupo", "formato", "cupo_adultos", "cupo_ninos", "estado", "confirmados",
        "telefono", "email", "invitados", "restricciones", "mensaje", "link",
    ])
    for i in invs:
        detalle_invitados = []
        for g in i.invitados:
            marca = "si" if g.asiste else ("no" if g.asiste is False else "-")
            detalle_invitados.append((g.nombre or "(sin nombre)") + ":" + marca)
        restricciones = [g.nombre + ": " + g.restriccion for g in i.invitados if g.restriccion]
        w.writerow([_celda_segura(v) for v in (
            i.codigo, i.nombre_grupo, "fisica" if i.tarjeta_fisica else "virtual",
            i.cupo_adultos, i.cupo_ninos, i.estado.value,
            i.confirmados, i.telefono or "", i.email or "",
            " | ".join(detalle_invitados), " | ".join(restricciones),
            (i.mensaje or "").replace("\n", " "),
            config.BASE_URL + "/i/" + i.codigo,
        )])
    datos = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(datos),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="invitaciones.csv"'},
    )


@router.get("/export.xlsx")
def exportar_excel(_: bool = Depends(requiere_staff), session: Session = Depends(get_session)):
    invs = session.exec(select(Invitacion).order_by(Invitacion.nombre_grupo)).all()
    fecha = datetime.now(config.TZ).strftime("%Y-%m-%d")
    return Response(
        excel.generar(invs),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="invitados-boda-{fecha}.xlsx"'},
    )


@router.get("/respaldo.db")
def respaldo(_: bool = Depends(requiere_staff)):
    """Copia consistente de la base SQLite aunque haya escrituras en curso (API de backup).

    En Railway el archivo vive en un Volume: esta es la forma simple de bajarlo.
    """
    archivo = make_url(config.DB_URL).database
    if not config.DB_URL.startswith("sqlite") or not archivo or not Path(archivo).is_file():
        raise HTTPException(status_code=404)
    with tempfile.TemporaryDirectory() as carpeta:
        ruta_copia = Path(carpeta) / "respaldo.db"
        origen = sqlite3.connect(archivo)
        copia = sqlite3.connect(ruta_copia)
        try:
            origen.backup(copia)
            # La base anda en modo WAL y la copia heredaria esa marca: se pasa a modo normal para
            # que el archivo descargado se abra solo, sin necesitar un -wal al lado.
            copia.execute("PRAGMA journal_mode=DELETE")
        finally:
            origen.close()
            copia.close()
        datos = ruta_copia.read_bytes()
    fecha = datetime.now(config.TZ).strftime("%Y-%m-%d-%H%M")
    return Response(
        datos,
        media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": f'attachment; filename="boda-respaldo-{fecha}.db"'},
    )


@router.post("/importar")
def importar(
    request: Request,
    archivo: UploadFile = File(...),
    _: bool = Depends(requiere_staff),
    session: Session = Depends(get_session),
):
    """CSV con columnas: grupo;adultos;ninos;telefono;email;fisica (separador ; o ,).

    En `fisica` vale si / 1 / x / fisica para marcar la tarjeta impresa. Se valida todo el
    archivo antes de guardar: si una fila esta mal no se importa ninguna.
    """
    try:
        texto = servicios.decodificar_csv(archivo.file.read(servicios.CSV_MAX_BYTES + 1))
        filas = servicios.leer_csv(texto)
        creadas, omitidas = servicios.importar_filas(session, filas)
    except ErrorValidacion as e:
        session.rollback()
        avisar(request, e.mensaje, detalles=e.detalles)
        return RedirectResponse("/admin", status_code=303)

    session.commit()  # todas las filas en una sola transaccion
    texto = f"Se importaron {len(creadas)} invitaciones."
    if omitidas:
        avisar(request, texto + f" Se omitieron {len(omitidas)}:", tipo="ok", detalles=omitidas)
    else:
        avisar(request, texto, tipo="ok")
    return RedirectResponse("/admin/invitaciones", status_code=303)
