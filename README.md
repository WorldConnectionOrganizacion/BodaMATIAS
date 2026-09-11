# Boda Sofía & Matías — invitación + gestión de invitados

Invitación web personalizada por grupo familiar, con confirmación de asistencia (RSVP),
base de datos SQLite y control de ingreso por código QR en la puerta del salón.

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python seed.py        # opcional: crea invitaciones de ejemplo
.\run.ps1                           # levanta el servidor en http://localhost:8000
```

O sin script: `.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Configuración: archivo `.env`

Toda la configuración vive en `.env`, en la raíz del proyecto (hay un `.env.example` de referencia).
Se lee al importar `app.config`; una variable ya definida en el sistema tiene prioridad sobre el `.env`.

| Variable | Default | Para qué |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | URL pública. **Es lo que queda grabado dentro de cada QR**: definirla antes de generar los QR definitivos. |
| `PUERTO` | `8000` | Puerto local donde escucha uvicorn (lo lee `run.ps1`). |
| `ADMIN_PASSWORD` | — | Contraseña del panel y del control de puerta (no se pide usuario). Sin ella nadie puede entrar. No se escribe en el repo: solo en `.env` o en las variables de Railway. |
| `SECRET_KEY` | valor de ejemplo | Firma de la cookie de sesión. Cambiala. |
| `DB_URL` | `sqlite:///data/boda.db` | Base de datos. |

**Después de tocar `.env` hay que reiniciar el servidor**: `uvicorn --reload` recarga el código, no las
variables de entorno. Para verificar qué está usando: al arrancar imprime `BASE_URL en uso: ...`, y el
tablero del panel lo muestra arriba de todo.

En PowerShell: `$env:BASE_URL="https://boda.midominio.com"` antes de levantar el servidor.

### Publicado en internet

`run.ps1` levanta en `0.0.0.0:8000` con `BASE_URL=http://201.252.170.251:9000`: el router redirige
el 9000 de afuera al 8000 de esta máquina, y `BASE_URL` siempre lleva el puerto público porque es
lo que queda grabado dentro de cada QR. Con la app expuesta:

- Definí `ADMIN_PASSWORD` y `SECRET_KEY` propias: `/admin` queda accesible desde cualquier lado y, sobre HTTP
  plano, la clave y la cookie de sesión viajan sin cifrar. El servidor avisa por consola si quedaron
  los valores de ejemplo.
- El escáner por cámara necesita HTTPS (los navegadores solo lo permiten en contexto seguro o
  `localhost`). Sobre HTTP funciona la carga manual del código. Para tener cámara: poner un dominio
  con certificado adelante (Caddy, Nginx + Let's Encrypt, o un túnel tipo Cloudflare).
- La IP pública es dinámica en la mayoría de las conexiones hogareñas: si cambia, los QR ya impresos
  dejan de funcionar. Conviene un dominio (o DNS dinámico) antes de repartir QR.

## Deploy en la PC de la empresa (Docker + Cloudflare Tunnel)

La app corre en Docker y el dominio llega por un túnel de Cloudflare: no hace falta abrir puertos en
el router ni tener IP fija, y el HTTPS lo pone Cloudflare. La app no queda expuesta en la red local;
solo la alcanza el túnel.

**Requisitos:** Ubuntu/Debian con [Docker Engine y el plugin compose](https://docs.docker.com/engine/install/ubuntu/)
(`sudo systemctl enable --now docker` para que arranque solo con la PC) y el dominio gestionado en
Cloudflare (alcanza el plan gratis).

1. **Túnel:** en Cloudflare, Zero Trust → Networks → Tunnels → *Create a tunnel* (tipo Cloudflared).
   Copiar el token que muestra. En *Public Hostname* cargar el subdominio (ej. `boda.tuempresa.com`)
   con servicio `HTTP` y URL `app:8000`.
2. **Configuración:** clonar el repo, `cp .env.example .env` y completar:
   - `BASE_URL=https://boda.tuempresa.com` — la URL final, queda grabada en cada QR.
   - `ADMIN_PASSWORD` y `SECRET_KEY` (generarla con `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).
   - `CLOUDFLARE_TUNNEL_TOKEN` con el token del paso 1.
3. **Levantar:** `docker compose up -d --build`. `docker compose ps` tiene que mostrar `app` como
   *healthy*, y `docker compose logs app` muestra `BASE_URL en uso`.
4. **Actualizar:** `git pull && docker compose up -d --build`. La base no se toca.

La base (`/app/data/boda.db`) vive en el volumen `datos` de Docker y sobrevive a reinicios y
actualizaciones. **`docker compose down -v` la borra**: nunca usar `-v`.

La IP real de cada visitante llega en `CF-Connecting-IP` (`DETRAS_DE_PROXY=cloudflare`, ya definido en
`docker-compose.yml`), así el bloqueo del login es por persona y no uno para todos.

**Respaldos:** `scripts/respaldo.sh` guarda una copia consistente en `respaldos/` con la app andando y
conserva las últimas 30. Para uno diario a las 4 AM: `crontab -e` y agregar
`0 4 * * * /ruta/al/repo/scripts/respaldo.sh` (el usuario del cron tiene que estar en el grupo `docker`).
Conviene copiar `respaldos/` a otro disco o a la nube. Para volver a un respaldo:
`scripts/restaurar.sh respaldos/boda-AAAAMMDD-HHMMSS.db` (pide confirmación y antes respalda lo actual).

**Probar sin el túnel**, en la misma PC: `docker compose run --rm -p 127.0.0.1:8000:8000 -e DETRAS_DE_PROXY=0 app`
y abrir `http://localhost:8000`.

## Deploy en Railway

Un solo servicio con la base SQLite en un **Volume**. El disco del contenedor se borra en cada
deploy: sin Volume se pierden todas las confirmaciones.

1. New Project → Deploy from GitHub repo. Railway construye con el `Dockerfile` del repo y
   `railway.json` define el arranque (`python iniciar.py`), el healthcheck (`/salud`) y el reinicio ante
   fallas. La imagen corre con un usuario sin privilegios: agregar la variable `RAILWAY_RUN_UID=0`
   para que pueda escribir en el Volume.
2. En el servicio: **Add Volume**, con mount path `/app/data`. Cualquier ruta sirve porque la app usa
   la que informa Railway (`RAILWAY_VOLUME_MOUNT_PATH`). **No definir `DB_URL`.**
3. Variables del servicio (el `.env` no se sube):
   - `ADMIN_PASSWORD` — la contraseña del panel.
   - `SECRET_KEY` — generarla con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   - `BASE_URL` — la URL pública final, con `https://`.
   - `PORT` lo pone Railway solo.
4. Settings → Networking → Generate Domain (o Custom Domain). **Definir el dominio antes de mandar
   links o imprimir QR**: quedan grabados con `BASE_URL` y los que ya se repartieron no cambian.
5. Una sola réplica: la base SQLite y el bloqueo del login viven en esa instancia.
6. Al arrancar, los logs muestran `BASE_URL en uso` y un `AVISO GRAVE` si la base no quedó en el Volume.

Detrás del proxy de Railway la IP real de cada cliente llega en `X-Forwarded-For`. La app la toma de
ahí sola (`DETRAS_DE_PROXY`, automático en Railway), así el bloqueo del login es por la IP de cada
persona y no uno solo para todos.

**Backup:** Tablero → *Respaldo de la base* descarga una copia de `boda.db`.

**Pruebas:** `pip install -r requirements-dev.txt` y después `python test_smoke.py`.

## Rutas

**Público**

- `/` — invitación general, sin datos personales.
- `/i/{codigo}` — **link único del grupo**: RSVP + QR de ingreso. Es el mismo link que se manda por
  WhatsApp y el que codifica el QR.
- `/i/{codigo}/qr.png` — imagen del QR de ese grupo.

**Staff** (requieren login en `/admin/login`)

- `/admin` — tablero: confirmados, pendientes, ingresos, restricciones alimentarias, mensajes.
- `/admin/invitaciones` — listado con búsqueda y filtro por estado.
- `/admin/invitaciones/nueva` — alta de grupo con cupo de adultos y niños.
- `/admin/invitaciones/{id}` — ficha: editar datos, invitados, estado, ver ingresos, link de WhatsApp.
- `/admin/invitaciones/{id}/tarjeta` — tarjeta imprimible con QR.
- `/admin/escaner` — escáner de cámara (Chrome/Android) o carga manual del código.
- `/admin/export.xlsx` — Excel con la lista de seguridad (una fila por persona confirmada, lista para
  imprimir) y el detalle de las invitaciones. `/admin/export.csv` — lo mismo en CSV, una fila por grupo.
- `/admin/respaldo.db` — copia consistente de la base, se puede bajar con el servidor andando.
- `/admin/importar` — carga masiva desde CSV.
- `/salud` — healthcheck (responde si la base contesta).
- `/i/{codigo}` con sesión staff — el mismo link muestra el control de puerta.
  Con `?vista=invitacion` el staff previsualiza lo que ve el invitado.
- `/pase/{codigo}` — redirección permanente al link único (compatibilidad con QR viejos).

## Cómo funciona el QR

**Un solo link por grupo.** Cada invitación tiene un `codigo` de 6 caracteres (sin I/O/0/1 para evitar
confusiones) y el QR codifica exactamente el mismo link que se manda por WhatsApp: `BASE_URL/i/{codigo}`.
La página se adapta a quién la abre:

- Un invitado que lo escanea ve su invitación.
- El staff logueado ve nombre del grupo, cupo, confirmados, restricciones alimentarias y el botón
  **Registrar ingreso**, que guarda un `Checkin` con cuántas personas entraron y quién lo registró.
- Si el grupo ya entró completo, la pantalla lo avisa antes de registrar de nuevo.
- El último ingreso se puede deshacer desde la ficha o desde la pantalla de puerta.

## La presentación (front)

- **Sobre lacrado**: la invitación abre con un sobre cerrado con sello dorado con las iniciales.
  Al tocarlo se abre la solapa en 3D, sale la carta con el nombre del grupo y recién ahí aparece
  la página. Se muestra una sola vez por sesión (`sessionStorage`), y se saltea si el link trae ancla.
- **Revelados al scroll**: cada bloque entra con fade + desplazamiento usando `IntersectionObserver`,
  con retardo escalonado dentro de cada grupo (tarjetas, countdown, campos del formulario).
- **Detalles**: barra de progreso de lectura, barra flotante con los nombres y botón *Confirmar*,
  pétalos flotando en la portada, parallax suave del bloque de nombres, ornamentos SVG que se
  dibujan solos, línea del itinerario que se pinta, latido del countdown en cada segundo,
  alias de Mercado Pago que se copia con un toque, botón de RSVP que pasa a *Enviando…*.
- **Rendimiento y accesibilidad**: solo se animan `transform` y `opacity`, el scroll usa
  `requestAnimationFrame`, se respeta `prefers-reduced-motion` y hay `<noscript>` + red de
  seguridad ante errores de JS para que nunca quede contenido invisible.

## Modelo de datos

- `Invitacion` — codigo, nombre_grupo, cupo_adultos, cupo_ninos, telefono, email,
  `tarjeta_fisica` (se entrega impresa o es solo link), estado
  (`pendiente` / `confirmada` / `parcial` / `rechazada`), mensaje, notas.
- `Invitado` — nombre, tipo (`adulto` / `nino`), asiste (sí / no / sin respuesta), restricción alimentaria.
- `Checkin` — personas, fecha/hora, operador.

## Importar la lista de invitados

CSV con encabezado (separador `;` o `,`). La columna `fisica` marca la tarjeta impresa
(`si` / `1` / `x`, o vacío para virtual):

```csv
grupo;adultos;ninos;telefono;email;fisica
Familia Pérez;2;1;5492611111111;perez@mail.com;si
Juan y Carla;2;0;5492612222222;;
```

## Tarjetas físicas vs. virtuales

Al crear la invitación (antes de cargar los invitados) hay un checkbox **Tarjeta física**. Sirve solo
para tenerlas identificadas: quién recibe la tarjeta impresa en mano y quién solo el link.

- En el listado hay una columna **Formato** y un filtro *Solo tarjeta física / Solo virtuales*.
- El tablero muestra el total de cada tipo, con acceso directo a la lista filtrada.
- El CSV exportado trae la columna `formato` con `fisica` o `virtual`.
- Se puede cambiar después desde la ficha del grupo.

## Notas de despliegue

- Antes de mandar las invitaciones: definir `BASE_URL` real, `ADMIN_PASSWORD` y `SECRET_KEY`.
- La cámara del escáner necesita HTTPS (salvo en `localhost`).
- La base es un archivo en `data/boda.db` en modo WAL: con el servidor andando, los últimos cambios
  pueden estar todavía en `data/boda.db-wal`. Backup en caliente:
  `.venv\Scripts\python -c "import sqlite3; sqlite3.connect('data/boda.db').backup(sqlite3.connect('data/copia.db'))"`,
  o frenar el servidor y copiar `data/boda.db`.
- La confirmación (RSVP) cierra al terminar el día `FECHA_LIMITE_RSVP` (hora de Mendoza, en
  `app/config.py`). Después el invitado ya no puede modificar su respuesta; los cambios se hacen desde
  la ficha del panel.
- El login bloquea una IP por 5 minutos después de 5 contraseñas incorrectas. Si se pone un proxy
  adelante (Caddy, Nginx, túnel), uvicorn tiene que recibir la IP real (`--proxy-headers` y
  `--forwarded-allow-ips`); si no, todos comparten el mismo contador y un ataque bloquea también al staff.
- Con `BASE_URL` en `https://` la cookie del panel se marca `Secure` (solo viaja cifrada).
- Cambiar `ADMIN_PASSWORD` y reiniciar el servidor cierra en el acto todas las sesiones abiertas del panel.
