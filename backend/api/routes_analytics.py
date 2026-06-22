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
from sqlalchemy.orm import aliased
from ..database.models import (Student, Session, Incident, MitigationAction,
                               GuidedSession, PracticeSession, SSTProtocolSession, Bitacora)
from ..api.routes_students import get_current_student, require_instructor
from ..simulation.mitigation import mitigation_engine, MITIGATION_RULES, ATTACK_CHAINS, ESCALATION_CONFIG
from ..utils_time import iso_utc

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ── RANKING DE ESTUDIANTES ────────────────────────────────────────────────────
@router.get("/ranking")
async def get_student_ranking(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_student)
):
    """Ranking de estudiantes con scores reales calculados desde actividades."""
    students = await crud.get_all_students(db)
    ranking = []
    for s in students:
        if s.role == "instructor":
            continue

        # Score real: promedio ponderado de todas las actividades
        g_q = await db.execute(
            select(func.avg(GuidedSession.score), func.count(GuidedSession.id))
            .where(GuidedSession.student_id == s.id)
        )
        g_row = g_q.first(); g_avg = g_row[0] or 0; g_cnt = g_row[1] or 0

        b_q = await db.execute(
            select(func.avg(Bitacora.score), func.count(Bitacora.id))
            .where(Bitacora.student_id == s.id)
        )
        b_row = b_q.first(); b_avg = b_row[0] or 0; b_cnt = b_row[1] or 0

        l_q = await db.execute(
            select(func.avg(PracticeSession.score), func.count(PracticeSession.id))
            .where(PracticeSession.student_id == s.id)
        )
        l_row = l_q.first(); l_avg = l_row[0] or 0; l_cnt = l_row[1] or 0

        sst_q = await db.execute(
            select(func.avg(SSTProtocolSession.score), func.count(SSTProtocolSession.id))
            .where(SSTProtocolSession.student_id == s.id)
        )
        sst_row = sst_q.first(); sst_avg = sst_row[0] or 0; sst_cnt = sst_row[1] or 0

        # Ponderación: diagnóstico 40%, bitácoras 30%, labs 20%, SST 10%
        parts, weights = [], []
        if g_cnt   > 0: parts.append(g_avg);   weights.append(0.40)
        if b_cnt   > 0: parts.append(b_avg);   weights.append(0.30)
        if l_cnt   > 0: parts.append(l_avg);   weights.append(0.20)
        if sst_cnt > 0: parts.append(sst_avg); weights.append(0.10)
        total_w  = sum(weights) or 1
        avg_sc   = sum(p*w for p,w in zip(parts,weights)) / total_w if parts else 0

        # ── MTTD: promedio desde Incident.mttd_seconds (join Session→student) ──
        # También fallback a Bitacora.mttd_seconds si no hay incidentes detectados
        # MTTD desde bitácoras del aprendiz (campo más confiable, sin necesidad de join)
        bit_mttd_q = await db.execute(
            select(func.avg(Bitacora.mttd_seconds))
            .where(Bitacora.student_id == s.id, Bitacora.mttd_seconds.isnot(None))
        )
        mttd_val = bit_mttd_q.scalar() or s.avg_mttd_seconds or 0

        # MTTR: desde incidentes ligados a sesiones del aprendiz
        # Usamos subquery para evitar el problema del JOIN con session_id nullable
        student_sessions_q = await db.execute(
            select(Session.id).where(Session.student_id == s.id)
        )
        student_session_ids = [r[0] for r in student_sessions_q.all()]
        mttr_val = 0.0
        if student_session_ids:
            inc_mttr_q = await db.execute(
                select(func.avg(Incident.mttr_seconds))
                .where(
                    Incident.session_id.in_(student_session_ids),
                    Incident.mttr_seconds.isnot(None)
                )
            )
            mttr_val = inc_mttr_q.scalar() or s.avg_mttr_seconds or 0

        # Actualizar Student con los valores calculados (para que otros endpoints los lean)
        if mttd_val and mttd_val != s.avg_mttd_seconds:
            s.avg_mttd_seconds = round(float(mttd_val), 1)
        if mttr_val and mttr_val != s.avg_mttr_seconds:
            s.avg_mttr_seconds = round(float(mttr_val), 1)

        total_acts = g_cnt + b_cnt + l_cnt + sst_cnt

        ranking.append({
            "id":               s.id,
            "name":             s.name,
            "email":            s.email,
            "total_sessions":   total_acts,
            "avg_mttd_seconds": round(float(mttd_val or 0), 1),
            "avg_mttr_seconds": round(float(mttr_val or 0), 1),
            "avg_score":        round(avg_sc, 1),
            "rank_label":       _rank_label(avg_sc),
            "breakdown": {
                "guided":   {"count": g_cnt,   "avg": round(g_avg, 1)},
                "bitacoras":{"count": b_cnt,   "avg": round(b_avg, 1)},
                "labs":     {"count": l_cnt,   "avg": round(l_avg, 1)},
                "sst":      {"count": sst_cnt, "avg": round(sst_avg, 1)},
            }
        })

    # Persistir MTTD/MTTR actualizados en el Student model
    try:
        await db.commit()
    except Exception:
        await db.rollback()

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
                "started_at": iso_utc(s.started_at) if s.started_at else None,
                "ended_at":   iso_utc(s.ended_at) if s.ended_at else None,
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
                "started_at":    iso_utc(i.started_at) if i.started_at else None,
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
                "timestamp":   iso_utc(datetime.utcnow()),
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
            iso_utc(i.started_at) if i.started_at else "",
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
            iso_utc(m.timestamp) if m.timestamp else "",
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
            "completed_at": iso_utc(s.completed_at) if s.completed_at else None
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
            "completed_at": iso_utc(s.completed_at) if s.completed_at else None
        }
        for s in sessions
    ]


# ── GUIDED SESSION SAVE ───────────────────────────────────────────
@router.post("/guided/complete")
async def save_guided_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Guardar resultado de diagnóstico guiado del estudiante."""
    from ..database.models import GuidedSession
    gs = GuidedSession(
        student_id      = current.id,
        attack_type     = payload.get("attack_type", "unknown"),
        node_id         = payload.get("node_id", "—"),
        score           = payload.get("score", 0),
        correct_answers = payload.get("correct", 0),
        total_questions = payload.get("total", 4),
        hints_used      = payload.get("hints", 0),
        duration_sec    = payload.get("duration", 0),
    )
    db.add(gs)
    await db.commit()
    return {"ok": True}


# ── SST PROTOCOL SESSION SAVE ─────────────────────────────────────
@router.post("/sst/complete")
async def save_sst_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Guardar resultado de protocolo SST del estudiante."""
    from ..database.models import SSTProtocolSession
    ss = SSTProtocolSession(
        student_id      = current.id,
        protocol_type   = payload.get("protocol", "unknown"),
        protocol_name   = payload.get("name", "—"),
        sensor_name     = payload.get("sensor", "—"),
        sensor_value    = payload.get("value", ""),
        score           = payload.get("score", 0),
        correct_answers = payload.get("correct", 0),
        total_questions = payload.get("total", 4),
        bitacora        = payload.get("bitacora", ""),
        duration_sec    = payload.get("duration", 0),
    )
    db.add(ss)
    await db.commit()
    return {"ok": True}


# ── INSTRUCTOR CLASS REPORT ───────────────────────────────────────
@router.get("/instructor/class-report")
async def get_class_report(
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Reporte completo de la clase para el instructor."""
    from fastapi import HTTPException
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores")

    from ..database.models import GuidedSession, SSTProtocolSession, PracticeSession

    # Todos los estudiantes activos
    students_q = await db.execute(
        select(Student).where(Student.role == "student", Student.is_active == True)
    )
    students = students_q.scalars().all()

    result = []
    for s in students:
        # Labs
        labs_q = await db.execute(
            select(func.count(), func.avg(PracticeSession.score))
            .where(PracticeSession.student_id == s.id)
        )
        lab_row = labs_q.first()
        lab_count = lab_row[0] or 0
        lab_avg   = lab_row[1]

        # Guided
        guided_q = await db.execute(
            select(func.count(), func.avg(GuidedSession.score))
            .where(GuidedSession.student_id == s.id)
        )
        guided_row = guided_q.first()
        guided_count = guided_row[0] or 0
        guided_avg   = guided_row[1]

        # SST
        sst_q = await db.execute(
            select(func.count(), func.avg(SSTProtocolSession.score))
            .where(SSTProtocolSession.student_id == s.id)
        )
        sst_row = sst_q.first()
        sst_count = sst_row[0] or 0
        sst_avg   = sst_row[1]

        # Detalles recientes
        guided_detail_q = await db.execute(
            select(GuidedSession)
            .where(GuidedSession.student_id == s.id)
            .order_by(GuidedSession.completed_at.desc())
            .limit(10)
        )
        sst_detail_q = await db.execute(
            select(SSTProtocolSession)
            .where(SSTProtocolSession.student_id == s.id)
            .order_by(SSTProtocolSession.completed_at.desc())
            .limit(10)
        )
        lab_detail_q = await db.execute(
            select(PracticeSession)
            .where(PracticeSession.student_id == s.id)
            .order_by(PracticeSession.completed_at.desc())
            .limit(10)
        )

        scores = [x for x in [lab_avg, guided_avg, sst_avg] if x is not None]
        overall_avg = round(sum(scores) / len(scores), 1) if scores else 0

        result.append({
            "id":             s.id,
            "name":           s.name,
            "email":          s.email,
            "total_exercises":(lab_count) + (guided_count) + (sst_count),
            "labs":           {"count": lab_count,    "avg_score": round(lab_avg    or 0, 1)},
            "guided":         {"count": guided_count, "avg_score": round(guided_avg or 0, 1)},
            "sst":            {"count": sst_count,    "avg_score": round(sst_avg    or 0, 1)},
            "overall_avg":    overall_avg,
            "guided_sessions": [
                {
                    "type": g.attack_type, "node": g.node_id, "score": g.score,
                    "correct": g.correct_answers, "hints": g.hints_used,
                    "duration": g.duration_sec,
                    "ts": g.completed_at.strftime("%d/%m %H:%M") if g.completed_at else "—"
                }
                for g in guided_detail_q.scalars().all()
            ],
            "sst_sessions": [
                {
                    "protocol": g.protocol_name, "sensor": g.sensor_name, "score": g.score,
                    "bitacora": g.bitacora, "duration": g.duration_sec,
                    "ts": g.completed_at.strftime("%d/%m %H:%M") if g.completed_at else "—"
                }
                for g in sst_detail_q.scalars().all()
            ],
            "lab_sessions": [
                {
                    "scenario": g.scenario_name, "score": g.score,
                    "duration": g.duration_sec, "steps": g.steps_completed,
                    "ts": g.completed_at.strftime("%d/%m %H:%M") if g.completed_at else "—"
                }
                for g in lab_detail_q.scalars().all()
            ],
        })

    result.sort(key=lambda x: x["overall_avg"], reverse=True)
    return {"students": result, "total": len(result)}


# ── PRACTICE MODE CONTROL ─────────────────────────────────────────
@router.post("/practice/start")
async def start_practice_mode(
    payload: dict,
    current=Depends(get_current_student)
):
    """El instructor inicia el modo práctica para toda la clase."""
    from fastapi import HTTPException
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores")
    duration_min = int(payload.get("duration_min", 20))
    from ..api.websocket import manager as ws_manager
    await ws_manager.broadcast("practice_mode", {
        "active": True,
        "duration_min": duration_min,
        "started_at": iso_utc(datetime.utcnow())
    })
    return {"ok": True, "duration_min": duration_min}


@router.post("/practice/stop")
async def stop_practice_mode(current=Depends(get_current_student)):
    """El instructor detiene el modo práctica."""
    from fastapi import HTTPException
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores")
    from ..api.websocket import manager as ws_manager
    from ..simulation.scheduler import scheduler
    # Reactivar ataques automáticos al terminar la práctica
    scheduler.set_auto_attacks(True)
    await ws_manager.broadcast("practice_mode", {"active": False})
    return {"ok": True}


@router.get("/bitacora-quality")
async def get_bitacora_quality(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor),
):
    """Agrega calidad textual de bitacoras por aprendiz."""
    import re
    from sqlalchemy import select as _sel
    from ..database.models import Bitacora, Student

    KEYBOARD_ROWS = [
        "qwertyuiop", "asdfghjkl", "zxcvbnm",
        "poiuytrewq", "lkjhgfdsa", "mnbvcxz",
    ]

    def _text_quality(text: str) -> float:
        if not text or len(text.strip()) < 10:
            return 0.1
        t = text.lower().strip()
        longest_run = max((len(m.group(0)) for m in re.finditer(r'(.)\1+', t)), default=1)
        repeat_penalty = max(0.0, 1.0 - (longest_run - 2) * 0.15)
        letters = re.sub(r'[^a-z]', '', t)
        if not letters:
            return 0.05
        unique_ratio = len(set(letters)) / len(letters)
        diversity_score = min(unique_ratio * 5, 1.0)
        words = re.findall(r'[a-z]{3,}', t)
        vocab_score = min(len(set(words)) / 4, 1.0)
        keyboard_penalty = 1.0
        for row in KEYBOARD_ROWS:
            for length in range(4, 8):
                for i in range(len(row) - length + 1):
                    pattern = row[i:i+length]
                    if pattern in t:
                        keyboard_penalty = max(0.3, keyboard_penalty - 0.2)
                        break
        quality = (repeat_penalty * 0.30 + diversity_score * 0.35 + vocab_score * 0.25 + keyboard_penalty * 0.10)
        return round(max(0.05, min(1.0, quality)), 3)

    def _quality_label(avg: float) -> str:
        if avg >= 0.75:
            return "alta"
        elif avg >= 0.45:
            return "media"
        elif avg >= 0.20:
            return "baja"
        return "muy_baja"

    # Cargar todas las bitacoras con sus estudiantes
    bq = await db.execute(
        _sel(Bitacora).order_by(Bitacora.created_at.desc())
    )
    bitacoras = bq.scalars().all()

    # Cargar mapa estudiante id -> nombre
    sq = await db.execute(_sel(Student))
    student_map = {s.id: s.name for s in sq.scalars().all()}

    # Acumular por estudiante
    by_student: dict = {}
    totals = {"alta": 0, "media": 0, "baja": 0, "muy_baja": 0}

    for b in bitacoras:
        fields = [b.sintomas_observados, b.causa_raiz, b.acciones_tomadas, b.lecciones]
        avg = sum(_text_quality(f or "") for f in fields) / 4
        label = _quality_label(avg)
        totals[label] += 1

        sid = b.student_id
        if sid not in by_student:
            by_student[sid] = {
                "student_id": sid,
                "name": student_map.get(sid, f"ID {sid}"),
                "total": 0,
                "alta": 0, "media": 0, "baja": 0, "muy_baja": 0,
                "quality_sum": 0.0,
            }
        by_student[sid]["total"] += 1
        by_student[sid][label] += 1
        by_student[sid]["quality_sum"] += avg

    # Calcular promedios y ordenar por % alta desc
    rows = []
    for s in by_student.values():
        avg_q = s["quality_sum"] / s["total"] if s["total"] else 0
        pct_alta = round(s["alta"] / s["total"] * 100, 1) if s["total"] else 0
        rows.append({
            "student_id": s["student_id"],
            "name": s["name"],
            "total": s["total"],
            "alta": s["alta"],
            "media": s["media"],
            "baja": s["baja"],
            "muy_baja": s["muy_baja"],
            "avg_quality": round(avg_q, 3),
            "pct_alta": pct_alta,
        })
    rows.sort(key=lambda r: r["pct_alta"], reverse=True)

    total_all = sum(totals.values())
    pct_alta_global = round(totals["alta"] / total_all * 100, 1) if total_all else 0

    return {
        "total": total_all,
        "pct_alta": pct_alta_global,
        "by_level": totals,
        "by_student": rows,
    }
