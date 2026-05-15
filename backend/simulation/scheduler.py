"""
DC Monitoring Simulator - Scheduler de Eventos Automáticos
Gestiona: ataques automáticos, mantenimientos programados, actualizaciones SSL
"""
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from .attacks import attack_manager, ATTACK_CATALOG
from .nodes import DC_NODES
from .engine import state as sim_state

logger = logging.getLogger("dc.scheduler")


class EventScheduler:
    """Scheduler de eventos del simulador."""

    def __init__(self):
        self._running = False
        self._auto_attacks = True
        self._attack_interval_min = (5, 20)   # min entre ataques auto
        self._broadcast_cb: Optional[Callable] = None
        self._db_save_cb: Optional[Callable] = None

    def set_broadcast_callback(self, cb: Callable):
        """Callback para enviar eventos por WebSocket."""
        self._broadcast_cb = cb

    def set_db_callback(self, cb: Callable):
        """Callback para guardar en DB."""
        self._db_save_cb = cb

    async def start(self):
        """Inicia todos los loops del scheduler."""
        self._running = True
        logger.info("🕐 Scheduler iniciado")
        await asyncio.gather(
            self._metrics_loop(),
            self._auto_attack_loop(),
            self._ssl_check_loop(),
            self._sst_monitor_loop(),
            self._escalation_loop(),
        )

    async def stop(self):
        self._running = False

    # ──────────────────────────────────────────────────────────
    # LOOP DE MÉTRICAS (cada 2 segundos)
    # ──────────────────────────────────────────────────────────
    async def _metrics_loop(self):
        from .engine import generate_full_snapshot, tick_attacks
        while self._running:
            try:
                tick_attacks()
                snapshot = generate_full_snapshot()

                if self._broadcast_cb:
                    await self._broadcast_cb("metrics", snapshot)

                if self._db_save_cb:
                    await self._db_save_cb("metrics", snapshot)

            except Exception as e:
                logger.error(f"Error en metrics_loop: {e}")
            await asyncio.sleep(2)

    # ──────────────────────────────────────────────────────────
    # LOOP DE ATAQUES AUTOMÁTICOS
    # ──────────────────────────────────────────────────────────
    async def _auto_attack_loop(self):
        import os
        auto_enabled = os.getenv("AUTO_ATTACK_ENABLED", "true").lower() == "true"
        min_min = int(os.getenv("AUTO_ATTACK_MIN_INTERVAL_MIN", "5"))
        max_min = int(os.getenv("AUTO_ATTACK_MAX_INTERVAL_MIN", "20"))

        while self._running:
            # Esperar intervalo aleatorio
            wait_sec = random.randint(min_min * 60, max_min * 60)
            await asyncio.sleep(wait_sec)

            if not self._running:
                break

            if not auto_enabled or not self._auto_attacks:
                continue

            # Solo lanzar si hay pocos ataques activos
            if len(sim_state.active_attacks) >= 2:
                continue

            scenario = attack_manager.get_random_attack_scenario()
            if not scenario:
                continue

            result = attack_manager.inject_attack(
                attack_type=scenario["attack_type"],
                node_id=scenario["node_id"],
                intensity=scenario["intensity"],
                auto=True
            )

            logger.info(f"🚨 Auto-ataque: {result['name']} → {scenario['node_id']}")

            # Notificar por WebSocket
            if self._broadcast_cb:
                await self._broadcast_cb("new_incident", {
                    "type": "auto_attack",
                    "attack": result,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"⚠️ NUEVO INCIDENTE: {result['name']} detectado en {scenario['node_id']}"
                })

            # Guardar incidente en DB
            if self._db_save_cb:
                await self._db_save_cb("incident", {
                    "incident_type": scenario["attack_type"],
                    "category": result.get("category", "attack"),
                    "severity": result.get("severity", "warning"),
                    "node_affected": scenario["node_id"],
                    "description": result.get("description", ""),
                    "started_at": datetime.utcnow(),
                    "status": "active",
                })

    # ──────────────────────────────────────────────────────────
    # LOOP DE MONITOREO SSL (cada 60 segundos)
    # ──────────────────────────────────────────────────────────
    async def _ssl_check_loop(self):
        from .nodes import get_nodes_with_ssl
        import os
        from datetime import datetime, timedelta

        while self._running:
            await asyncio.sleep(60)
            if not self._running:
                break

            try:
                ssl_nodes = get_nodes_with_ssl()
                ssl_status = []

                for node in ssl_nodes:
                    # Simular estado SSL del certificado
                    # En un entorno real, aquí se haría la conexión SSL real
                    days = self._simulate_cert_days(node.id)
                    now = datetime.utcnow()
                    expires_at = now + timedelta(days=days)

                    is_expired = days <= 0
                    tls_version = self._simulate_tls_version(node.id)
                    is_self_signed = random.random() < 0.05  # 5% chance

                    alert_level = "normal"
                    alert_msg = ""
                    if is_expired:
                        alert_level = "critical"
                        alert_msg = "Certificado EXPIRADO"
                    elif days <= 7:
                        alert_level = "critical"
                        alert_msg = f"Certificado vence en {days} días"
                    elif days <= 30:
                        alert_level = "warning"
                        alert_msg = f"Certificado vence en {days} días"
                    elif tls_version in ("TLSv1.0", "TLSv1.1"):
                        alert_level = "warning"
                        alert_msg = f"Versión TLS insegura: {tls_version}"
                    elif is_self_signed:
                        alert_level = "warning"
                        alert_msg = "Certificado auto-firmado en producción"

                    cert_data = {
                        "domain": node.ssl_domain or f"{node.id.lower()}.datacenter.edu",
                        "issuer": "Let's Encrypt" if not is_self_signed else "Self-Signed",
                        "tls_version": tls_version,
                        "cipher_suite": "TLS_AES_256_GCM_SHA384",
                        "days_to_expire": days,
                        "expires_at": expires_at,
                        "is_expired": is_expired,
                        "is_self_signed": is_self_signed,
                        "is_valid": not is_expired and not is_self_signed,
                        "alert_level": alert_level,
                        "alert_message": alert_msg,
                    }
                    ssl_status.append({"node_id": node.id, **cert_data})

                    if self._broadcast_cb and alert_level != "normal":
                        await self._broadcast_cb("ssl_alert", {
                            "node_id": node.id,
                            "domain": cert_data["domain"],
                            "alert_level": alert_level,
                            "message": alert_msg,
                            "timestamp": now.isoformat(),
                        })

                if self._broadcast_cb:
                    await self._broadcast_cb("ssl_status", {"certs": ssl_status})

                if self._db_save_cb:
                    await self._db_save_cb("ssl_certs", ssl_status)

            except Exception as e:
                logger.error(f"Error en ssl_check_loop: {e}")

    # ──────────────────────────────────────────────────────────
    # LOOP DE MONITOREO SST (cada 5 segundos)
    # ──────────────────────────────────────────────────────────
    async def _sst_monitor_loop(self):
        from .engine import generate_sst_reading
        from .nodes import SST_SENSORS

        while self._running:
            await asyncio.sleep(5)
            if not self._running:
                break

            try:
                sst_alerts = []
                for sensor_id, sensor in SST_SENSORS.items():
                    reading = generate_sst_reading(sensor)
                    if reading.get("alert_level") in ("warning", "critical"):
                        sst_alerts.append({
                            "sensor_id": sensor_id,
                            "sensor_name": sensor.name,
                            "zone": sensor.zone,
                            "type": sensor.sensor_type,
                            "alert_level": reading["alert_level"],
                            **reading
                        })

                if sst_alerts and self._broadcast_cb:
                    await self._broadcast_cb("sst_alerts", {
                        "alerts": sst_alerts,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                if self._db_save_cb:
                    await self._db_save_cb("sst_readings", sst_alerts)

            except Exception as e:
                logger.error(f"Error en sst_monitor_loop: {e}")


    # ──────────────────────────────────────────────────────────
    # LOOP DE ESCALADO DE ALERTAS (cada 10 segundos)
    # ──────────────────────────────────────────────────────────
    async def _escalation_loop(self):
        """Escala alertas si los incidentes no se detectan a tiempo."""
        from ..database.db import AsyncSessionLocal
        from ..database import crud
        from ..database.models import Incident
        from sqlalchemy import select
        from .mitigation import ESCALATION_CONFIG
        while self._running:
            try:
                await asyncio.sleep(10)
                async with AsyncSessionLocal() as db:
                    q = select(Incident).where(
                        Incident.status == "active",
                        Incident.detected_at.is_(None)
                    )
                    result = await db.execute(q)
                    active_undetected = result.scalars().all()

                    for inc in active_undetected:
                        if not inc.started_at:
                            continue
                        elapsed = (datetime.utcnow() - inc.started_at).total_seconds()
                        warning_t  = ESCALATION_CONFIG["warning_after_sec"]
                        critical_t = ESCALATION_CONFIG["critical_after_sec"]
                        auto_t     = ESCALATION_CONFIG["auto_detect_after_sec"]

                        if elapsed >= auto_t and self._broadcast_cb:
                            # Auto-detectar con penalizacion
                            await crud.detect_incident(db, inc.id, 0)
                            await db.commit()
                            await self._broadcast_cb("incident_auto_detected", {
                                "incident_id": inc.id,
                                "node":        inc.node_affected,
                                "attack_type": inc.incident_type,
                                "elapsed_sec": round(elapsed, 0),
                                "penalty":     ESCALATION_CONFIG["score_penalty_pct"],
                                "message":     f"Sistema auto-detecto: {inc.incident_type} en {inc.node_affected} tras {elapsed:.0f}s. Penalizacion {ESCALATION_CONFIG['score_penalty_pct']}%",
                                "timestamp":   datetime.utcnow().isoformat(),
                            })
                        elif elapsed >= critical_t and self._broadcast_cb:
                            await self._broadcast_cb("incident_escalated", {
                                "incident_id": inc.id,
                                "level":       "critical",
                                "node":        inc.node_affected,
                                "attack_type": inc.incident_type,
                                "elapsed_sec": round(elapsed, 0),
                                "message":     f"CRITICO: {inc.incident_type} en {inc.node_affected} sin detectar por {elapsed:.0f}s",
                                "timestamp":   datetime.utcnow().isoformat(),
                            })
                        elif elapsed >= warning_t and self._broadcast_cb:
                            await self._broadcast_cb("incident_escalated", {
                                "incident_id": inc.id,
                                "level":       "warning",
                                "node":        inc.node_affected,
                                "attack_type": inc.incident_type,
                                "elapsed_sec": round(elapsed, 0),
                                "message":     f"Alerta: {inc.incident_type} en {inc.node_affected} sin detectar por {elapsed:.0f}s",
                                "timestamp":   datetime.utcnow().isoformat(),
                            })
            except Exception as e:
                logger.warning(f"Error en escalation_loop: {e}")

    # ──────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────
    _cert_days_cache: dict = {}

    def _simulate_cert_days(self, node_id: str) -> int:
        """Simula días restantes del certificado. Consistente por nodo."""
        if node_id not in self._cert_days_cache:
            # Distribuir: 70% > 90 días, 20% 30-90, 7% 7-30, 3% < 7
            r = random.random()
            if r < 0.70:
                days = random.randint(90, 365)
            elif r < 0.90:
                days = random.randint(30, 89)
            elif r < 0.97:
                days = random.randint(7, 29)
            else:
                days = random.randint(-5, 6)
            self._cert_days_cache[node_id] = days
        return self._cert_days_cache[node_id]

    def _simulate_tls_version(self, node_id: str) -> str:
        """Simula versión TLS del nodo."""
        r = random.random()
        if r < 0.60: return "TLSv1.3"
        if r < 0.85: return "TLSv1.2"
        if r < 0.95: return "TLSv1.1"
        return "TLSv1.0"

    def set_auto_attacks(self, enabled: bool):
        self._auto_attacks = enabled


# Instancia global
scheduler = EventScheduler()
