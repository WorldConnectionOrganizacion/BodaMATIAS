"""Prueba de humo de punta a punta, contra una base temporal.

Uso:  .venv\\Scripts\\python test_smoke.py
No toca data/boda.db: crea y borra data/test_smoke.db.
"""
import io
import os
import pathlib
import sqlite3
import zipfile
from urllib.parse import parse_qs, urlsplit

RUTA = pathlib.Path("data/test_smoke.db")
os.environ["DB_URL"] = "sqlite:///data/test_smoke.db"
os.environ["ADMIN_PASSWORD"] = "clave-test-1"  # gana sobre el .env
RUTA.parent.mkdir(exist_ok=True)
RUTA.unlink(missing_ok=True)

import openpyxl  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app import config, security, servicios  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Estado, Invitacion  # noqa: E402
from app.templating import hora_local  # noqa: E402

fallos = []


def check(nombre, condicion, extra=""):
    print(("OK   " if condicion else "FALLA") + "  " + nombre + ("  " + str(extra) if extra else ""))
    if not condicion:
        fallos.append(nombre)


def leer(inv_id):
    with Session(engine) as s:
        inv = s.get(Invitacion, inv_id)
        if inv is None:
            return None
        return {
            "estado": inv.estado, "confirmados": inv.confirmados, "ingresados": inv.ingresados,
            "filas": [(str(g.id), g.tipo.value, g.nombre, g.asiste) for g in inv.invitados],
        }


def contar_grupos(nombre):
    with Session(engine) as s:
        return len(s.exec(select(Invitacion).where(Invitacion.nombre_grupo == nombre)).all())


def importar(texto, codificacion="utf-8"):
    datos = texto.encode(codificacion) if isinstance(texto, str) else texto
    return c.post("/admin/importar", files={"archivo": ("lista.csv", datos, "text/csv")})


init_db()
c = TestClient(app)
clave = "clave-test-1"

# --- alta desde el panel ---
c.post("/admin/login", data={"password": clave})
check("login solo con la contraseña", c.get("/admin", follow_redirects=False).status_code == 200)
r = c.post("/admin/invitaciones/nueva",
           data={"nombre_grupo": "Familia Prueba", "cupo_adultos": "2", "cupo_ninos": "1",
                 "telefono": "5492611234567", "tarjeta_fisica": "1"}, follow_redirects=False)
check("alta de invitacion", r.status_code == 303, r.status_code)
inv_id = int(r.headers["location"].rsplit("/", 1)[1])
with Session(engine) as s:
    inv = s.get(Invitacion, inv_id)
    codigo = inv.codigo
    check("crea 3 slots de invitado", len(inv.invitados) == 3, len(inv.invitados))
    check("marca la tarjeta como fisica", inv.tarjeta_fisica is True)
filas = leer(inv_id)["filas"]
adultos = [f[0] for f in filas if f[1] == "adulto"]
nino = [f[0] for f in filas if f[1] == "nino"][0]

# --- validaciones del alta ---
for nombre, datos, texto in [
    ("alta: nombre en blanco", {"nombre_grupo": "   ", "cupo_adultos": "2"}, "no puede quedar vac"),
    ("alta: cupo 0 + 0", {"nombre_grupo": "Cero", "cupo_adultos": "0", "cupo_ninos": "0"}, "al menos un lugar"),
    ("alta: cupo 20000", {"nombre_grupo": "Enorme", "cupo_adultos": "20000"}, "entre 0 y 20"),
    ("alta: cupo 'dos'", {"nombre_grupo": "Texto", "cupo_adultos": "dos"}, "entre 0 y 20"),
    ("alta: cupo negativo", {"nombre_grupo": "Neg", "cupo_adultos": "-1"}, "entre 0 y 20"),
]:
    r = c.post("/admin/invitaciones/nueva", data=datos)
    check(nombre + " se rechaza con aviso",
          r.status_code == 200 and texto in r.text and contar_grupos(datos["nombre_grupo"]) == 0)

# --- invitacion publica ---
r = c.get("/i/" + codigo)
check("invitacion personalizada", r.status_code == 200 and "Familia Prueba" in r.text)
check("el formulario manda invitado_id y no el tipo", 'name="invitado_id"' in r.text and 'name="tipo"' not in r.text)
r = c.get("/i/" + codigo + "/qr.png")
check("QR generado", r.status_code == 200 and r.headers["content-type"] == "image/png" and len(r.content) > 500)
check("codigo inexistente da 404", c.get("/i/ZZZZZZ").status_code == 404)

pendiente = TestClient(app).get("/i/" + codigo)          # sin sesion de staff
check("invitacion pendiente: muestra el formulario",
      pendiente.status_code == 200 and "Enviar respuesta" in pendiente.text)
check("formulario: nadie viene marcado como que asiste",
      'value="si" selected' not in pendiente.text and "Elegí una opción" in pendiente.text)
check("invitacion pendiente: todavia no muestra el codigo QR",
      "Tu código para ese día" not in pendiente.text)

# --- RSVP: lo que no se puede ---
r = c.post("/i/" + codigo + "/rsvp", data={
    "nombre": [f"P{i}" for i in range(10)], "tipo": ["adulto"] * 10,
    "asiste": ["si"] * 10, "restriccion": [""] * 10}, follow_redirects=False)
check("RSVP con mas personas que el cupo se rechaza",
      r.status_code == 303 and "editar=1" in r.headers["location"]
      and leer(inv_id)["estado"] == Estado.pendiente and len(leer(inv_id)["filas"]) == 3)
check("el rechazo muestra el aviso en la invitacion", "La invitación cambió" in c.get(r.headers["location"]).text)
r = c.post("/i/" + codigo + "/rsvp", data={
    "invitado_id": adultos + [nino, "999999"], "nombre": ["A", "B", "C", "D"],
    "asiste": ["si"] * 4, "restriccion": [""] * 4}, follow_redirects=False)
check("RSVP con un id ajeno se rechaza", "editar=1" in r.headers["location"] and leer(inv_id)["confirmados"] == 0)
r = c.post("/i/" + codigo + "/rsvp", data={
    "invitado_id": adultos + [nino], "nombre": ["Ana", "", "Mini"],
    "asiste": ["si", "si", "no"], "restriccion": ["", "", ""]}, follow_redirects=False)
check("RSVP: quien asiste necesita nombre", "editar=1" in r.headers["location"] and leer(inv_id)["confirmados"] == 0)
r = c.post("/i/" + codigo + "/rsvp", data={
    "invitado_id": adultos + [nino], "nombre": ["Ana", "Luis", "Mini"],
    "asiste": ["si", "", "no"], "restriccion": ["", "", ""]}, follow_redirects=False)
check("RSVP: sin elegir asistencia se rechaza",
      "editar=1" in r.headers["location"] and leer(inv_id)["confirmados"] == 0)

# --- RSVP del invitado ---
r = c.post("/i/" + codigo + "/rsvp", data={
    "invitado_id": adultos + [nino], "nombre": ["Ana", "Luis", ""],
    "asiste": ["si", "si", "no"], "restriccion": ["celiaca", "", ""],
    "mensaje": "Felicidades!", "telefono": "5492610000000"}, follow_redirects=False)
check("RSVP acepta respuesta (quien no va puede quedar sin nombre)",
      r.status_code == 303 and "ok=1" in r.headers["location"])
with Session(engine) as s:
    inv = s.get(Invitacion, inv_id)
    check("estado parcial (2 de 3)", inv.estado == Estado.parcial, inv.estado)
    check("confirmados = 2", inv.confirmados == 2, inv.confirmados)
    check("guarda restriccion", any(g.restriccion == "celiaca" for g in inv.invitados))
    check("guarda mensaje", inv.mensaje == "Felicidades!")
    check("el RSVP no cambia ids ni tipos", sorted(str(g.id) for g in inv.invitados) == sorted(adultos + [nino])
          and sum(1 for g in inv.invitados if g.tipo.value == "nino") == 1)
r = TestClient(app).get("/i/" + codigo)
check("tras confirmar aparece el agradecimiento", "Gracias por confirmar" in r.text)
check("tras confirmar aparece el codigo QR", "Tu código para ese día" in r.text)
check("el invitado no ve nada de 'registrar ingreso'", "Registrar ingreso" not in r.text)
r = TestClient(app).get("/i/" + codigo + "?editar=1")
check("puede volver a editar la respuesta", "Enviar respuesta" in r.text)

# --- puerta ---
sin_sesion = TestClient(app)
r = sin_sesion.get("/pase/" + codigo, follow_redirects=False)
check("QR viejo /pase redirige al link unico",
      r.status_code == 301 and r.headers["location"] == "/i/" + codigo)
r = sin_sesion.get("/admin", follow_redirects=False)
check("admin exige login", r.status_code == 303 and "/admin/login" in r.headers["location"])
r = sin_sesion.post("/admin/login", data={"password": "clave-mala"}, follow_redirects=False)
check("clave incorrecta no entra", "error=1" in r.headers.get("location", ""))
formulario_login = sin_sesion.get("/admin/login").text
check("el login pide solo la contraseña",
      'name="usuario"' not in formulario_login and 'name="password"' in formulario_login)

r = c.get("/i/" + codigo)
check("staff tambien ve la invitacion por defecto", "Registrar ingreso" not in r.text)
r = c.get("/i/" + codigo + "?puerta=1")
check("staff entra al control con ?puerta=1",
      r.status_code == 200 and "Registrar ingreso" in r.text)
r = sin_sesion.get("/i/" + codigo + "?puerta=1", follow_redirects=False)
check("sin sesion, ?puerta=1 pide login y vuelve a la puerta (nunca muestra el control)",
      r.status_code == 303 and r.headers["location"].startswith("/admin/login")
      and parse_qs(urlsplit(r.headers["location"]).query)["next"] == [f"/i/{codigo}?puerta=1"])
vencida = TestClient(app)
r = vencida.post("/i/" + codigo + "/ingreso", data={"personas": "1"},
                 headers={"referer": f"http://testserver/i/{codigo}?puerta=1"}, follow_redirects=False)
login_url = r.headers["location"]
check("sesion vencida: el ingreso no se registra y el login lo avisa",
      "vencida=1" in login_url and leer(inv_id)["ingresados"] == 0
      and "sesión se venció" in vencida.get(login_url).text)
r = vencida.post("/admin/login", data={"password": clave,
                                        "next": parse_qs(urlsplit(login_url).query)["next"][0]},
                 follow_redirects=False)
check("sesion vencida: tras el login vuelve a la pantalla de puerta (no a un 405)",
      r.headers["location"] == f"/i/{codigo}?puerta=1", r.headers["location"])
r = c.post("/i/" + codigo + "/ingreso", data={"personas": "500"})
check("ingreso por encima del cupo se rechaza",
      "Solo quedan 3 de 3" in r.text and leer(inv_id)["ingresados"] == 0)
r = c.post("/i/" + codigo + "/ingreso", data={"personas": "abc"})
check("ingreso con cantidad invalida muestra aviso (no JSON)",
      r.status_code == 200 and "mayor a 0" in r.text and leer(inv_id)["ingresados"] == 0)
r = c.post("/i/" + codigo + "/ingreso", data={"personas": "2"}, follow_redirects=False)
check("registrar ingreso redirige (PRG)", r.status_code == 303 and "hecho=1" in r.headers["location"])
r = c.get(r.headers["location"])
check("registra ingreso", r.status_code == 200 and "Ingreso registrado" in r.text)
check("el ingreso queda registrado como staff", "2 pers. (staff)" in r.text)
c.get("/i/" + codigo + "?puerta=1&hecho=1")                     # recargar la pantalla
check("ingresados = 2 (recargar no duplica)", leer(inv_id)["ingresados"] == 2)
r = c.post("/admin/invitaciones/" + str(inv_id),
           data={"nombre_grupo": "Familia Prueba", "cupo_adultos": "1", "cupo_ninos": "0"})
check("no deja bajar el cupo por debajo de los que ya ingresaron",
      "ya ingresaron 2" in r.text and len(leer(inv_id)["filas"]) == 3)
with Session(engine) as s:
    momento = s.get(Invitacion, inv_id).checkins[0].at
ficha = c.get("/admin/invitaciones/" + str(inv_id)).text
check("la ficha muestra el ingreso en hora de Mendoza", hora_local(momento) in ficha and " UTC" not in ficha)
c.post("/admin/invitaciones/" + str(inv_id) + "/deshacer-ingreso", follow_redirects=False)
check("deshacer ingreso vuelve a 0", leer(inv_id)["ingresados"] == 0)

# --- pantallas del panel ---
for ruta in ["/admin", "/admin/invitaciones", "/admin/invitaciones/nueva", "/admin/escaner",
             "/admin/invitaciones/" + str(inv_id), "/admin/invitaciones/" + str(inv_id) + "/tarjeta"]:
    check("pantalla " + ruta, c.get(ruta).status_code == 200)

# --- CSV ---
r = importar("grupo;adultos;ninos;telefono;email\nFamilia CSV;2;0;5492611111111;a@b.com\n")
check("importa CSV", r.status_code == 200 and "Se importaron 1 invitaciones" in r.text)
r = importar("grupo;adultos;ninos\nFamilia CSV;2;0\nOtra CSV;1;0\n")
check("CSV: grupo repetido se omite y se informa",
      "Se omitieron 1" in r.text and contar_grupos("Familia CSV") == 1 and contar_grupos("Otra CSV") == 1)
r = importar("grupo;adultos\nDoble;1\nDoble;1\n")
check("CSV: repetido dentro del archivo se informa como tal",
      "repetido en el archivo" in r.text and contar_grupos("Doble") == 1)
r = importar("grupo;adultos;ninos\nImp A;2;0\nImp B;2;0\nImp C;dos;0\nImp D;-1;0\n")
check("CSV con filas invalidas no importa nada",
      "No se importó nada" in r.text and "Línea 4" in r.text and "Línea 5" in r.text
      and contar_grupos("Imp A") == 0)
r = importar("Grupo;Adultos;Niños\nMayúsculas;2;1\n")
check("CSV: encabezados con mayusculas y tildes", contar_grupos("Mayúsculas") == 1)
r = importar("grupo,adultos\nFamilia Pérez Excel,2\n", "cp1252")
check("CSV guardado por Excel (cp1252)", contar_grupos("Familia Pérez Excel") == 1)
r = importar(b"PK\x03\x04\x00\x00binario")
check("CSV: archivo binario se rechaza", "no es un CSV de texto" in r.text)
r = importar("nombre;adultos\nSin columna;2\n")
check("CSV: falta columna grupo", "Falta la columna" in r.text and contar_grupos("Sin columna") == 0)
r = c.get("/admin/invitaciones?formato=fisica")
check("filtro solo fisicas", "Familia Prueba" in r.text and "Familia CSV" not in r.text)
r = c.get("/admin/invitaciones?formato=virtual")
check("filtro solo virtuales", "Familia CSV" in r.text and "Familia Prueba" not in r.text)
r = c.get("/admin/export.csv")
check("exporta CSV", r.status_code == 200 and "Familia CSV" in r.text)
check("el CSV trae la columna formato", "formato" in r.text.splitlines()[0] and ";fisica;" in r.text)

# --- edicion: estado calculado y cupo ---
base = {"nombre_grupo": "Familia Prueba", "cupo_adultos": "2", "cupo_ninos": "1",
        "invitado_id": adultos + [nino], "nombre": ["Ana", "Luis", "Mini"], "restriccion": ["", "", ""]}
c.post("/admin/invitaciones/" + str(inv_id), data={**base, "asiste": ["si", "si", "si"]})
check("admin marca todos: estado confirmada", leer(inv_id)["estado"] == Estado.confirmada)
r = c.post("/admin/invitaciones/" + str(inv_id),
           data={**base, "nombre": ["Ana", "", "Mini"], "asiste": ["si", "si", "no"]})
check("panel: no deja marcar que asiste sin nombre",
      "completar el nombre" in r.text and leer(inv_id)["estado"] == Estado.confirmada)
c.post("/admin/invitaciones/" + str(inv_id), data={**base, "asiste": ["sin", "sin", "sin"]})
check("admin borra respuestas: estado pendiente", leer(inv_id)["estado"] == Estado.pendiente)
c.post("/admin/invitaciones/" + str(inv_id), data={**base, "asiste": ["no", "no", "no"]})
check("admin marca que nadie va: estado rechazada", leer(inv_id)["estado"] == Estado.rechazada)
c.post("/admin/invitaciones/" + str(inv_id), data={**base, "asiste": ["si", "si", "no"]})

r = c.post("/admin/invitaciones/" + str(inv_id),
           data={"nombre_grupo": "Familia Prueba", "cupo_adultos": "1", "cupo_ninos": "0"})
check("no deja bajar el cupo por debajo de los confirmados",
      "No se puede bajar el cupo de adultos" in r.text and len(leer(inv_id)["filas"]) == 3)
r = c.post("/admin/invitaciones/" + str(inv_id),
           data={**base, "cupo_adultos": "1", "cupo_ninos": "0", "asiste": ["si", "no", "no"]})
datos = leer(inv_id)
check("bajar cupo ajusta invitados", len(datos["filas"]) == 1, len(datos["filas"]))
check("bajar cupo conserva al confirmado", datos["filas"][0][2:] == ("Ana", True), datos["filas"])
check("bajar cupo recalcula el estado", datos["estado"] == Estado.confirmada, datos["estado"])
c.post("/admin/invitaciones/" + str(inv_id), data={"nombre_grupo": "Familia Prueba", "cupo_adultos": "3"})
check("subir cupo deja la invitacion parcial", leer(inv_id)["estado"] == Estado.parcial)

# --- manejo de errores ---
check("filtro de estado invalido no rompe", c.get("/admin/invitaciones?estado=foo").status_code == 200)
r = c.get("/no-existe")
check("ruta inexistente: 404 en HTML", r.status_code == 404 and "text/html" in r.headers["content-type"])
r = c.get("/i/" + codigo + "?puerta=abc")
check("parametro invalido: 400 en HTML", r.status_code == 400 and "text/html" in r.headers["content-type"])
original = servicios.crear_invitacion


def _base_bloqueada(*a, **k):
    raise OperationalError("INSERT", {}, Exception("database is locked"))


servicios.crear_invitacion = _base_bloqueada
r = c.post("/admin/invitaciones/nueva", data={"nombre_grupo": "Bloqueada", "cupo_adultos": "1"})
servicios.crear_invitacion = original
check("base bloqueada: 503 con pagina amigable",
      r.status_code == 503 and "No se guardó nada" in r.text and contar_grupos("Bloqueada") == 0)

# --- seguridad y limites ---
r = c.post("/admin/invitaciones/nueva", data={"nombre_grupo": "Familia Formula", "cupo_adultos": "1"},
           follow_redirects=False)
f_id = int(r.headers["location"].rsplit("/", 1)[1])
with Session(engine) as s:
    f_cod = s.get(Invitacion, f_id).codigo
rsvp_f = {"invitado_id": [f[0] for f in leer(f_id)["filas"]], "nombre": ["=1+1"], "asiste": ["si"],
          "restriccion": ["-2"], "mensaje": "@SUMA(A1)", "telefono": "+5492615550000"}
c.post(f"/i/{f_cod}/rsvp", data=rsvp_f)
exportado = c.get("/admin/export.csv").text
check("CSV exportado neutraliza formulas",
      "'=1+1:si" in exportado and "'@SUMA(A1)" in exportado and ";=1+1" not in exportado)

r = c.get("/admin/export.xlsx")
check("descarga Excel", r.status_code == 200 and "spreadsheetml" in r.headers["content-type"])
libro = openpyxl.load_workbook(io.BytesIO(r.content))
check("Excel: hojas", libro.sheetnames == ["Lista de seguridad", "Invitaciones"], libro.sheetnames)
filas_seguridad = list(libro["Lista de seguridad"].iter_rows(min_row=2, values_only=True))
personas = [f[1] for f in filas_seguridad if isinstance(f[0], int)]
with Session(engine) as s:
    total_confirmados = sum(i.confirmados for i in s.exec(select(Invitacion)).all())
check("Excel: una fila por persona confirmada, en orden alfabetico",
      len(personas) == total_confirmados and "Ana" in personas and "=1+1" in personas
      and personas == sorted(personas, key=str.casefold), personas)
check("Excel: total al pie", any(f[1] and str(f[1]).startswith(f"Total confirmados: {total_confirmados}")
                                 for f in filas_seguridad))
with zipfile.ZipFile(io.BytesIO(r.content)) as z:
    hojas_xml = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
check("Excel: ningun texto se guarda como formula", "<f>" not in hojas_xml)
check("Excel: telefono intacto (sin apostrofe ni notacion cientifica)",
      "+5492615550000" in [v for f in libro["Invitaciones"].iter_rows(values_only=True) for v in f])

r = c.post(f"/i/{f_cod}/rsvp", data={**rsvp_f, "nombre": ["Ana"], "mensaje": "x" * 1001})
check("RSVP: mensaje demasiado largo se rechaza",
      "hasta 1000 caracteres" in r.text and leer(f_id)["filas"][0][2] == "=1+1")
r = c.post(f"/i/{f_cod}/rsvp", data={**rsvp_f, "nombre": ["x" * 81]})
check("RSVP: nombre demasiado largo se rechaza", "hasta 80 caracteres" in r.text)
r = c.post(f"/admin/invitaciones/{f_id}",
           data={"nombre_grupo": "Familia Formula", "cupo_adultos": "1", "notas": "x" * 1001})
check("panel: notas demasiado largas se rechazan", "hasta 1000 caracteres" in r.text)
r = c.post(f"/i/{f_cod}/rsvp", data={**rsvp_f, "mensaje": "x" * 2_100_000})
check("cuerpo de mas de 2 MB: 413", r.status_code == 413, r.status_code)

limite_original = config.FECHA_LIMITE_RSVP
config.FECHA_LIMITE_RSVP = "2000-01-01"
r = TestClient(app).get(f"/i/{f_cod}?editar=1")
check("RSVP cerrado: sin formulario ni boton de modificar",
      "Gracias por confirmar" in r.text and "Enviar respuesta" not in r.text
      and "Modificar mi respuesta" not in r.text)
r = c.post(f"/i/{f_cod}/rsvp", data={**rsvp_f, "nombre": ["Ana"]})
check("RSVP cerrado: el POST se rechaza",
      "cerró el 01/01/2000" in r.text and leer(f_id)["filas"][0][2] == "=1+1")
r = c.post("/admin/invitaciones/nueva", data={"nombre_grupo": "Familia Tarde", "cupo_adultos": "1"},
           follow_redirects=False)
with Session(engine) as s:
    tarde = s.get(Invitacion, int(r.headers["location"].rsplit("/", 1)[1])).codigo
r = TestClient(app).get("/i/" + tarde)
check("RSVP cerrado: el pendiente ve el aviso de cierre",
      "Confirmación cerrada" in r.text and "Enviar respuesta" not in r.text)
config.FECHA_LIMITE_RSVP = limite_original

for destino, esperado in [("https://evil.example", "/admin"), ("//evil.example", "/admin"),
                          ("/\\evil.example", "/admin"), ("/\t/evil.example", "/admin"),
                          ("/admin/escaner", "/admin/escaner")]:
    r = TestClient(app).post("/admin/login", data={"password": clave, "next": destino},
                             follow_redirects=False)
    check(f"login con next={destino!r} va a {esperado}", r.headers["location"] == esperado,
          r.headers["location"])

r = c.post("/admin/invitaciones/nueva", data={"nombre_grupo": "Familia D'Angelo", "cupo_adultos": "2"})
check("apostrofe en el nombre no rompe la confirmacion de borrado",
      'data-grupo="Familia D&#39;Angelo"' in r.text and "this.dataset.grupo" in r.text
      and "confirm('Eliminar la invitación de Familia" not in r.text)

with engine.connect() as k:
    check("SQLite valida claves foraneas", k.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1)
    check("SQLite en modo WAL", k.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal")

security._fallidos.clear()
atacante = TestClient(app)
for _ in range(security.MAX_INTENTOS):
    r = atacante.post("/admin/login", data={"password": "mala"}, follow_redirects=False)
check("5 claves incorrectas bloquean el login", "error=2" in r.headers["location"], r.headers["location"])
r = atacante.post("/admin/login", data={"password": clave}, follow_redirects=False)
check("bloqueado: ni la clave correcta entra",
      "error=2" in r.headers["location"] and atacante.get("/admin", follow_redirects=False).status_code == 303)
check("el login avisa el bloqueo", "Demasiados intentos" in atacante.get(r.headers["location"]).text)
security._fallidos.clear()

config.DETRAS_DE_PROXY = True
uno = TestClient(app, headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"})
for _ in range(security.MAX_INTENTOS):
    uno.post("/admin/login", data={"password": "mala"})
r = TestClient(app, headers={"X-Forwarded-For": "2.2.2.2"}).post(
    "/admin/login", data={"password": clave}, follow_redirects=False)
check("detras de proxy: el bloqueo es por la IP real de cada uno", r.headers["location"] == "/admin")
r = TestClient(app, headers={"X-Forwarded-For": "5.5.5.5, 1.1.1.1"}).post(
    "/admin/login", data={"password": clave}, follow_redirects=False)
check("detras de proxy: inventar X-Forwarded-For no esquiva el bloqueo", "error=2" in r.headers["location"])
config.DETRAS_DE_PROXY = False
security._fallidos.clear()

config.DETRAS_DE_PROXY, config.IP_DE_CLOUDFLARE = True, True
for _ in range(security.MAX_INTENTOS):
    TestClient(app, headers={"CF-Connecting-IP": "3.3.3.3", "X-Forwarded-For": "7.7.7.7"}).post(
        "/admin/login", data={"password": "mala"})
r = TestClient(app, headers={"CF-Connecting-IP": "4.4.4.4", "X-Forwarded-For": "7.7.7.7"}).post(
    "/admin/login", data={"password": clave}, follow_redirects=False)
check("Cloudflare: el bloqueo es por la IP de CF-Connecting-IP", r.headers["location"] == "/admin")
r = TestClient(app, headers={"CF-Connecting-IP": "3.3.3.3", "X-Forwarded-For": "8.8.8.8"}).post(
    "/admin/login", data={"password": clave}, follow_redirects=False)
check("Cloudflare: cambiar X-Forwarded-For no esquiva el bloqueo", "error=2" in r.headers["location"])
config.DETRAS_DE_PROXY, config.IP_DE_CLOUDFLARE = False, False
security._fallidos.clear()

check("healthcheck /salud", TestClient(app).get("/salud").json() == {"ok": True})
check("respaldo exige login", TestClient(app).get("/admin/respaldo.db", follow_redirects=False).status_code == 303)
r = c.get("/admin/respaldo.db")
copia = sqlite3.connect(":memory:")
if r.content.startswith(b"SQLite format 3"):
    copia.deserialize(r.content)
    en_copia = copia.execute("SELECT count(*) FROM invitacion").fetchone()[0]
else:
    en_copia = -1
with Session(engine) as s:
    en_base = len(s.exec(select(Invitacion)).all())
check("respaldo: copia completa de la base", en_copia == en_base, (en_copia, en_base))
copia.close()

otro = TestClient(app)
otro.post("/admin/login", data={"password": clave})
check("otra persona entra con la misma contraseña", otro.get("/admin", follow_redirects=False).status_code == 200)
config.ADMIN_PASSWORD = "clave-nueva"
check("cambiar la contraseña cierra todas las sesiones abiertas",
      otro.get("/admin", follow_redirects=False).status_code == 303
      and c.get("/admin", follow_redirects=False).status_code == 303)
config.ADMIN_PASSWORD = ""
r = TestClient(app).post("/admin/login", data={"password": ""}, follow_redirects=False)
check("sin ADMIN_PASSWORD configurada nadie entra", "error=1" in r.headers["location"])
config.ADMIN_PASSWORD = clave
security._fallidos.clear()
check("con la contraseña de antes la sesion vuelve a valer", c.get("/admin", follow_redirects=False).status_code == 200)

# --- borrado ---
c.post("/admin/invitaciones/" + str(inv_id) + "/eliminar", follow_redirects=False)
with Session(engine) as s:
    check("elimina invitacion", s.get(Invitacion, inv_id) is None)
    check("borra invitados en cascada",
          not s.exec(select(Invitacion).where(Invitacion.id == inv_id)).first())

print()
print("FALLAS: " + (", ".join(fallos) if fallos else "ninguna"))
engine.dispose()
RUTA.unlink(missing_ok=True)
raise SystemExit(1 if fallos else 0)
