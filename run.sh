#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PYTHON="$DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Entorno virtual no encontrado en .venv. Creándolo..."
    python3 -m venv .venv
    "$DIR/.venv/bin/pip" install -r requirements.txt
fi

PUERTO=$("$PYTHON" -c "from app import config; print(config.PUERTO)")
BASE_URL=$("$PYTHON" -c "from app import config; print(config.BASE_URL)")

echo ""
echo "================================================="
echo "  Boda Sofía & Matías - Servicio Iniciado"
echo "================================================="
echo "BASE_URL (.env):  $BASE_URL"
echo "Escuchando en:    0.0.0.0:$PUERTO"
echo ""
echo "Invitación:  $BASE_URL/"
echo "Local:       http://localhost:$PUERTO/"
echo "Panel Admin: $BASE_URL/admin"
echo "Escáner:     $BASE_URL/admin/escaner"
echo ""
echo "Los QR codifican $BASE_URL/i/{codigo}"
echo "================================================="
echo ""

exec "$DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PUERTO" --reload
