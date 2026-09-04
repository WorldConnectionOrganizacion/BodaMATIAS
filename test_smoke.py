"""Prueba de humo de punta a punta, contra una base temporal.

Uso:  .venv\\Scripts\\python test_smoke.py
No toca data/boda.db: crea y borra data/test_smoke.db.
"""
import os
import pathlib

RUTA = pathlib.Path("data/test_smoke.db")
os.environ["DB_URL"] = "sqlite:///data/test_smoke.db"
os.environ.setdefault("ADMIN_PASSWORD", "boda2026")
RUTA.parent.mkdir(exist_ok=True)
RUTA.unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Estado, Invitacion  # noqa: E402

fallos = []


def check(nombre, condicion, extra=""):
    print(("OK   " if condicion else "FALLA") + "  " + nombre + ("  " + str(extra) if extra else ""))
    if not condicion:
        fallos.append(nombre)


init_db()
c = TestClient(app)
clave = os.environ["ADMIN_PASSWORD"]

# --- alta desde el panel ---
c.post("/admin/login", data={"password": clave, "operador": "Test"})
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

# --- invitacion publica ---
r = c.get("/i/" + codigo)
check("invitacion personalizada", r.status_code == 200 and "Familia Prueba" in r.text)
r = c.get("/i/" + codigo + "/qr.png")
check("QR generado", r.status_code == 200 and r.headers["content-type"] == "image/png" and len(r.content) > 500)
check("codigo inexistente da 404", c.get("/i/ZZZZZZ").status_code == 404)

pendiente = TestClient(app).get("/i/" + codigo)          # sin sesion de staff
check("invitacion pendiente: muestra el formulario",
      pendiente.status_code == 200 and "Enviar respuesta" in pendiente.text)
check("invitacion pendiente: todavia no muestra el codigo QR",
      "Tu código para ese día" not in pendiente.text)

# --- RSVP del invitado ---
r = c.post("/i/" + codigo + "/rsvp", data={
    "nombre": ["Ana", "Luis", "Mini"], "tipo": ["adulto", "adulto", "nino"],
    "asiste": ["si", "si", "no"], "restriccion": ["celiaca", "", ""],
    "mensaje": "Felicidades!", "telefono": "5492610000000"}, follow_redirects=False)
check("RSVP acepta respuesta", r.status_code == 303)
with Session(engine) as s:
    inv = s.get(Invitacion, inv_id)
    check("estado parcial (2 de 3)", inv.estado == Estado.parcial, inv.estado)
    check("confirmados = 2", inv.confirmados == 2, inv.confirmados)
    check("guarda restriccion", any(g.restriccion == "celiaca" for g in inv.invitados))
    check("guarda mensaje", inv.mensaje == "Felicidades!")
r = sin_sesion_previo = TestClient(app).get("/i/" + codigo)
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

r = c.get("/i/" + codigo)
check("staff tambien ve la invitacion por defecto", "Registrar ingreso" not in r.text)
r = c.get("/i/" + codigo + "?puerta=1")
check("staff entra al control con ?puerta=1",
      r.status_code == 200 and "Registrar ingreso" in r.text)
r = sin_sesion.get("/i/" + codigo + "?puerta=1")
check("invitado NUNCA ve el control de puerta", "Registrar ingreso" not in r.text)
r = c.post("/i/" + codigo + "/ingreso", data={"personas": "2"})
check("registra ingreso", r.status_code == 200 and "Ingreso registrado" in r.text)
with Session(engine) as s:
    check("ingresados = 2", s.get(Invitacion, inv_id).ingresados == 2)
c.post("/admin/invitaciones/" + str(inv_id) + "/deshacer-ingreso", follow_redirects=False)
with Session(engine) as s:
    check("deshacer ingreso vuelve a 0", s.get(Invitacion, inv_id).ingresados == 0)

# --- pantallas del panel ---
for ruta in ["/admin", "/admin/invitaciones", "/admin/invitaciones/nueva", "/admin/escaner",
             "/admin/invitaciones/" + str(inv_id), "/admin/invitaciones/" + str(inv_id) + "/tarjeta"]:
    check("pantalla " + ruta, c.get(ruta).status_code == 200)

# --- CSV ---
csv = "grupo;adultos;ninos;telefono;email\nFamilia CSV;2;0;5492611111111;a@b.com\n"
r = c.post("/admin/importar", files={"archivo": ("lista.csv", csv.encode("utf-8"), "text/csv")},
           follow_redirects=False)
check("importa CSV", r.status_code == 303)
r = c.get("/admin/invitaciones?formato=fisica")
check("filtro solo fisicas", "Familia Prueba" in r.text and "Familia CSV" not in r.text)
r = c.get("/admin/invitaciones?formato=virtual")
check("filtro solo virtuales", "Familia CSV" in r.text and "Familia Prueba" not in r.text)
r = c.get("/admin/export.csv")
check("exporta CSV", r.status_code == 200 and "Familia CSV" in r.text)
check("el CSV trae la columna formato", "formato" in r.text.splitlines()[0] and ";fisica;" in r.text)

# --- edicion y borrado ---
r = c.post("/admin/invitaciones/" + str(inv_id),
           data={"nombre_grupo": "Familia Prueba", "cupo_adultos": "1", "cupo_ninos": "0"},
           follow_redirects=False)
with Session(engine) as s:
    check("bajar cupo ajusta invitados", len(s.get(Invitacion, inv_id).invitados) == 1)
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
