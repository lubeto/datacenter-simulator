"""
DC Monitoring Simulator - Rutas de Analytics, Rankings y Export
"""
import csv, io
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database.db import get_db
from ..database import crud
from ..database.models import Student, Session, Incident, MitigationAction
from ..api.routes_students import get_current_student, require_instructor
from ..simulation.mitigation import mitigation_engine, MITIGATION_RULES, ATTACK_CHAINS, ESCALATION_CONFIG

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ── RANKING DE ESTUDIANTES ────────────────────────────────────────────────────
@router.get("/ranking")
async def get_student_ranking(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_student)
):
    """Ranking de estudiantes ordenado por score promedio."""
    students = await crud.get_all_students(db)
    ranking = []
    for s in students:
        if s.role == "instructor":
            continue
        ranking.append({
            "id":               s.id,
            "name":             s.name,
            "email":            s.email,
            "total_sessions":   s.total_sessions,
            "avg_mttd_seconds": round(s.avg_mttd_seconds, 1),
            "avg_mttr_seconds": round(s.avg_mttr_seconds, 1),
            "avg_score":        round(s.avg_score, 1),
            "rank_label":       _rank_label(s.avg_score),
        })
    ranking.sort(key=lambda x: x["avg_score"], reverse=True)
    for i, r in enumerate(ranking):
        r["rank"] = i + 1
    return ranking


def _rank_label(score: float) -> str:
    if score >= 90: return "Elite"
    if score >= 75: return "Avanzado"
    if score >= 55: return "Intermedio"
    if score >= 30: return "Principiante"
    return "En formacion"


# ── ESTADISTICAS DE UN ESTUDIANTE ─────────────────────────────────────────────
@router.get("/student/{student_id}")
async def get_student_stats(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Estadisticas detalladas de un estudiante."""
    if current.role != "instructor" and current.id != student_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Sin permiso")

    student = await crud.get_student_by_id(db, student_id)
    if not student:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Sesiones del estudiante — db is already an AsyncSession from FastAPI
    q = select(Session).where(Session.student_id == student_id).order_by(Session.started_at.desc()).limit(10)
    result = await db.execute(q)
    sessions = result.scalars().all()

    # Incidentes mas recientes del sistema (para contexto del estudiante)
    q2 = select(Incident).order_by(Incident.started_at.desc()).limit(20)
    result2 = await db.execute(q2)
    incidents = result2.scalars().all()

    return {
        "student": {
            "id": student.id, "name": student.name, "email": student.email,
            "total_sessions": student.total_sessions,
            "avg_mttd_seconds": round(student.avg_mttd_seconds, 1),
            "avg_mttr_seconds": round(student.avg_mttr_seconds, 1),
            "avg_score": round(student.avg_score, 1),
            "rank_label": _rank_label(student.avg_score),
        },
        "sessions": [
            {
                "id": s.id,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at":   s.ended_at.isoformat() if s.ended_at else None,
                "duration_min": s.duration_min,
                "score":        s.score,
                "is_active":    s.ended_at is None,
            }
            for s in sessions
        ],
        "recent_incidents": [
            {
                "id":            i.id,
                "incident_type": i.incident_type,
                "node_affected": i.node_affected,
                "severity":      i.severity,
                "status":        i.status,
                "mttd_seconds":  round(i.mttd_seconds, 1) if i.mttd_seconds else None,
                "mttr_seconds":  round(i.mttr_seconds, 1) if i.mttr_seconds else None,
                "started_at":    i.started_at.isoformat() if i.started_at else None,
            }
            for i in incidents
        ],
    }


# ── MITIGACION: PLAN Y CADENAS ─────────────────────────────────────────────────
@router.get("/mitigation/plan/{attack_type}")
async def get_mitigation_plan(
    attack_type: str,
    node_id: str = Query("WEB-01"),
    _=Depends(get_current_student)
):
    """Obtiene el plan de mitigacion completo para un tipo de ataque."""
    plan = mitigation_engine.get_mitigation_plan(attack_type, node_id)
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Sin plan para: {attack_type}")
    return plan


@router.get("/mitigation/rules")
async def get_all_mitigation_rules(_=Depends(get_current_student)):
    """Catalogo completo de reglas de mitigacion."""
    return {
        k: {
            "name":                 v["name"],
            "steps_count":          len(v["steps"]),
            "auto_actions":         v["auto_actions"],
            "expected_recovery_sec":v["expected_recovery_sec"],
            "severity_impact":      v["severity_impact"],
        }
        for k, v in MITIGATION_RULES.items()
    }


@router.get("/mitigation/suggestions")
async def get_active_suggestions(_=Depends(require_instructor)):
    """Sugerencias de mitigacion activas para incidentes en curso."""
    return mitigation_engine.get_all_suggestions()


@router.post("/mitigation/apply")
async def apply_mitigation(
    incident_id: int,
    action: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """El estudiante aplica una accion de mitigacion especifica."""
    suggestion = mitigation_engine.get_suggestion(incident_id)
    if not suggestion:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sin sugerencia activa para este incidente")

    step = next((s for s in suggestion["steps"] if s["action"] == action), None)
    if not step:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Accion '{action}' no encontrada")

    await crud.log_mitigation(
        db, incident_id, current.id,
        action=step["desc"],
        category=action,
        notes=f"Comando: {step['command']}"
    )
    return {
        "applied":   True,
        "action":    action,
        "desc":      step["desc"],
        "command":   step["command"],
        "incident_id": incident_id,
    }


# ── ATTACK CHAINS ─────────────────────────────────────────────────────────────
@router.get("/chains")
async def get_attack_chains(_=Depends(get_current_student)):
    """Catalogo de cadenas de ataque APT disponibles."""
    return mitigation_engine.get_available_chains()


@router.post("/chains/{chain_id}/launch")
async def launch_attack_chain(
    chain_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Lanza una cadena de ataque APT de forma asincrona."""
    import asyncio
    from ..simulation.attacks import attack_manager
    from ..api.websocket import manager as ws_manager

    chain = mitigation_engine.get_chain(chain_id)
    if not chain:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Cadena '{chain_id}' no encontrada")

    async def run_chain():
        for i, phase in enumerate(chain["phases"]):
            if i > 0:
                await asyncio.sleep(phase["delay_sec"] - chain["phases"][i-1]["delay_sec"])
            result = attack_manager.inject_attack(
                phase["attack_type"], phase["node"], 0.7, 180
            )
            incident = await crud.create_incident(db, {
                "incident_type": phase["attack_type"],
                "category":      result.get("category", "attack"),
                "severity":      result.get("severity", "warning"),
                "node_affected": phase["node"],
                "description":   phase["desc"],
                "started_at":    datetime.utcnow(),
                "status":        "active",
            })
            mitigation_engine.register_suggestion(incident.id, phase["attack_type"], phase["node"])
            await ws_manager.broadcast("apt_phase", {
                "chain_id":    chain_id,
                "chain_name":  chain["name"],
                "phase":       i + 1,
                "total_phases":len(chain["phases"]),
                "attack_type": phase["attack_type"],
                "node":        phase["node"],
                "description": phase["desc"],
                "incident_id": incident.id,
                "timestamp":   datetime.utcnow().isoformat(),
            })

    asyncio.create_task(run_chain())
    return {
        "chain_id":    chain_id,
        "name":        chain["name"],
        "phases":      len(chain["phases"]),
        "message":     f"Cadena APT '{chain['name']}' iniciada. {len(chain['phases'])} fases en progreso.",
    }


# ── ESCALATION CONFIG ──────────────────────────────────────────────────────────
@router.get("/escalation/config")
async def get_escalation_config(_=Depends(get_current_student)):
    return ESCALATION_CONFIG


# ── CSV EXPORT ────────────────────────────────────────────────────────────────
@router.get("/export/students-csv")
async def export_students_csv(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Exporta estadisticas de estudiantes en CSV."""
    students = await crud.get_all_students(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Nombre","Email","Rol","Sesiones","MTTD_avg_s","MTTR_avg_s","Score_avg","Nivel"])
    for s in students:
        writer.writerow([
            s.id, s.name, s.email, s.role,
            s.total_sessions,
            round(s.avg_mttd_seconds, 1),
            round(s.avg_mttr_seconds, 1),
            round(s.avg_score, 1),
            _rank_label(s.avg_score),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ranking_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"}
    )


@router.get("/export/incidents-csv")
async def export_incidents_csv(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Exporta historial de incidentes en CSV."""
    q = select(Incident).order_by(Incident.started_at.desc()).limit(500)
    result = await db.execute(q)
    incidents = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Tipo","Categoria","Severidad","Nodo","Estado","Inicio","MTTD_s","MTTR_s","Descripcion"])
    for i in incidents:
        writer.writerow([
            i.id, i.incident_type, i.category, i.severity,
            i.node_affected, i.status,
            i.started_at.isoformat() if i.started_at else "",
            round(i.mttd_seconds, 1) if i.mttd_seconds else "",
            round(i.mttr_seconds, 1) if i.mttr_seconds else "",
            i.description or "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=incidents_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"}
    )


@router.get("/export/metrics-csv/{node_id}")
async def export_metrics_csv(
    node_id: str,
    hours: int = Query(1, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_student)
):
    """Exporta metricas historicas de un nodo en CSV."""
    from sqlalchemy import select
    from ..database.models import Metric
    since = datetime.utcnow() - timedelta(hours=hours)
    q = select(Metric).where(Metric.node_id == node_id, Metric.timestamp >= since).order_by(Metric.timestamp)
    result = await db.execute(q)
    metrics = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp","CPU_%","RAM_%","Disk_Used_%","Disk_IO_Mbps","Net_IN_Mbps","Net_OUT_Mbps","Latency_ms","Packet_Loss_%","Connections","Online"])
    for m in metrics:
        writer.writerow([
            m.timestamp.isoformat() if m.timestamp else "",
            m.cpu_pct, m.ram_pct, m.disk_used_pct, m.disk_io_mbps,
            m.net_in_mbps, m.net_out_mbps, m.latency_ms,
            m.packet_loss_pct, m.connections, m.is_online
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={node_id}_metrics_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"}
    )


# ── Lab de Mitigación: Practice Sessions ─────────────────────
from pydantic import BaseModel as _BaseModel

class PracticeCompleteData(_BaseModel):
    scenario_type: str
    scenario_name: str
    score: float
    duration_sec: float
    steps_completed: int
    total_steps: int


@router.post("/practice/complete")
async def complete_practice(
    data: PracticeCompleteData,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Guardar resultado de práctica del Lab de Mitigación."""
    ps = await crud.save_practice_session(
        db, current.id,
        data.scenario_type, data.scenario_name,
        data.score, data.duration_sec,
        data.steps_completed, data.total_steps
    )
    return {"id": ps.id, "score": ps.score, "ok": True}


@router.get("/practice/history")
async def my_practice_history(
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Historial de prácticas del estudiante actual."""
    sessions = await crud.get_practice_sessions_by_student(db, current.id)
    return [
        {
            "id": s.id,
            "scenario_type": s.scenario_type,
            "scenario_name": s.scenario_name,
            "score": s.score,
            "duration_sec": s.duration_sec,
            "steps_completed": s.steps_completed,
            "total_steps": s.total_steps,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None
        }
        for s in sessions
    ]


@router.get("/practice/all")
async def all_practice_sessions(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Todas las prácticas de todos los estudiantes (solo instructor)."""
    sessions = await crud.get_all_practice_sessions(db)
    from ..database.models import Student as _Student
    from sqlalchemy import select as _sel
    res = await db.execute(_sel(_Student))
    students = {st.id: st.name for st in res.scalars().all()}
    return [
        {
            "id": s.id,
            "student_name": students.get(s.student_id, "—"),
            "scenario_type": s.scenario_type,
            "scenario_name": s.scenario_name,
            "score": s.score,
            "duration_sec": s.duration_sec,
            "steps_completed": s.steps_completed,
            "total_steps": s.total_steps,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None
        }
        for s in sessions
    ]
