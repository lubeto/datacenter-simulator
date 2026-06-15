"""
DC Monitoring Simulator - Modo Clase en Vivo
Permite al instructor pausar/reanudar la simulación, revelar soluciones
y enviar notificaciones push a todos los aprendices conectados.
"""
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.db import get_db
from ..database.models import Incident, Session as EvalSession, Student
from ..simulation.engine import state as sim_state
from ..simulation.attacks import ATTACK_CATALOG
from ..api.routes_students import require_instructor
from ..api.websocket import manager as ws_manager

router = APIRouter(prefix="/api/instructor", tags=["instructor"])


class BroadcastRequest(BaseModel):
    cmd: Literal["pause_sim", "resume_sim", "reveal_solution", "notification"]
    message: Optional[str] = None
    node_id: Optional[str] = None


@router.post("/broadcast")
async def broadcast_command(req: BroadcastRequest, _=Depends(require_instructor)):
    """Envía un comando en vivo a todos los aprendices conectados."""
    if req.cmd == "pause_sim":
        sim_state.is_paused = True
        await ws_manager.broadcast("sim_paused", {"timestamp": datetime.utcnow().isoformat()})
        return {"message": "Simulación pausada", "paused": True}

    if req.cmd == "resume_sim":
        sim_state.is_paused = False
        await ws_manager.broadcast("sim_resumed", {"timestamp": datetime.utcnow().isoformat()})
        return {"message": "Simulación reanudada", "paused": False}

    if req.cmd == "reveal_solution":
        if not req.node_id:
            raise HTTPException(status_code=400, detail="Se requiere 'node_id'")
        attack = sim_state.active_attacks.get(req.node_id)
        if not attack:
            raise HTTPException(status_code=404, detail="No hay un ataque activo en ese nodo")

        catalog = ATTACK_CATALOG.get(attack.get("type"), {})
        solution = {
            "node_id": req.node_id,
            "attack_type": attack.get("type"),
            "name": attack.get("name") or catalog.get("name"),
            "description": catalog.get("description", ""),
            "mitigation_steps": catalog.get("mitigation_steps", []),
        }
        await ws_manager.broadcast("reveal_solution", solution)
        return {"message": "Solución revelada", "solution": solution}

    # notification
    if not req.message:
        raise HTTPException(status_code=400, detail="Se requiere 'message'")
    await ws_manager.broadcast("instructor_notification", {
        "message": req.message,
        "timestamp": datetime.utcnow().isoformat(),
    })
    return {"message": "Notificación enviada"}


@router.get("/live-status")
async def live_status(db: AsyncSession = Depends(get_db), _=Depends(require_instructor)):
    """Estado en vivo de la clase: conectados, simulación pausada/activa y quién ha detectado cada incidente."""
    students = [
        {"id": s.get("id"), "email": s.get("email"), "role": s.get("role")}
        for s in ws_manager.get_connected_students()
        if s and s.get("role") != "instructor"
    ]

    active_attacks = []
    for node_id, a in sim_state.active_attacks.items():
        try:
            started_at = datetime.fromisoformat(a.get("started_at"))
        except (TypeError, ValueError):
            started_at = datetime.utcnow()

        d_q = await db.execute(
            select(EvalSession.student_id).join(
                Incident, Incident.session_id == EvalSession.id
            ).where(
                Incident.node_affected == node_id,
                Incident.incident_type == a.get("type"),
                Incident.detected_at.isnot(None),
                Incident.detected_at >= started_at,
            )
        )
        detected_ids = set(d_q.scalars().all())

        detected_names = []
        if detected_ids:
            s_q = await db.execute(select(Student.name).where(Student.id.in_(detected_ids)))
            detected_names = [n for n in s_q.scalars().all()]

        active_attacks.append({
            "node_id": node_id,
            "type": a.get("type"),
            "name": a.get("name"),
            "started_at": a.get("started_at"),
            "detected_count": len(detected_ids),
            "detected_names": detected_names,
        })

    return {
        "connected_count": len(students),
        "connected_students": students,
        "paused": sim_state.is_paused,
        "active_attacks": active_attacks,
    }
