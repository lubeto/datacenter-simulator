"""
DC Monitoring Simulator - Exportación de datos para migración SQLite → PostgreSQL
TEMPORAL: remover después de completar la migración
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ..database.db import get_db
from ..api.routes_students import get_current_student
from ..database.models import (
    Student, Session, Incident, Bitacora,
    GuidedSession, SSTProtocolSession, PracticeSession,
    MitigationAction, Alert, Report, EvalGroup
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _dt(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _row(obj, fields):
    return {f: _dt(getattr(obj, f, None)) for f in fields}


@router.get("/export-data")
async def export_data(
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    if current.role != "instructor":
        return {"error": "Solo instructores pueden exportar datos"}

    # ── Students ──────────────────────────────────────────────
    students = (await db.execute(select(Student))).scalars().all()
    students_data = [_row(s, [
        "id", "name", "email", "password_hash", "role",
        "created_at", "is_active", "total_sessions",
        "total_incidents", "avg_mttd_seconds", "avg_mttr_seconds", "avg_score"
    ]) for s in students]

    # ── Sessions ──────────────────────────────────────────────
    sessions = (await db.execute(select(Session))).scalars().all()
    sessions_data = [_row(s, [
        "id", "student_id", "started_at", "ended_at", "duration_min",
        "is_active", "incidents_detected", "incidents_missed",
        "false_positives", "score", "notes"
    ]) for s in sessions]

    # ── Incidents ─────────────────────────────────────────────
    incidents = (await db.execute(select(Incident))).scalars().all()
    incidents_data = [_row(i, [
        "id", "session_id", "incident_type", "category", "severity",
        "node_affected", "description", "started_at", "detected_at",
        "resolved_at", "auto_resolved", "mttd_seconds", "mttr_seconds",
        "mitigation_score", "status", "root_cause", "resolution_notes"
    ]) for i in incidents]

    # ── Bitácoras ─────────────────────────────────────────────
    bitacoras = (await db.execute(select(Bitacora))).scalars().all()
    bitacoras_data = [_row(b, [
        "id", "student_id", "incident_id", "node_id", "attack_type",
        "severity", "score", "correct_answers", "total_questions",
        "hints_used", "mttd_seconds", "duration_sec",
        "sintomas_observados", "causa_raiz", "acciones_tomadas",
        "lecciones", "created_at"
    ]) for b in bitacoras]

    # ── GuidedSessions ────────────────────────────────────────
    guided = (await db.execute(select(GuidedSession))).scalars().all()
    guided_data = [_row(g, [
        "id", "student_id", "attack_type", "node_id", "score",
        "correct_answers", "total_questions", "hints_used",
        "duration_sec", "completed_at"
    ]) for g in guided]

    # ── SSTProtocolSessions ───────────────────────────────────
    sst = (await db.execute(select(SSTProtocolSession))).scalars().all()
    sst_data = [_row(s, [
        "id", "student_id", "protocol_type", "protocol_name",
        "sensor_name", "sensor_value", "score", "correct_answers",
        "total_questions", "bitacora", "duration_sec", "completed_at"
    ]) for s in sst]

    # ── PracticeSessions ──────────────────────────────────────
    practice = (await db.execute(select(PracticeSession))).scalars().all()
    practice_data = [_row(p, [
        "id", "student_id", "scenario_type", "scenario_name",
        "score", "duration_sec", "steps_completed",
        "total_steps", "completed_at"
    ]) for p in practice]

    # ── MitigationActions ─────────────────────────────────────
    actions = (await db.execute(select(MitigationAction))).scalars().all()
    actions_data = [_row(a, [
        "id", "incident_id", "student_id", "action_taken",
        "action_category", "was_correct", "timestamp",
        "effectiveness_pct", "notes"
    ]) for a in actions]

    # ── Reports ───────────────────────────────────────────────
    reports = (await db.execute(select(Report))).scalars().all()
    reports_data = [_row(r, [
        "id", "student_id", "session_id", "report_type", "title",
        "generated_at", "file_path", "file_format",
        "summary_json", "period_from", "period_to"
    ]) for r in reports]

    # ── EvalGroups ────────────────────────────────────────────
    groups = (await db.execute(select(EvalGroup))).scalars().all()
    groups_data = [_row(g, [
        "id", "name", "student_ids_json", "session_ids_json",
        "started_at", "ended_at", "is_active", "group_score", "notes"
    ]) for g in groups]

    export = {
        "exported_at": datetime.utcnow().isoformat(),
        "version": "1.0",
        "counts": {
            "students": len(students_data),
            "sessions": len(sessions_data),
            "incidents": len(incidents_data),
            "bitacoras": len(bitacoras_data),
            "guided_sessions": len(guided_data),
            "sst_sessions": len(sst_data),
            "practice_sessions": len(practice_data),
            "mitigation_actions": len(actions_data),
            "reports": len(reports_data),
            "eval_groups": len(groups_data),
        },
        "students": students_data,
        "sessions": sessions_data,
        "incidents": incidents_data,
        "bitacoras": bitacoras_data,
        "guided_sessions": guided_data,
        "sst_sessions": sst_data,
        "practice_sessions": practice_data,
        "mitigation_actions": actions_data,
        "reports": reports_data,
        "eval_groups": groups_data,
    }

    return export
