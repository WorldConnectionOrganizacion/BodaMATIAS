"""Reglas de negocio de las invitaciones: validaciones, cupo, estado, RSVP e importacion.

Ninguna funcion de este modulo hace commit: el endpoint que las usa confirma una sola vez al
final, asi cada pedido se guarda completo o no se guarda nada.
"""
import csv
import io
import unicodedata
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from sqlmodel import Session, select

from app import config
from app.db import nuevo_codigo
from app.models import Estado, Invitacion, Invitado, Tipo

CUPO_MAX_POR_TIPO = 20
LARGO_MAX = {  # caracteres por campo de texto (los templates usan los mismos en maxlength)
    "grupo": 120,
    "nombre": 80,
    "restriccion": 200,
    "mensaje": 1000,
    "telefono": 30,
    "email": 120,
    "notas": 1000,
}
LARGO_MAX_GRUPO = LARGO_MAX["grupo"]
CSV_MAX_BYTES = 1_000_000
VALORES_FISICA = ("si", "sí", "1", "x", "true", "fisica", "física")
COLUMNAS_CSV = {
    "grupo": ("grupo", "nombre_grupo"),
    "adultos": ("adultos", "cupo_adultos"),
    "ninos": ("ninos", "cupo_ninos"),
    "telefono": ("telefono",),
    "email": ("email",),
    "fisica": ("fisica", "formato", "tarjeta_fisica"),
    # Opcionales: solo presentes en un CSV exportado (respaldo o migracion), no en carga manual.
    "codigo": ("codigo",),
    "estado": ("estado",),
    "mensaje": ("mensaje",),
    "notas": ("notas",),
    "creada_at": ("creada_at",),
    "respondida_at": ("respondida_at",),
}
FORM_DESACTUALIZADO = (
    "La invitación cambió mientras la completabas. Recargá la página y volvé a enviar tu respuesta."
)


class ErrorValidacion(Exception):
    """Dato invalido cargado por un usuario. `mensaje` se muestra tal cual en pantalla."""

    def __init__(self, mensaje: str, detalles: Optional[List[str]] = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or []


# --- Validaciones -----------------------------------------------------------
def validar_nombre_grupo(texto: str) -> str:
    nombre = " ".join((texto or "").split())
    if not nombre:
        raise ErrorValidacion("El nombre del grupo no puede quedar vacío.")
    if len(nombre) > LARGO_MAX_GRUPO:
        raise ErrorValidacion(f"El nombre del grupo supera los {LARGO_MAX_GRUPO} caracteres.")
    return nombre


def validar_cupo(texto, campo: str) -> int:
    crudo = str(texto if texto is not None else "").strip()
    if not crudo:
        return 0
    if not crudo.isdecimal() or int(crudo) > CUPO_MAX_POR_TIPO:
        raise ErrorValidacion(
            f"{campo}: tiene que ser un número entero entre 0 y {CUPO_MAX_POR_TIPO} (llegó '{crudo[:20]}')."
        )
    return int(crudo)


def validar_cupos(adultos, ninos) -> Tuple[int, int]:
    cupo_adultos = validar_cupo(adultos, "Adultos")
    cupo_ninos = validar_cupo(ninos, "Niños")
    if cupo_adultos + cupo_ninos == 0:
        raise ErrorValidacion("La invitación tiene que tener al menos un lugar (adulto o niño).")
    return cupo_adultos, cupo_ninos


def texto_opcional(valor: str, campo: str, rotulo: str) -> Optional[str]:
    limpio = (valor or "").strip()
    if len(limpio) > LARGO_MAX[campo]:
        raise ErrorValidacion(f"{rotulo}: puede tener hasta {LARGO_MAX[campo]} caracteres.")
    return limpio or None


# --- Cupo y estado ----------------------------------------------------------
def _prioridad_para_conservar(g: Invitado) -> Tuple[bool, bool, bool]:
    """Al sobrar lugares se borran primero los vacios y al final los que respondieron."""
    return (g.asiste is True, g.asiste is not None, bool((g.nombre or "").strip()))


def sincronizar_slots(inv: Invitacion) -> None:
    """Deja tantas filas de Invitado como cupo declarado (adultos + ninos).

    Nunca borra a alguien confirmado: si el cupo nuevo queda por debajo de los confirmados
    de ese tipo, corta con ErrorValidacion.
    """
    for tipo, cupo, rotulo in (
        (Tipo.adulto, inv.cupo_adultos, "adultos"),
        (Tipo.nino, inv.cupo_ninos, "niños"),
    ):
        lista = [g for g in inv.invitados if g.tipo == tipo]
        confirmados = sum(1 for g in lista if g.asiste is True)
        if cupo < confirmados:
            raise ErrorValidacion(
                f"No se puede bajar el cupo de {rotulo} a {cupo}: hay {confirmados} confirmados. "
                "Marcá primero quién no asiste."
            )
        for _ in range(cupo - len(lista)):
            inv.invitados.append(Invitado(tipo=tipo, nombre=""))
        sobrantes = sorted(lista, key=_prioridad_para_conservar)[: max(0, len(lista) - cupo)]
        for g in sobrantes:
            inv.invitados.remove(g)  # delete-orphan: se borra al hacer flush


def recalcular_estado(inv: Invitacion) -> None:
    """El estado sale siempre de la asistencia cargada, nunca se fija a mano."""
    respuestas = [g.asiste for g in inv.invitados]
    van = sum(1 for r in respuestas if r is True)
    if van:
        inv.estado = Estado.confirmada if van >= inv.cupo_total else Estado.parcial
    elif respuestas and all(r is False for r in respuestas):
        inv.estado = Estado.rechazada
    else:
        inv.estado = Estado.pendiente


def crear_invitacion(session: Session, **datos) -> Invitacion:
    """Crea una invitacion nueva.

    `estado` y `respondida_at`, si vienen (import con datos ya respondidos), no se asignan
    tal cual: `sincronizar_slots` crea los lugares y despues se marca `asiste` acorde para que
    `recalcular_estado` llegue al mismo estado por el camino normal, sin romper la regla de que
    el estado siempre sale de la asistencia cargada.
    """
    datos.setdefault("codigo", nuevo_codigo(session))
    estado_previo = datos.pop("estado", None)
    respondida_at = datos.pop("respondida_at", None)
    inv = Invitacion(**datos)
    sincronizar_slots(inv)
    if estado_previo == Estado.confirmada:
        for g in inv.invitados:
            g.asiste = True
    elif estado_previo == Estado.rechazada:
        for g in inv.invitados:
            g.asiste = False
    recalcular_estado(inv)
    if respondida_at:
        inv.respondida_at = respondida_at
    session.add(inv)
    return inv


def link_whatsapp(inv: Invitacion) -> str:
    """Link `wa.me` con la invitacion precargada para mandar por WhatsApp. Vacio sin telefono."""
    tel = "".join(c for c in (inv.telefono or "") if c.isdigit())
    if not tel:
        return ""
    texto = (
        "Hola " + inv.nombre_grupo + "! Nos casamos y queremos que esten con nosotros. "
        "Aca esta su invitacion: " + config.BASE_URL + "/i/" + inv.codigo
    )
    return "https://wa.me/" + tel + "?text=" + quote(texto)


# --- RSVP del invitado ------------------------------------------------------
def rsvp_abierto(hoy: Optional[date] = None) -> bool:
    """La confirmacion queda abierta hasta el final del dia FECHA_LIMITE_RSVP (hora del evento)."""
    hoy = hoy or datetime.now(config.TZ).date()
    return hoy <= date.fromisoformat(config.FECHA_LIMITE_RSVP)


def fecha_limite_texto() -> str:
    return date.fromisoformat(config.FECHA_LIMITE_RSVP).strftime("%d/%m/%Y")


def aplicar_rsvp(
    inv: Invitacion,
    ids: List[str],
    nombres: List[str],
    asistencias: List[str],
    restricciones: List[str],
) -> None:
    """Actualiza en su lugar las filas que ya tiene la invitacion.

    El cupo y el tipo de cada lugar los define el panel: del formulario solo se toma nombre,
    asistencia y restriccion, y tiene que traer exactamente los lugares de la invitacion.
    Primero valida todo y recien despues modifica, asi un error no deja cambios a medias.
    """
    propios: Dict[str, Invitado] = {str(g.id): g for g in inv.invitados}
    if not (len(ids) == len(nombres) == len(asistencias) == len(restricciones)):
        raise ErrorValidacion(FORM_DESACTUALIZADO)
    if len(set(ids)) != len(ids) or set(ids) != set(propios):
        raise ErrorValidacion(FORM_DESACTUALIZADO)

    cambios = []
    for ident, nombre, marca, restriccion in zip(ids, nombres, asistencias, restricciones):
        if marca not in ("si", "no"):
            raise ErrorValidacion("Elegí si asiste o no para cada persona.")
        nombre = " ".join(nombre.split())
        if marca == "si" and not nombre:
            raise ErrorValidacion("Completá el nombre y apellido de cada persona que asiste.")
        if len(nombre) > LARGO_MAX["nombre"]:
            raise ErrorValidacion(f"Nombre y apellido: puede tener hasta {LARGO_MAX['nombre']} caracteres.")
        restriccion = texto_opcional(restriccion, "restriccion", "Restricción alimentaria")
        cambios.append((propios[ident], nombre, marca == "si", restriccion))

    for g, nombre, asiste, restriccion in cambios:
        g.nombre = nombre
        g.asiste = asiste
        g.restriccion = restriccion


# --- Importacion CSV --------------------------------------------------------
def decodificar_csv(crudo: bytes) -> str:
    if len(crudo) > CSV_MAX_BYTES:
        raise ErrorValidacion(f"El archivo supera {CSV_MAX_BYTES // 1_000_000} MB.")
    if b"\x00" in crudo:
        raise ErrorValidacion("El archivo no es un CSV de texto (¿es un .xlsx?). Guardalo como CSV y probá de nuevo.")
    try:
        return crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return crudo.decode("cp1252", errors="replace")  # CSV guardado por Excel en Windows


def _normalizar_encabezado(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower().replace(" ", "_")


def _fecha_opcional(texto: str, rotulo: str):
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        raise ErrorValidacion(f"{rotulo}: fecha inválida '{texto[:30]}' (formato esperado AAAA-MM-DD HH:MM:SS).")


def leer_csv(texto: str) -> List[dict]:
    """Valida todas las filas. Si alguna esta mal no devuelve nada: la carga es todo o nada."""
    primera = texto.split("\n", 1)[0]
    separador = ";" if primera.count(";") >= primera.count(",") else ","
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    filas, errores = [], []
    try:
        encabezado = [_normalizar_encabezado(c) for c in next(lector, [])]
        indices = {}
        for clave, alias in COLUMNAS_CSV.items():
            encontrado = next((a for a in alias if a in encabezado), None)
            if encontrado:
                indices[clave] = encabezado.index(encontrado)
        if "grupo" not in indices:
            raise ErrorValidacion("Falta la columna 'grupo' en la primera fila del archivo.")

        for fila in lector:
            if not any(c.strip() for c in fila):
                continue

            def celda(clave: str) -> str:
                i = indices.get(clave)
                return fila[i].strip() if i is not None and i < len(fila) else ""

            try:
                grupo = validar_nombre_grupo(celda("grupo"))
                adultos, ninos = validar_cupos(celda("adultos"), celda("ninos"))
                telefono = texto_opcional(celda("telefono"), "telefono", "Teléfono")
                email = texto_opcional(celda("email"), "email", "Email")
                codigo = celda("codigo").strip().upper() or None
                estado_txt = celda("estado").strip()
                if estado_txt and estado_txt not in Estado.__members__:
                    raise ErrorValidacion(f"estado: valor desconocido '{estado_txt}'.")
                mensaje = texto_opcional(celda("mensaje"), "mensaje", "Mensaje")
                notas = texto_opcional(celda("notas"), "notas", "Notas")
                creada_at = _fecha_opcional(celda("creada_at"), "creada_at")
                respondida_at = _fecha_opcional(celda("respondida_at"), "respondida_at")
            except ErrorValidacion as e:
                errores.append(f"Línea {lector.line_num}: {e.mensaje}")
                continue
            fila = {
                "nombre_grupo": grupo,
                "cupo_adultos": adultos,
                "cupo_ninos": ninos,
                "telefono": telefono,
                "email": email,
                "tarjeta_fisica": celda("fisica").lower() in VALORES_FISICA,
            }
            if codigo:
                fila["codigo"] = codigo
            if estado_txt:
                fila["estado"] = Estado[estado_txt]
            if mensaje:
                fila["mensaje"] = mensaje
            if notas:
                fila["notas"] = notas
            if creada_at:
                fila["creada_at"] = creada_at
            if respondida_at:
                fila["respondida_at"] = respondida_at
            filas.append(fila)
    except csv.Error as e:
        raise ErrorValidacion(f"El archivo tiene un formato inválido cerca de la línea {lector.line_num}: {e}")

    if errores:
        raise ErrorValidacion("No se importó nada: corregí estas filas y volvé a subir el archivo.", errores)
    if not filas:
        raise ErrorValidacion("El archivo no tiene filas con invitaciones.")
    return filas


def importar_filas(session: Session, filas: List[dict]) -> Tuple[List[Invitacion], List[str]]:
    """Crea las invitaciones. Omite, e informa por que, los grupos que ya existen en la base o
    que aparecen repetidos dentro del mismo archivo."""
    def clave(nombre: str) -> str:
        return " ".join(nombre.split()).casefold()

    en_base = {clave(n) for n in session.exec(select(Invitacion.nombre_grupo)).all()}
    codigos_en_base = {c for c in session.exec(select(Invitacion.codigo)).all()}
    en_archivo = set()
    codigos_en_archivo = set()
    creadas, omitidas = [], []
    for datos in filas:
        grupo = datos["nombre_grupo"]
        codigo = datos.get("codigo")
        if codigo and codigo in codigos_en_base:
            omitidas.append(f"{grupo} ({codigo}, ya existía)")
        elif codigo and codigo in codigos_en_archivo:
            omitidas.append(f"{grupo} ({codigo}, repetido en el archivo)")
        elif not codigo and clave(grupo) in en_base:
            omitidas.append(f"{grupo} (ya existía)")
        elif not codigo and clave(grupo) in en_archivo:
            omitidas.append(f"{grupo} (repetido en el archivo)")
        else:
            en_archivo.add(clave(grupo))
            if codigo:
                codigos_en_archivo.add(codigo)
            creadas.append(crear_invitacion(session, **datos))
    return creadas, omitidas
