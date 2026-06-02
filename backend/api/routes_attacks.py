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
from ..simulation.attacks import attack_manager, ATTACK_CATALOG
from ..simulation.engine import state as sim_state
from ..api.routes_students import get_current_student, require_instructor
from ..api.websocket import manager as ws_manager

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
        "timestamp": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
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
            "started_at":   inc.started_at.isoformat() if inc.started_at else None,
            "detected_at":  inc.detected_at.isoformat() if inc.detected_at else None,
            "resolved_at":  inc.resolved_at.isoformat() if inc.resolved_at else None,
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
    incident = await crud.detect_incident(db, incident_id, session_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    await ws_manager.broadcast("incident_detected", {
        "incident_id": incident_id,
        "detected_by": current.name,
        "mttd_seconds": incident.mttd_seconds,
        "timestamp": datetime.utcnow().isoformat(),
    })
    return {
        "incident_id": incident_id,
        "mttd_seconds": incident.mttd_seconds,
        "message": f"Detectado en {incident.mttd_seconds:.1f}s"
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
        "timestamp": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
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
