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
| `ADMIN_PASSWORD` | `boda2026` | Contraseña del panel y del control de puerta. Cambiala. |
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

- Cambiá `ADMIN_PASSWORD` y `SECRET_KEY`: `/admin` queda accesible desde cualquier lado y, sobre HTTP
  plano, la clave y la cookie de sesión viajan sin cifrar. El servidor avisa por consola si quedaron
  los valores de ejemplo.
- El escáner por cámara necesita HTTPS (los navegadores solo lo permiten en contexto seguro o
  `localhost`). Sobre HTTP funciona la carga manual del código. Para tener cámara: poner un dominio
  con certificado adelante (Caddy, Nginx + Let's Encrypt, o un túnel tipo Cloudflare).
- La IP pública es dinámica en la mayoría de las conexiones hogareñas: si cambia, los QR ya impresos
  dejan de funcionar. Conviene un dominio (o DNS dinámico) antes de repartir QR.

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
- `/admin/export.csv` — exporta todo. `/admin/importar` — carga masiva desde CSV.
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
- La base es un archivo en `data/boda.db`: copiarlo es todo el backup.
