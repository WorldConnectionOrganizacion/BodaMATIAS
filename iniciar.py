"""Arranque de produccion (Docker, Railway):  python iniciar.py

Toma el puerto de $PORT (lo asigna Railway) o de PUERTO, y la interfaz de HOST (por defecto todas).
Sin --reload y en un solo proceso: la base SQLite y el bloqueo del login viven en esta instancia.
Para desarrollo usar run.sh / run.ps1.
"""
import os

import uvicorn

from app import config

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT") or config.PUERTO),
        proxy_headers=False,  # la IP real detras del proxy la resuelve app.security (DETRAS_DE_PROXY)
    )
