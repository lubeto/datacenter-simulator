"""
DC Monitoring Simulator - Servidor Principal FastAPI
Punto de entrada de la aplicación
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from .middleware.security import SecurityHeadersMiddleware, RequestLoggingMiddleware

from dotenv import load_dotenv
load_dotenv()

from .database.db import init_db, get_db, AsyncSessionLocal
from .database import crud
from .database.models import Student
from .auth.jwt_handler import hash_password, decode_token
from .api.routes_students import router as students_router, auth_router
from .api.routes_metrics  import router as metrics_router
from .api.routes_attacks  import router as attacks_router
from .api.routes_reports  import router as reports_router
from .api.routes_analytics import router as analytics_router
from .api.routes_bitacoras import router as bitacoras_router
from .api.routes_sessions  import router as sessions_router
from .api.routes_admin     import router as admin_router
from .api.websocket       import manager as ws_manager
from .simulation.scheduler import scheduler
from .simulation.engine   import generate_full_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("dc.main")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


# ============================================================
# CALLBACKS DEL SCHEDULER
# ============================================================
async def broadcast_callback(event_type: str, data):
    await ws_manager.broadcast(event_type, data)


async def db_save_callback(data_type: str, data):
    """Persiste datos en la base de datos de forma asíncrona."""
    async with AsyncSessionLocal() as db:
        try:
            if data_type == "metrics":
                # Guardar métricas de cada nodo
                for node_id, node_data in data.get("nodes", {}).items():
                    m = node_data.get("metrics", {})
                    await crud.save_metric(db, node_id, node_data.get("type", ""), {
                        "cpu_pct":         m.get("cpu_pct", 0),
                        "ram_pct":         m.get("ram_pct", 0),
                        "disk_io_mbps":    m.get("disk_io_mbps", 0),
                        "disk_used_pct":   m.get("disk_used_pct", 0),
                        "net_in_mbps":     m.get("net_in_mbps", 0),
                        "net_out_mbps":    m.get("net_out_mbps", 0),
                        "latency_ms":      m.get("latency_ms", 0),
                        "packet_loss_pct": m.get("packet_loss_pct", 0),
                        "connections":     m.get("connections", 0),
                        "is_online":       m.get("is_online", True),
                        "uptime_pct":      m.get("uptime_pct", 99.9),
                    })

            elif data_type == "incident":
                await crud.create_incident(db, data)

            elif data_type == "ssl_certs":
                for cert in data:
                    node_id = cert.pop("node_id", None)
                    if node_id:
                        await crud.upsert_ssl_cert(db, node_id, cert)

            elif data_type == "sst_readings":
                for reading in data:
                    sensor_id = reading.get("sensor_id")
                    zone = reading.get("zone", "")
                    stype = reading.get("type", "")
                    if sensor_id:
                        await crud.save_sst_reading(db, sensor_id, stype, zone, {
                            k: v for k, v in reading.items()
                            if k not in ("sensor_id", "type", "zone", "id", "name", "unit",
                                         "sensor_name", "alert_level")
                        })

            await db.commit()
        except Exception as e:
            logger.warning(f"db_save_callback error ({data_type}): {e}")
            await db.rollback()


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando DC Monitoring Simulator...")

    # Inicializar base de datos
    await init_db()
    logger.info("✅ Base de datos inicializada")

    # Crear usuario administrador/instructor por defecto
    async with AsyncSessionLocal() as db:
        admin_email = os.getenv("ADMIN_EMAIL", "instructor@datacenter.edu")
        existing = await crud.get_student_by_email(db, admin_email)
        if not existing:
            await crud.create_student(
                db,
                name=os.getenv("ADMIN_NAME", "Instructor Principal"),
                email=admin_email,
                password_hash=hash_password(os.getenv("ADMIN_PASSWORD", "Admin1234!")),
                role="instructor"
            )
            logger.info(f"✅ Usuario instructor creado: {admin_email}")

    # Configurar callbacks del scheduler
    scheduler.set_broadcast_callback(broadcast_callback)
    scheduler.set_db_callback(db_save_callback)

    # Iniciar scheduler en background
    scheduler_task = asyncio.create_task(scheduler.start())
    logger.info("✅ Scheduler de simulación iniciado")

    # Limpieza inmediata al arrancar + cada hora (retener solo últimas 6h de métricas)
    async def _cleanup_loop():
        # Primera limpieza al inicio para liberar espacio si el disco estaba lleno
        try:
            async with AsyncSessionLocal() as db:
                deleted = await crud.cleanup_old_metrics(db, keep_hours=6)
                logger.info(f"🧹 Limpieza inicial: {deleted} registros eliminados")
        except Exception as e:
            logger.warning(f"cleanup inicial error: {e}")
        # Luego repetir cada hora
        while True:
            await asyncio.sleep(3600)
            try:
                async with AsyncSessionLocal() as db:
                    deleted = await crud.cleanup_old_metrics(db, keep_hours=6)
                    if deleted:
                        logger.info(f"🧹 Limpieza automática: {deleted} registros eliminados")
            except Exception as e:
                logger.warning(f"cleanup_loop error: {e}")
    asyncio.create_task(_cleanup_loop())
    logger.info("🖥️  Dashboard disponible en: http://localhost:8000")
    logger.info("📚 API Docs en: http://localhost:8000/docs")

    yield

    # Shutdown
    logger.info("🛑 Deteniendo simulador...")
    await scheduler.stop()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("👋 Simulador detenido")


# ============================================================
# APLICACIÓN FASTAPI
# ============================================================
app = FastAPI(
    title="DC Monitoring Simulator",
    description="Simulador de Centro de Datos para prácticas estudiantiles",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _raw_origins.strip() == "*":
    _allowed_origins = ["*"]
    _allow_cred = False   # credentials no compatibles con wildcard
else:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _allow_cred = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_cred,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# ── Security headers ──────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Request logging ───────────────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)

# Montar archivos estáticos del frontend
if os.path.exists(os.path.join(FRONTEND_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Registrar routers de API
app.include_router(auth_router)
app.include_router(students_router)
app.include_router(metrics_router)
app.include_router(attacks_router)
app.include_router(reports_router)
app.include_router(analytics_router)
app.include_router(bitacoras_router)
app.include_router(sessions_router)
app.include_router(admin_router)


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket principal para datos en tiempo real."""
    student_info = None

    # Intentar autenticar via query param
    token = websocket.query_params.get("token")
    if token:
        payload = decode_token(token)
        if payload:
            student_info = {
                "id": int(payload.get("sub", 0)),
                "email": payload.get("email"),
                "role": payload.get("role"),
            }

    await ws_manager.connect(websocket, student_info)
    logger.info(f"WS cliente conectado. Activos: {ws_manager.count}")

    # Enviar snapshot inicial
    try:
        snapshot = generate_full_snapshot()
        await ws_manager.send_to(websocket, "metrics", snapshot)
        await ws_manager.send_to(websocket, "connected", {
            "message": "Conectado al DC Monitoring Simulator",
            "student": student_info,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error enviando snapshot inicial: {e}")

    try:
        while True:
            data = await websocket.receive_text()
            # Manejar mensajes del cliente (ping, commands)
            import json
            try:
                msg = json.loads(data)
                cmd = msg.get("cmd")
                if cmd == "ping":
                    await ws_manager.send_to(websocket, "pong", {"ts": datetime.utcnow().isoformat()})
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info(f"WS cliente desconectado. Activos: {ws_manager.count}")


# ============================================================
# RUTAS DE PÁGINAS HTML
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def index():
    """Landing inteligente: redirige a login si no hay sesión, o al panel según rol."""
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>body{background:#0a0e1a;margin:0}</style>
<script>
  var token = localStorage.getItem('token');
  var student = {};
  try { student = JSON.parse(localStorage.getItem('student') || '{}'); } catch(e) {}
  if (!token || !student.id) {
    location.replace('/login');
  } else if (student.role === 'instructor') {
    location.replace('/instructor');
  } else {
    location.replace('/dashboard');
  }
</script>
</head><body></body></html>""")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Panel del estudiante."""
    html_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>DC Simulator</h1><p>Frontend not found</p>")


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    html_path = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Login</h1>")


@app.get("/instructor", response_class=HTMLResponse)
async def instructor_page():
    html_path = os.path.join(FRONTEND_DIR, "instructor.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Instructor Panel</h1>")


@app.get("/reports-page", response_class=HTMLResponse)
async def reports_page():
    html_path = os.path.join(FRONTEND_DIR, "reports.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Reports</h1>")


@app.get("/analytics-page", response_class=HTMLResponse)
async def analytics_page():
    html_path = os.path.join(FRONTEND_DIR, "analytics.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Analytics</h1>")


# ── Health Check ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "simulator": "running",
        "ws_clients": ws_manager.count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/status")
async def api_status():
    from .simulation.engine import state as sim_state
    from .simulation.attacks import attack_manager
    return {
        "online_nodes": 12 - len(sim_state.offline_nodes),
        "offline_nodes": len(sim_state.offline_nodes),
        "active_attacks": len(sim_state.active_attacks),
        "ws_clients": ws_manager.count,
        "simulated_hour": 