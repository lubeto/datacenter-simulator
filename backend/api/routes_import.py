"""
DC Monitoring Simulator - Importación de datos desde backup JSON
TEMPORAL: remover después de completar la migración
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..database.db import get_db
from ..api.routes_students import get_current_student
from ..database.models import (
    Student, Session, Incident, Bitacora,
    GuidedSession, SSTProtocolSession, PracticeSession,
    MitigationAction, Report, EvalGroup
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except Exception:
        return None


@router.post("/import-data")
async def import_data(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    if current.role != "instructor":
        return {"error": "Solo instructores pueden importar datos"}

    imported = {}

    # ── Students (skip id=1 instructor ya existente) ──────────
    existing_ids = set()
    count = 0
    for s in payload.get("students", []):
        if s["id"] == 1:
            existing_ids.add(1)
            continue
        obj = Student(
            id=s["id"], name=s["name"], email=s["email"],
            password_hash=s["password_hash"], role=s.get("role", "student"),
            created_at=_parse_dt(s.get("created_at")),
            is_active=s.get("is_active", True),
            total_sessions=s.get("total_sessions", 0),
            total_incidents=s.get("total_incidents", 0),
            avg_mttd_seconds=s.get("avg_mttd_seconds", 0.0),
            avg_mttr_seconds=s.get("avg_mttr_seconds", 0.0),
            avg_score=s.get("avg_score", 0.0),
        )
        db.add(obj)
        existing_ids.add(s["id"])
        count += 1
    await db.flush()
    imported["students"] = count

    # Resetear secuencia de IDs en PostgreSQL
    if count > 0:
        max_id = max(s["id"] for s in payload.get("students", []))
        await db.execute(text(f"SELECT setval('students_id_seq', {max_id})"))

    # ── Sessions ──────────────────────────────────────────────
    count = 0
    for s in payload.get("sessions", []):
        obj = Session(
            id=s["id"], student_id=s["student_id"],
            started_at=_parse_dt(s.get("started_at")),
            ended_at=_parse_dt(s.get("ended_at")),
            duration_min=s.get("duration_min", 0.0),
            is_active=s.get("is_active", False),
            incidents_detected=s.get("incidents_detected", 0),
            incidents_missed=s.get("incidents_missed", 0),
            false_positives=s.get("false_positives", 0),
            score=s.get("score", 0.0), notes=s.get("notes"),
        )
        db.add(obj)
        count += 1
    await db.flush()
    imported["sessions"] = count
    if count > 0:
        max_id = max(s["id"] for s in payload.get("sessions", []))
        await db.execute(text(f"SELECT setval('sessions_id_seq', {max_id})"))

    # ── Incidents ─────────────────────────────────────────────
    count = 0
    for i in payload.get("incidents", []):
        obj = Incident(
            id=i["id"], session_id=i.get("session_id"),
            incident_type=i["incident_type"], category=i["category"],
            severity=i.get("severity"), node_affected=i["node_affected"],
            description=i.get("description"),
            started_at=_parse_dt(i.get("started_at")) or datetime.utcnow(),
            detected_at=_parse_dt(i.get("detected_at")),
            resolved_at=_parse_dt(i.get("resolved_at")),
            auto_resolved=i.get("auto_resolved", False),
            mttd_seconds=i.get("mttd_seconds"),
            mttr_seconds=i.get("mttr_seconds"),
            mitigation_score=i.get("mitigation_score"),
            status=i.get("status", "resolved"),
            root_cause=i.get("root_cause"),
            resolution_notes=i.get("resolution_notes"),
        )
        db.add(obj)
        count += 1
    await db.flush()
    imported["incidents"] = count
    if count > 0:
        max_id = max(i["id"] for i in payload.get("incidents", []))
        await db.execute(text(f"SELECT setval('incidents_id_seq', {max_id})"))

    # ── Bitácoras ─────────────────────────────────────────────
    count = 0
    for b in payload.get("bitacoras", []):
        obj = Bitacora(
            id=b["id"], student_id=b["student_id"],
            incident_id=b.get("incident_id"), node_id=b["node_id"],
            attack_type=b["attack_type"], severity=b.get("severity"),
            score=b.get("score", 0.0),
            correct_answers=b.get("correct_answers", 0),
            total_questions=b.get("total_questions", 4),
            hints_used=b.get("hints_used", 0),
            mttd_seconds=b.get("mttd_seconds"),
            duration_sec=b.get("duration_sec", 0.0),
            sintomas_observados=b.get("sintomas_observados", ""),
            causa_raiz=b.get("causa_raiz", ""),
            acciones_tomadas=b.get("acciones_tomadas", ""),
            lecciones=b.get("lecciones", ""),
            created_at=_parse_dt(b.get("created_at")),
        )
        db.add(obj)
        count += 1
    await db.flush()
    imported["bitacoras"] = count
    if count > 0:
        max_id = max(b["id"] for b in payload.get("bitacoras", []))
        await db.execute(text(f"SELECT setval('bitacoras_id_seq', {max_id})"))

    # ── GuidedSessions ────────────────────────────────────────
    count = 0
    for g in payload.get("guided_sessions", []):
        obj = GuidedSession(
            id=g["id"], student_id=g["student_id"],
            attack_type=g["attack_type"], node_id=g["node_id"],
            score=g.get("score", 0.0),
            correct_answers=g.get("correct_answers", 0),
            total_questions=g.get("total_questions", 4),
            hints_used=g.get("hints_used", 0),
            duration_sec=g.get("duration_sec", 0.0),
            completed_at=_parse_dt(g.get("completed_at")),
        )
        db.add(obj)
        count += 1
    await db.flush()
    imported["guided_sessions"] = count
    if count > 0:
        max_id = max(g["id"] for g in payload.get("guided_sessions", []))
        await db.execute(text(f"SELECT setval('guided_sessions_id_seq', {max_id})"))

    # ── PracticeSessions ──────────────────────────────────────
    count = 0
    for p in payload.get("practice_sessions", []):
        obj = PracticeSession(
            id=p["id"], student_id=p["student_id"],
            scenario_type=p["scenario_type"], scenario_name=p["scenario_name"],
            score=p.get("score", 0.0), duration_sec=p.get("duration_sec", 0.0),
            steps_completed=p.get("steps_completed", 0),
            total_steps=p.get("total_steps", 0),
            completed_at=_parse_dt(p.get("completed_at")),
        )
        db.add(obj)
        count += 1
    await db.flush()
    imported["practice_sessions"] = count
    if count > 0:
        max_id = max(p["id"] for p in payload.get("practice_sessions", []))
        await db.execute(text(f"SELECT setval('practice_sessions_id_seq', {max_id})"))

    # ── EvalGroups ────────────────────────────────────────────
    count = 0
    for g in payload.get("eval_groups", []):
        obj = EvalGroup(
            id=g["id"], name=g.get("name"),
            student_ids_json=g.get("student_ids_json", "[]"),
            session_ids_json=g.get("session_ids_json"),
            started_at=_parse_dt(g.get("started_at")),
            ended_at=_parse_dt(g.get("ended_at")),
            is_active=g.get("is_active", False),
            group_score=g.get("group_score"),
            notes=g.get("notes"),
        )
        db.add(obj)
        count += 1
    await db.flush()
    imported["eval_groups"] = count
    if count > 0:
        max_id = max(g["id"] for g in payload.get("eval_groups", []))
        await db.execute(text(f"SELECT setval('eval_groups_id_seq', {max_id})"))

    return {"status": "ok", "imported": imported}
