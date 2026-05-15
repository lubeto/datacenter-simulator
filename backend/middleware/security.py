"""
DC Monitoring Simulator — Middleware de Seguridad
Security headers + logging estructurado
"""
import time
import logging
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("dc_simulator.security")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad HTTP a todas las respuestas."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), bluetooth=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "worker-src 'self' blob:;"
        )
        if ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logging estructurado de requests con tiempo de respuesta."""

    SKIP_PATHS = {"/health", "/api/metrics/snapshot"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info("%s %s %d %.1fms ip=%s",
            request.method, request.url.path, response.status_code, elapsed_ms, client_ip)

        return response
