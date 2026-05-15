# =============================================================================
# DC Monitoring Simulator — Dockerfile de Producción
# Build multi-stage: builder → runtime slim con usuario no-root
# =============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Solo dependencias de compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias en directorio isolado (no en sistema)
COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="DC Monitoring Simulator"
LABEL description="Simulador de Centro de Datos para prácticas estudiantiles"
LABEL version="1.0.0"

# Variables de entorno de Python y seguridad
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.11/site-packages:/app"

# Copiar dependencias compiladas desde el builder
COPY --from=builder /install /install

# Crear usuario no-root para ejecutar la app
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/false appuser

WORKDIR /app

# Copiar código fuente
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Crear directorios necesarios y asignar permisos
RUN mkdir -p data/reports_output logs && \
    chown -R appuser:appuser /app

# Cambiar al usuario no-root
USER appuser

# Exponer puerto
EXPOSE 8000

# Health check robusto con curl-less Python
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "\
import urllib.request, sys; \
req = urllib.request.urlopen('http://localhost:8000/health', timeout=8); \
sys.exit(0 if req.status == 200 else 1)"

# Comando de inicio con configuración de producción
CMD ["python", "-m", "uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info", \
     "--access-log", \
     "--no-use-colors"]
