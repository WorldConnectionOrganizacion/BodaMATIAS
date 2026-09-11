# Imagen de produccion de la invitacion (FastAPI + SQLite).
# PC de la empresa: se usa desde docker-compose.yml. Railway tambien construye con este archivo.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY iniciar.py .

# Usuario sin privilegios. La base vive en /app/data, que docker-compose monta como volumen.
RUN useradd --create-home --uid 1000 boda \
    && mkdir -p /app/data \
    && chown boda:boda /app/data
USER boda

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=4)"

CMD ["python", "iniciar.py"]
