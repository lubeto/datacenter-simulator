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

        # Modo clase guiada
        self._guided_active = False
        self._guided_name: str = ""
        self._guided_steps: list = []
        self._guided_current_step: int = 0
        self._guided_task: Optional[asyncio.Task] = None
        self._guided_auto_attacks_was: bool = True  # para restaurar al terminar

    def set_broadcast_callback(self, cb: Callable):
        """Callback para enviar eventos por WebSocket."""
        self._broadcast_cb = cb

    def set_db_callback(self, cb: Callable):
        """Callback para guardar en DB."""
        self._db_save_cb = cb

    async def start(self):
        """Inicia todos los loops del scheduler."""
        self._running = True
        logger.info("Scheduler iniciado")
        await asyncio.gather(
            self._metrics_loop(),
            self._auto_attack_loop(),
            self._ssl_check_loop(),
            self._sst_monitor_loop(),
            self._escalation_loop(),
        )

    async def stop(self):
        self._running = False

    # ----------------------------------------------------------
    # LOOP DE METRICAS (cada 2 segundos)
    # ----------------------------------------------------------
    async def _metrics_loop(self):
        from .engine import generate_full_snapshot, tick_attacks
        _db_tick = 0
        while self._running:
            try:
                if not sim_state.is_paused:
                    tick_attacks()
                snapshot = generate_full_snapshot()
                snapshot["paused"] = sim_state.is_paused

                if self._broadcast_cb:
                    await self._broadcast_cb("metrics", snapshot)

                _db_tick += 1
                if self._db_save_cb and _db_tick >= 15:
                    await self._db_save_cb("metrics", snapshot)
                    _db_tick = 0

            except Exception as e:
                logger.error(f"Error en metrics_loop: {e}")
            await asyncio.sleep(2)

    # ----------------------------------------------------------
    # LOOP DE ATAQUES AUTOMATICOS
    # ----------------------------------------------------------
    async def _auto_attack_loop(self):
        import os
        auto_enabled = os.getenv("AUTO_ATTACK_ENABLED", "true").lower() == "true"
        min_min = int(os.getenv("AUTO_ATTACK_MIN_INTERVAL_MIN", "1"))
        max_min = int(os.getenv("AUTO_ATTACK_MAX_INTERVAL_MIN", "3"))
        max_concurrent = int(os.getenv("AUTO_ATTACK_MAX_CONCURRENT", "2"))

        def _has_manual_attack() -> bool:
            return any(
                not a.get("auto_injected", True)
                for a in sim_state.active_attacks.values()
            )

        while self._running:
            wait_sec = random.randint(min_min * 60, max_min * 60)
            elapsed = 0

            while elapsed < wait_sec and self._running:
                await asyncio.sleep(10)
                elapsed += 10
                if _has_manual_attack():
                    elapsed = 0

            if not self._running:
                break

            if not auto_enabled or not self._auto_attacks:
                continue

            if sim_state.is_paused:
                continue

            if _has_manual_attack():
                continue

            if len(sim_state.active_attacks) >= max_concurrent:
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

            logger.info(f"Auto-ataque: {result['name']} -> {scenario['node_id']}")

            if self._broadcast_cb:
                await self._broadcast_cb("new_incident", {
                    "type": "auto_attack",
                    "attack": result,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"NUEVO INCIDENTE: {result['name']} detectado en {scenario['node_id']}"
                })

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

    # ----------------------------------------------------------
    # LOOP DE MONITOREO SSL (cada 60 segundos)
    # ----------------------------------------------------------
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
                    days = self._simulate_cert_days(node.id)
                    now = datetime.utcnow()
                    expires_at = now + timedelta(days=days)

                    is_expired = days <= 0
                    tls_version = self._simulate_tls_version(node.id)
                    is_self_signed = random.random() < 0.05

                    alert_level = "normal"
                    alert_msg = ""
                    if is_expired:
                        alert_level = "critical"
                        alert_msg = "Certificado EXPIRADO"
                    elif days <= 7:
                        alert_level = "critical"
                        alert_msg = f"Certificado vence en {days} dias"
                    elif days <= 30:
                        alert_level = "warning"
                        alert_msg = f"Certificado vence en {days} dias"
                    elif tls_version in ("TLSv1.0", "TLSv1.1"):
                        alert_level = "warning"
                        alert_msg = f"Version TLS insegura: {tls_version}"
                    elif is_self_signed:
                        alert_level = "warning"
                        alert_msg = "Certificado auto-firmado en produccion"

                    cert_data = {
                        "domain": node.ssl_domain or f"{node.id.lower()}.datacenter.edu",
                        "issuer": "Let's Encrypt" if not is_self_signed else "Self-Signed",
                        "tls_version": tls_version,
                        "cipher_suite": "TLS_AES_256_GCM_SHA384",
                        "days_to_expire": days,
                        "expires_at": expires_at.isoformat(),
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

    # ----------------------------------------------------------
    # LOOP DE MONITOREO SST (cada 5 segundos)
    # ----------------------------------------------------------
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

    # ----------------------------------------------------------
    # LOOP DE ESCALADO DE ALERTAS (cada 10 segundos)
    # ----------------------------------------------------------
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
                if sim_state.is_paused:
                    continue
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

                        if elapsed > 900:
                            await crud.detect_incident(db, inc.id, 0)
                            await db.commit()
                            continue

                        if elapsed >= auto_t and self._broadcast_cb:
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

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------
    _cert_days_cache: dict = {}

    def _simulate_cert_days(self, node_id: str) -> int:
        """Simula dias restantes del certificado. Consistente por nodo."""
        if node_id not in self._cert_days_cache:
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
        """Simula version TLS del nodo."""
        r = random.random()
        if r < 0.60: return "TLSv1.3"
        if r < 0.85: return "TLSv1.2"
        if r < 0.95: return "TLSv1.1"
        return "TLSv1.0"

    def set_auto_attacks(self, enabled: bool):
        self._auto_attacks = enabled

    # ----------------------------------------------------------
    # MODO CLASE GUIADA
    # ----------------------------------------------------------
    def guided_session_active(self) -> bool:
        return self._guided_active

    def start_guided_session(self, name: str, steps: list, disable_auto: bool = True):
        """Inicia la sesion guiada y lanza el loop asincrono."""
        self._guided_name = name
        self._guided_steps = steps
        self._guided_current_step = 0
        self._guided_active = True
        if disable_auto:
            self._guided_auto_attacks_was = self._auto_attacks
            self._auto_attacks = False
        self._guided_task = asyncio.create_task(self._guided_session_loop())

    def stop_guided_session(self):
        """Detiene la sesion guiada."""
        self._guided_active = False
        self._auto_attacks = self._guided_auto_attacks_was
        if self._guided_task and not self._guided_task.done():
            self._guided_task.cancel()
        self._guided_task = None

    def get_guided_status(self) -> dict:
        if not self._guided_active:
            return {"active": False}
        total = len(self._guided_steps)
        current = self._guided_current_step
        return {
            "active": True,
            "name": self._guided_name,
            "total_steps": total,
            "current_step": current,
            "steps_done": current,
            "steps_remaining": total - current,
            "steps": [
                {
                    "index": i,
                    "attack_type": s["attack_type"],
                    "node_id": s["node_id"],
                    "intensity": s.get("intensity", 0.7),
                    "delay_before_sec": s.get("delay_before_sec", 60),
                    "status": "done" if i < current else ("running" if i == current else "pending"),
                }
                for i, s in enumerate(self._guided_steps)
            ],
        }

    async def _get_step_stats(self, incident_id: int, step_info: dict) -> dict:
        """Consulta estadisticas de deteccion para un paso de clase guiada."""
        from ..database.db import AsyncSessionLocal
        from ..database.models import Incident, Session as EvalSession, Student
        from sqlalchemy import select as sa_select, func as sa_func

        was_detected = False
        detected_by = None
        mttd_seconds = None
        active_students = 0

        try:
            async with AsyncSessionLocal() as db:
                inc_q = await db.execute(sa_select(Incident).where(Incident.id == incident_id))
                inc = inc_q.scalar_one_or_none()
                if inc:
                    was_detected = inc.detected_at is not None
                    mttd_seconds = inc.mttd_seconds
                    if inc.session_id:
                        sess_q = await db.execute(sa_select(EvalSession).where(EvalSession.id == inc.session_id))
                        sess = sess_q.scalar_one_or_none()
                        if sess:
                            stu_q = await db.execute(sa_select(Student).where(Student.id == sess.student_id))
                            stu = stu_q.scalar_one_or_none()
                            if stu:
                                detected_by = stu.name

                count_q = await db.execute(
                    sa_select(sa_func.count(EvalSession.id)).where(EvalSession.ended_at.is_(None))
                )
                active_students = count_q.scalar() or 0
        except Exception as e:
            logger.error(f"Error en _get_step_stats: {e}")

        step_num = step_info.get("step_index", 0) + 1
        mttd_fmt = f"{mttd_seconds:.1f}s" if mttd_seconds is not None else "--"
        atk_name = step_info.get("attack_name", step_info.get("attack_type", ""))
        node_id = step_info.get("node_id", "")

        return {
            "incident_id": incident_id,
            "step_num": step_num,
            "attack_name": atk_name,
            "node_id": node_id,
            "was_detected": was_detected,
            "detected_by": detected_by,
            "mttd_seconds": mttd_seconds,
            "active_students": active_students,
            "message": (
                f"Paso {step_num} -- "
                f"{'Detectado por ' + detected_by if detected_by else 'Sin deteccion'} . "
                f"MTTD: {mttd_fmt} . {active_students} activos"
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _guided_session_loop(self):
        """Ejecuta los pasos de la sesion guiada en orden, con stats por paso."""
        logger.info(f"Sesion guiada '{self._guided_name}' iniciada ({len(self._guided_steps)} pasos)")

        prev_incident_id = None
        prev_step_info = None

        try:
            for i, step in enumerate(self._guided_steps):
                if not self._guided_active:
                    break

                self._guided_current_step = i
                delay = step.get("delay_before_sec", 60)
                total = len(self._guided_steps)

                # Broadcast stats del paso ANTERIOR antes de la siguiente cuenta regresiva
                if prev_incident_id is not None and self._broadcast_cb:
                    try:
                        stats = await self._get_step_stats(prev_incident_id, prev_step_info)
                        await self._broadcast_cb("guided_step_stats", stats)
                    except Exception as e:
                        logger.warning(f"Error al broadcast step_stats: {e}")

                # Notificar cuenta regresiva
                if self._broadcast_cb:
                    await self._broadcast_cb("guided_step_countdown", {
                        "step_index": i,
                        "step_num": i + 1,
                        "total_steps": total,
                        "attack_type": step["attack_type"],
                        "node_id": step["node_id"],
                        "delay_before_sec": delay,
                        "message": f"Paso {i+1}/{total}: '{step['attack_type']}' en {step['node_id']} en {delay}s",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                # Esperar delay (en trozos de 5s para poder cancelar)
                waited = 0
                while waited < delay and self._guided_active:
                    await asyncio.sleep(min(5, delay - waited))
                    waited += 5

                if not self._guided_active:
                    break

                # Lanzar ataque
                result = attack_manager.inject_attack(
                    attack_type=step["attack_type"],
                    node_id=step["node_id"],
                    intensity=step.get("intensity", 0.7),
                    duration_sec=step.get("duration_sec", 120),
                )
                logger.info(f"Paso {i+1}: {result.get('name')} -> {step['node_id']}")

                # Guardar incidente directamente para obtener el incident_id
                incident_id = None
                try:
                    from ..database.db import AsyncSessionLocal
                    from ..database.models import Incident as _Inc
                    from ..simulation.mitigation import mitigation_engine as _mit_engine
                    async with AsyncSessionLocal() as db:
                        inc = _Inc(
                            incident_type=step["attack_type"],
                            category=result.get("category", "attack"),
                            severity=result.get("severity", "warning"),
                            node_affected=step["node_id"],
                            description=f"[CLASE GUIADA] {result.get('description', '')}",
                            started_at=datetime.utcnow(),
                            status="active",
                        )
                        db.add(inc)
                        await db.commit()
                        await db.refresh(inc)
                        incident_id = inc.id
                        try:
                            _mit_engine.register_suggestion(incident_id, step["attack_type"], step["node_id"])
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Error guardando incidente guiado: {e}")
                    # fallback sin retorno de id
                    if self._db_save_cb:
                        await self._db_save_cb("incident", {
                            "incident_type": step["attack_type"],
                            "category": result.get("category", "attack"),
                            "severity": result.get("severity", "warning"),
                            "node_affected": step["node_id"],
                            "description": f"[CLASE GUIADA] {result.get('description', '')}",
                            "started_at": datetime.utcnow(),
                            "status": "active",
                        })

                prev_incident_id = incident_id
                prev_step_info = {
                    "step_index": i,
                    "attack_type": step["attack_type"],
                    "attack_name": result.get("name", step["attack_type"]),
                    "node_id": step["node_id"],
                }

                # Broadcast paso lanzado
                if self._broadcast_cb:
                    await self._broadcast_cb("guided_step_launched", {
                        "step_index": i,
                        "step_num": i + 1,
                        "total_steps": total,
                        "attack": result,
                        "attack_name": result.get("name", step["attack_type"]),
                        "node_id": step["node_id"],
                        "incident_id": incident_id,
                        "message": f"[Clase Guiada] Paso {i+1}/{total}: {result.get('name')} en {step['node_id']}",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

        except asyncio.CancelledError:
            logger.info("Sesion guiada cancelada")
        except Exception as e:
            logger.error(f"Error en guided_session_loop: {e}")
        finally:
            if self._guided_active:
                # Stats del ultimo paso antes de completar
                if prev_incident_id is not None and self._broadcast_cb:
                    try:
                        stats = await self._get_step_stats(prev_incident_id, prev_step_info)
                        await self._broadcast_cb("guided_step_stats", stats)
                    except Exception as e:
                        logger.warning(f"Error al broadcast step_stats final: {e}")

                self._guided_active = False
                self._auto_attacks = self._guided_auto_attacks_was
                self._guided_current_step = len(self._guided_steps)
                if self._broadcast_cb:
                    await self._broadcast_cb("guided_session_completed", {
                        "name": self._guided_name,
                        "total_steps": len(self._guided_steps),
                        "message": f"Sesion guiada '{self._guided_name}' completada",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                logger.info(f"Sesion guiada '{self._guided_name}' completada")


# Instancia global
scheduler = EventScheduler()
