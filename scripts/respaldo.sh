#!/usr/bin/env bash
# Copia consistente de la base, con la app andando (Docker). Deja el archivo en ./respaldos del
# host y conserva los ultimos 30. Para uno diario ver README (cron).
set -euo pipefail
cd "$(dirname "$0")/.."

nombre="boda-$(date +%Y%m%d-%H%M%S).db"
mkdir -p respaldos

docker compose exec -T app python - "$nombre" <<'PY'
import sqlite3
import sys

destino = "/tmp/" + sys.argv[1]
origen = sqlite3.connect("/app/data/boda.db")
copia = sqlite3.connect(destino)
origen.backup(copia)                           # API de backup: consistente aunque haya escrituras
copia.execute("PRAGMA journal_mode=DELETE")    # archivo suelto, sin depender de un -wal
copia.close()
origen.close()
PY

docker compose cp "app:/tmp/$nombre" "respaldos/$nombre"
docker compose exec -T app rm -f "/tmp/$nombre"

ls -1t respaldos/boda-*.db | tail -n +31 | xargs -r rm --
echo "Respaldo guardado en respaldos/$nombre"
