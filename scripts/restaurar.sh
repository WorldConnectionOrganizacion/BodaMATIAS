#!/usr/bin/env bash
# Reemplaza la base por un respaldo (Docker), con la app andando.
# Uso: scripts/restaurar.sh respaldos/boda-AAAAMMDD-HHMMSS.db
set -euo pipefail
cd "$(dirname "$0")/.."

archivo="${1:?Uso: scripts/restaurar.sh respaldos/boda-AAAAMMDD-HHMMSS.db}"
[ -f "$archivo" ] || { echo "No existe $archivo"; exit 1; }

read -r -p "Esto reemplaza TODOS los datos actuales por $archivo. Escribí 'si' para seguir: " respuesta
[ "$respuesta" = "si" ] || { echo "Cancelado: no se tocó nada."; exit 1; }

echo "Antes, respaldo de lo actual:"
scripts/respaldo.sh

docker compose exec -T app sh -c 'cat > /tmp/restaurar.db' < "$archivo"
docker compose exec -T app python - <<'PY'
import sqlite3

origen = sqlite3.connect("/tmp/restaurar.db")
if origen.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    raise SystemExit("El respaldo esta dañado: no se restauro nada.")
destino = sqlite3.connect("/app/data/boda.db")
origen.backup(destino)   # reemplaza el contenido de la base en uso de forma atomica
destino.close()
origen.close()
PY
docker compose exec -T app rm -f /tmp/restaurar.db
echo "Base restaurada desde $archivo"
