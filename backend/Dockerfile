# ---------- Etapa 1: dependencias en un entorno virtual ----------
FROM python:3.12-slim AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Etapa 2: imagen final ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser . .

# Hash del commit (lo inyecta el pipeline) -> se ve en GET /api/health
ARG GIT_SHA=local
ENV GIT_SHA=$GIT_SHA

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" || exit 1

# 1 worker con hilos: la inicialización (tablas + admin) y OpenTelemetry corren en un solo proceso
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--access-logfile", "-", "wsgi:app"]
