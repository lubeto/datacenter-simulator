"""
DC Monitoring Simulator - Rutas de Ataques e Incidentes
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.db import get_db
from ..database import crud
from ..database.models import Incident
from ..simulation.attacks import attack_manager, ATTACK_CATALOG
from ..simulation.engine import state as sim_state
from ..api.routes_students import get_current_student, require_instructor
from ..api.websocket import manager as ws_manager
from ..api.routes_collab import check_collab_exclusive_lock
from ..utils_time import iso_utc

router = APIRouter(prefix="/api/attacks", tags=["attacks"])


# ── Schemas ──────────────────────────────────────────────────
class InjectAttackRequest(BaseModel):
    attack_type: str
    node_id: str
    intensity: float = 0.7
    duration_sec: Optional[int] = None


class ResolveIncidentRequest(BaseModel):
    incident_id: int
    notes: str = ""
    root_cause: str = ""


class MitigationRequest(BaseModel):
    incident_id: int
    action_taken: str
    action_category: str = ""
    notes: str = ""


class NodeStatusRequest(BaseModel):
    node_id: str
    online: bool


# ── Rutas ────────────────────────────────────────────────────
@router.get("/catalog")
async def get_attack_catalog():
    """Catálogo completo de tipos de ataques y fallos."""
    return {k: {
        "name": v["name"],
        "category": v["category"],
        "severity": v["severity"],
        "description": v["description"],
        "indicators": v["indicators"],
        "mitigation_steps": v["mitigation_steps"],
        "target_types": v["target_types"],
    } for k, v in ATTACK_CATALOG.items()}


@router.post("/inject")
async def inject_attack(
    req: InjectAttackRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Inyectar un ataque manualmente (solo instructores)."""
    result = attack_manager.inject_attack(
        req.attack_type, req.node_id, req.intensity, req.duration_sec
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Registrar sugerencia de mitigacion automatica
    from ..simulation.mitigation import mitigation_engine as _mit_engine

    # Guardar incidente en DB
    incident = await crud.create_incident(db, {
        "incident_type": req.attack_type,
        "category": result.get("category", "attack"),
        "severity": result.get("severity", "warning"),
        "node_affected": req.node_id,
        "description": result.get("description", ""),
        "started_at": datetime.utcnow(),
        "status": "active",
    })

    # Registrar sugerencia de mitigacion
    if incident:
        _mit_engine.register_suggestion(incident.id, req.attack_type, req.node_id)

    # Crear alerta
    await crud.create_alert(db,
        node_id=req.node_id,
        alert_type=req.attack_type,
        severity=result.get("severity", "warning"),
        message=f"[MANUAL] {result['name']} en {req.node_id}",
        incident_id=incident.id
    )

    # Broadcast WebSocket
    await ws_manager.broadcast("new_incident", {
        "incident_id": incident.id,
        "attack": result,
        "message": f"🚨 {result['name']} inyectado en {req.node_id}",
        "timestamp": iso_utc(datetime.utcnow()),
    })

    return {"incident_id": incident.id, "attack": result}


@router.post("/resolve/{node_id}")
async def resolve_attack(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Resolver un ataque activo en un nodo."""
    resolved = attack_manager.resolve_attack(node_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="No hay ataque activo en ese nodo")

    await ws_manager.broadcast("attack_resolved", {
        "node_id": node_id,
        "timestamp": iso_utc(datetime.utcnow()),
        "message": f"✅ Ataque resuelto en {node_id}"
    })
    return {"resolved": True, "node_id": node_id}


@router.get("/active")
async def get_active_attacks():
    """Lista de ataques activos en este momento."""
    return attack_manager.get_active_attacks()


@router.get("/incidents")
async def get_incidents(
    status:  Optional[str] = None,   # 'resolved', 'detected', 'active', None=todos
    limit:   int           = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_student)
):
    """Historial de incidentes con datos del aprendiz que los detectó/resolvió."""
    from sqlalchemy import select as sa_select
    from ..database.models import Session as EvalSession, Student

    q = sa_select(Incident).order_by(Incident.started_at.desc()).limit(limit)
    if status == "resolved":
        q = sa_select(Incident).where(Incident.status == "resolved").order_by(Incident.started_at.desc()).limit(limit)
    elif status == "detected":
        q = sa_select(Incident).where(Incident.status == "detected").order_by(Incident.started_at.desc()).limit(limit)

    result = await db.execute(q)
    incidents = result.scalars().all()

    out = []
    for inc in incidents:
        student_name = None
        student_id   = None
        if inc.session_id:
            sess_q = await db.execute(sa_select(EvalSession).where(EvalSession.id == inc.session_id))
            sess = sess_q.scalar_one_or_none()
            if sess:
                student_id = sess.student_id
                stu_q = await db.execute(sa_select(Student).where(Student.id == sess.student_id))
                stu = stu_q.scalar_one_or_none()
                if stu:
                    student_name = stu.name

        out.append({
            "id":           inc.id,
            "attack_type":  inc.incident_type,
            "node_id":      inc.node_affected,
            "severity":     inc.severity,
            "status":       inc.status,
            "started_at":   iso_utc(inc.started_at) if inc.started_at else None,
            "detected_at":  iso_utc(inc.detected_at) if inc.detected_at else None,
            "resolved_at":  iso_utc(inc.resolved_at) if inc.resolved_at else None,
            "mttd_seconds": round(inc.mttd_seconds, 1) if inc.mttd_seconds else None,
            "mttr_seconds": round(inc.mttr_seconds, 1) if inc.mttr_seconds else None,
            "student_id":   student_id,
            "student_name": student_name or "—",
            "score":        round(inc.mitigation_score, 1) if inc.mitigation_score else None,
        })
    return out


@router.get("/incidents/active")
async def get_active_incidents(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_student)
):
    """Incidentes activos."""
    return await crud.get_active_incidents(db)


@router.post("/incidents/detect")
async def detect_incident(
    incident_id: int,
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """El estudiante marca un incidente como detectado."""
    await check_collab_exclusive_lock(db, current)
    incident = await crud.detect_incident(db, incident_id, session_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    await ws_manager.broadcast("incident_detected", {
        "incident_id": incident_id,
        "detected_by": current.name,
        "mttd_seconds": incident.mttd_seconds,
        "timestamp": iso_utc(datetime.utcnow()),
    })
    # Buscar IP atacante y marcar ataque como "en investigación"
    # para que no se auto-elimine mientras el aprendiz trabaja en él
    node_id = getattr(incident, "node_id", None)
    attacker_ip = None
    if node_id and node_id in sim_state.active_attacks:
        attacker_ip = sim_state.active_attacks[node_id].get("attacker_ip")
        sim_state.active_attacks[node_id]["detected"] = True
        sim_state.active_attacks[node_id]["elapsed_sec"] = 0  # reinicia el contador
        sim_state.active_attacks[node_id]["investigation_deadline_sec"] = 1200  # 20 min

    return {
        "incident_id": incident_id,
        "mttd_seconds": incident.mttd_seconds,
        "message": f"Detectado en {incident.mttd_seconds:.1f}s",
        "attacker_ip": attacker_ip,
    }


@router.post("/incidents/resolve")
async def resolve_incident(
    req: ResolveIncidentRequest,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """El estudiante resuelve un incidente."""
    incident = await crud.resolve_incident(db, req.incident_id, req.notes, req.root_cause)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    await ws_manager.broadcast("incident_resolved", {
        "incident_id": req.incident_id,
        "resolved_by": current.name,
        "mttr_seconds": incident.mttr_seconds,
        "timestamp": iso_utc(datetime.utcnow()),
    })
    return {
        "incident_id": req.incident_id,
        "mttr_seconds": incident.mttr_seconds,
        "message": f"Resuelto en {incident.mttr_seconds:.1f}s"
    }


@router.post("/mitigate")
async def log_mitigation_action(
    req: MitigationRequest,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Registrar una acción de mitigación del estudiante."""
    await check_collab_exclusive_lock(db, current)
    action = await crud.log_mitigation(
        db, req.incident_id, current.id,
        req.action_taken, req.action_category,
        correct=True, effectiveness=85.0,
        notes=req.notes
    )
    return {"action_id": action.id, "logged": True}


@router.post("/node-status")
async def set_node_status(
    req: NodeStatusRequest,
    _=Depends(require_instructor)
):
    """Poner un nodo online u offline (instructor)."""
    if req.online:
        attack_manager.set_node_online(req.node_id)
    else:
        attack_manager.set_node_offline(req.node_id)

    await ws_manager.broadcast("node_status_change", {
        "node_id": req.node_id,
        "is_online": req.online,
        "timestamp": iso_utc(datetime.utcnow()),
    })
    return {"node_id": req.node_id, "is_online": req.online}


@router.post("/auto-attacks")
async def toggle_auto_attacks(
    enabled: bool,
    _=Depends(require_instructor)
):
    """Activar/desactivar ataques automáticos."""
    from ..simulation.scheduler import scheduler
    scheduler.set_auto_attacks(enabled)
    return {"auto_attacks_enabled": enabled}


# ── Modo Clase Guiada ─────────────────────────────────────────

class GuidedStep(BaseModel):
    attack_type: str
    node_id: str
    intensity: float = 0.7
    duration_sec: int = 120
    delay_before_sec: int = 60   # segundos a esperar antes de lanzar este ataque


class GuidedSessionRequest(BaseModel):
    name: str = "Clase guiada"
    steps: list[GuidedStep]
    auto_attacks_off: bool = True  # desactivar ataques auto durante la sesión
    briefing: str = ""  # mensaje de contexto inicial para el aprendiz


def _build_scenario_catalog():
    """Convierte ATTACK_CHAINS (mitigation.py) en escenarios narrativos listos
    para 'Clase Guiada': cada fase se traduce a un GuidedStep con
    delay_before_sec relativo a la fase anterior."""
    from ..simulation.mitigation import ATTACK_CHAINS

    # mitigation.py usa "tls_downgrade" pero ATTACK_CATALOG (attacks.py) define "ssl_tls_downgrade"
    ATTACK_TYPE_ALIASES = {"tls_downgrade": "ssl_tls_downgrade"}

    catalog = {}
    for key, chain in ATTACK_CHAINS.items():
        phases = chain["phases"]
        total = chain.get("total_duration_sec", 300)
        steps = []
        for i, p in enumerate(phases):
            prev_delay = phases[i - 1]["delay_sec"] if i > 0 else 0
            next_delay = phases[i + 1]["delay_sec"] if i + 1 < len(phases) else total
            steps.append({
                "attack_type": ATTACK_TYPE_ALIASES.get(p["attack_type"], p["attack_type"]),
                "node_id": p["node"],
                "intensity": p["intensity"],
                "duration_sec": max(60, next_delay - p["delay_sec"]),
                "delay_before_sec": max(5, p["delay_sec"] - prev_delay),
                "desc": p.get("desc", ""),
            })
        catalog[key] = {
            "name": chain["name"],
            "description": chain["description"],
            "briefing": chain["description"],
            "total_steps": len(steps),
            "steps": steps,
        }
    return catalog


SCENARIO_CATALOG = _build_scenario_catalog()


@router.get("/guided/catalog")
async def get_guided_catalog(_=Depends(require_instructor)):
    """Catálogo de escenarios narrativos predefinidos para Clase Guiada."""
    return SCENARIO_CATALOG


@router.post("/guided/start")
async def start_guided_session(
    req: GuidedSessionRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Inicia una sesión de clase guiada con secuencia de ataques predefinida."""
    from ..simulation.scheduler import scheduler
    if scheduler.guided_session_active():
        raise HTTPException(status_code=409, detail="Ya hay una sesión guiada activa")
    if not req.steps:
        raise HTTPException(status_code=400, detail="La sesión debe tener al menos un ataque")

    steps_dict = [s.model_dump() for s in req.steps]
    scheduler.start_guided_session(req.name, steps_dict, req.auto_attacks_off)

    await ws_manager.broadcast("guided_session_started", {
        "name": req.name,
        "briefing": req.briefing,
        "total_steps": len(req.steps),
        "timestamp": iso_utc(datetime.utcnow()),
        "message": f"🎓 Sesión guiada '{req.name}' iniciada — {len(req.steps)} ataques programados",
    })
    return {"started": True, "name": req.name, "total_steps": len(req.steps)}


@router.post("/guided/stop")
async def stop_guided_session(_=Depends(require_instructor)):
    """Detiene la sesión de clase guiada en curso."""
    from ..simulation.scheduler import scheduler
    scheduler.stop_guided_session()
    await ws_manager.broadcast("guided_session_stopped", {
        "timestamp": iso_utc(datetime.utcnow()),
        "message": "🛑 Sesión guiada detenida por el instructor",
    })
    return {"stopped": True}


@router.get("/guided/status")
async def guided_session_status(_=Depends(require_instructor)):
    """Estado actual de la sesión guiada."""
    from ..simulation.scheduler import scheduler
    return scheduler.get_guided_status()
