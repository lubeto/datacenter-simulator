"""
DC Monitoring Simulator — Sesiones Evaluativas Formales
Individual:
  POST /api/sessions/start          → instructor inicia sesión individual
  POST /api/sessions/end/{id}       → instructor cierra sesión individual
  GET  /api/sessions/active         → sesiones individuales activas
Grupal:
  POST /api/sessions/group/start    → instructor inicia sesión grupal
  POST /api/sessions/group/end/{id} → instructor cierra sesión grupal
  GET  /api/sessions/group/active   → grupos activos
Estudiante:
  GET  /api/sessions/my             → mis sesiones
"""
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from ..database.db import get_db
from ..database.models import (
    Session as EvalSession, Student, EvalGroup,
    GuidedSession, PracticeSession, SSTProtocolSession, Bitacora
)
from .routes_students import get_current_student, require_instructor

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionStart(BaseModel):
    student_id: int
    notes: Optional[str] = None


# ── Iniciar sesión evaluativa ──────────────────────────────────
@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_session(
    data: SessionStart,
    db:   AsyncSession = Depends(get_db),
    _:    Student      = Depends(require_instructor),
):
    # Cerrar TODAS las sesiones activas previas del mismo estudiante
    q = select(EvalSession).where(
        EvalSession.student_id == data.student_id,
        EvalSession.is_active  == True
    )
    res  = await db.execute(q)
    for prev in res.scalars().all():
        prev.is_active    = False
        prev.ended_at     = datetime.utcnow()
        prev.duration_min = (datetime.utcnow() - prev.started_at).total_seconds() / 60

    session = EvalSession(
        student_id = data.student_id,
        started_at = datetime.utcnow(),
        is_active  = True,
        notes      = data.notes or "",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Notificar al estudiante via WebSocket
    from ..api.websocket import manager as ws_manager
    await ws_manager.broadcast_to_student(data.student_id, "eval_session", {
        "active":     True,
        "mode":       "individual",
        "session_id": session.id,
        "started_at": session.started_at.isoformat(),
        "message":    "El instructor ha iniciado tu sesión evaluativa",
    })

    return {"id": session.id, "student_id": data.student_id, "started_at": session.started_at.isoformat()}


# ── Terminar sesión evaluativa ─────────────────────────────────
@router.post("/end/{session_id}")
async def end_session(
    session_id: int,
    db:         AsyncSession = Depends(get_db),
    _:          Student      = Depends(require_instructor),
):
    q   = select(EvalSession).where(EvalSession.id == session_id)
    res = await db.execute(q)
    s   = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    now           = datetime.utcnow()
    s.ended_at    = now
    s.is_active   = False
    s.duration_min = (now - s.started_at).seconds / 60

    # Calcular score desde actividades durante la sesión
    start = s.started_at

    guided_q = await db.execute(
        select(func.avg(GuidedSession.score), func.count(GuidedSession.id))
        .where(GuidedSession.student_id == s.student_id,
               GuidedSession.completed_at >= start)
    )
    guided_row = guided_q.first()
    guided_avg = guided_row[0] or 0
    guided_cnt = guided_row[1] or 0

    lab_q = await db.execute(
        select(func.avg(PracticeSession.score), func.count(PracticeSession.id))
        .where(PracticeSession.student_id == s.student_id,
               PracticeSession.completed_at >= start)
    )
    lab_row = lab_q.first()
    lab_avg = lab_row[0] or 0
    lab_cnt = lab_row[1] or 0

    sst_q = await db.execute(
        select(func.avg(SSTProtocolSession.score), func.count(SSTProtocolSession.id))
        .where(SSTProtocolSession.student_id == s.student_id,
               SSTProtocolSession.completed_at >= start)
    )
    sst_row = sst_q.first()
    sst_avg = sst_row[0] or 0
    sst_cnt = sst_row[1] or 0

    bit_q = await db.execute(
        select(func.avg(Bitacora.score), func.count(Bitacora.id))
        .where(Bitacora.student_id == s.student_id,
               Bitacora.created_at >= start)
    )
    bit_row = bit_q.first()
    bit_avg = bit_row[0] or 0
    bit_cnt = bit_row[1] or 0

    # Score ponderado: diagnóstico 40%, bitácoras 30%, labs 20%, SST 10%
    scores  = []
    weights = []
    if guided_cnt > 0: scores.append(guided_avg); weights.append(0.40)
    if bit_cnt    > 0: scores.append(bit_avg);    weights.append(0.30)
    if lab_cnt    > 0: scores.append(lab_avg);    weights.append(0.20)
    if sst_cnt    > 0: scores.append(sst_avg);    weights.append(0.10)

    if scores:
        total_w   = sum(weights)
        final_sc  = sum(sc * w for sc, w in zip(scores, weights)) / total_w
    else:
        final_sc  = 0.0

    s.score              = round(final_sc, 1)
    s.incidents_detected = guided_cnt + bit_cnt

    # Actualizar métricas acumuladas del Student
    stu_q  = await db.execute(select(Student).where(Student.id == s.student_id))
    student = stu_q.scalar_one_or_none()
    if student:
        # Recalcular promedio acumulado incluyendo esta sesión
        prev_sessions = student.total_sessions or 0
        prev_avg      = student.avg_score or 0.0
        new_sessions  = prev_sessions + 1
        new_avg       = ((prev_avg * prev_sessions) + final_sc) / new_sessions

        student.total_sessions = new_sessions
        student.avg_score      = round(new_avg, 1)

        # MTTD desde bitácoras (si tienen mttd_seconds)
        mttd_q = await db.execute(
            select(func.avg(Bitacora.mttd_seconds))
            .where(Bitacora.student_id == s.student_id,
                   Bitacora.mttd_seconds.isnot(None))
        )
        mttd_val = mttd_q.scalar()
        if mttd_val:
            student.avg_mttd_seconds = round(mttd_val, 1)

    await db.commit()

    # Notificar al estudiante
    from ..api.websocket import manager as ws_manager
    await ws_manager.broadcast_to_student(s.student_id, "eval_session", {
        "active":  False,
        "mode":    "individual",
        "score":   round(final_sc, 1),
        "message": "Sesión evaluativa finalizada",
    })

    return {
        "session_id":    session_id,
        "duration_min":  round(s.duration_min, 1),
        "score":         round(final_sc, 1),
        "guided_count":  guided_cnt,
        "lab_count":     lab_cnt,
        "sst_count":     sst_cnt,
        "bitacora_count":bit_cnt,
    }


# ── Sesiones activas ───────────────────────────────────────────
@router.get("/active")
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    _:  Student      = Depends(require_instructor),
):
    q   = select(EvalSession).where(EvalSession.is_active == True)
    res = await db.execute(q)
    sessions = res.scalars().all()

    # Deduplicar: solo la sesión más reciente por estudiante,
    # y solo si el estudiante tiene rol "student" (no instructores)
    seen_students: dict = {}  # student_id -> session más reciente
    for s in sessions:
        if s.student_id not in seen_students:
            seen_students[s.student_id] = s
        elif s.started_at > seen_students[s.student_id].started_at:
            seen_students[s.student_id] = s

    out = []
    for s in seen_students.values():
        stu_q   = await db.execute(select(Student).where(Student.id == s.student_id))
        student = stu_q.scalar_one_or_none()
        # Solo mostrar aprendices, ignorar instructores o entradas huérfanas
        if not student or student.role != "student":
            continue
        elapsed = (datetime.utcnow() - s.started_at).total_seconds() // 60
        out.append({
            "id":           s.id,
            "student_id":   s.student_id,
            "student_name": student.name,
            "started_at":   s.started_at.isoformat(),
            "elapsed_min":  int(elapsed),
        })
    # Ordenar por nombre de aprendiz
    out.sort(key=lambda x: x["student_name"])
    return out


# ── Limpiar sesiones obsoletas ─────────────────────────────────
@router.post("/cleanup")
async def cleanup_sessions(
    db: AsyncSession = Depends(get_db),
    _:  Student      = Depends(require_instructor),
):
    """Cierra todas las sesiones activas con más de 30 minutos sin cerrar."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    q   = select(EvalSession).where(EvalSession.is_active == True)
    res = await db.execute(q)
    sessions = res.scalars().all()
    closed = 0
    for s in sessions:
        if s.started_at < cutoff:
            s.is_active   = False
            s.ended_at    = datetime.utcnow()
            s.duration_min = (datetime.utcnow() - s.started_at).total_seconds() / 60
            closed += 1
    await db.commit()
    return {"closed": closed, "message": f"Se cerraron {closed} sesiones obsoletas (>4 h)"}


# ── Mis sesiones (estudiante) ──────────────────────────────────
@router.get("/my")
async def my_sessions(
    db:  AsyncSession = Depends(get_db),
    me:  Student      = Depends(get_current_student),
):
    q   = select(EvalSession).where(EvalSession.student_id == me.id)\
            .order_by(EvalSession.started_at.desc()).limit(20)
    res = await db.execute(q)
    sessions = res.scalars().all()
    return [
        {
            "id":           s.id,
            "started_at":   s.started_at.isoformat() if s.started_at else None,
            "ended_at":     s.ended_at.isoformat()   if s.ended_at   else None,
            "duration_min": round(s.duration_min, 1) if s.duration_min else None,
            "score":        s.score,
            "is_active":    s.is_active,
        }
        for s in sessions
    ]


# ══════════════════════════════════════════════════════════════
# SESIONES GRUPALES
# ══════════════════════════════════════════════════════════════

class GroupSessionStart(BaseModel):
    student_ids: List[int]
    name: Optional[str] = None


async def _calc_student_score(db: AsyncSession, student_id: int, start: datetime) -> dict:
    """Calcula puntaje ponderado de un estudiante desde una fecha de inicio."""
    g_q = await db.execute(
        select(func.avg(GuidedSession.score), func.count(GuidedSession.id))
        .where(GuidedSession.student_id == student_id, GuidedSession.completed_at >= start)
    )
    g_r = g_q.first(); g_avg = g_r[0] or 0; g_cnt = g_r[1] or 0

    b_q = await db.execute(
        select(func.avg(Bitacora.score), func.count(Bitacora.id))
        .where(Bitacora.student_id == student_id, Bitacora.created_at >= start)
    )
    b_r = b_q.first(); b_avg = b_r[0] or 0; b_cnt = b_r[1] or 0

    l_q = await db.execute(
        select(func.avg(PracticeSession.score), func.count(PracticeSession.id))
        .where(PracticeSession.student_id == student_id, PracticeSession.completed_at >= start)
    )
    l_r = l_q.first(); l_avg = l_r[0] or 0; l_cnt = l_r[1] or 0

    sst_q = await db.execute(
        select(func.avg(SSTProtocolSession.score), func.count(SSTProtocolSession.id))
        .where(SSTProtocolSession.student_id == student_id, SSTProtocolSession.completed_at >= start)
    )
    sst_r = sst_q.first(); sst_avg = sst_r[0] or 0; sst_cnt = sst_r[1] or 0

    parts, weights = [], []
    if g_cnt   > 0: parts.append(g_avg);   weights.append(0.40)
    if b_cnt   > 0: parts.append(b_avg);   weights.append(0.30)
    if l_cnt   > 0: parts.append(l_avg);   weights.append(0.20)
    if sst_cnt > 0: parts.append(sst_avg); weights.append(0.10)
    total_w = sum(weights) or 1
    score   = round(sum(p*w for p,w in zip(parts,weights)) / total_w, 1) if parts else 0.0

    return {
        "score": score, "guided": g_cnt, "bitacoras": b_cnt,
        "labs": l_cnt, "sst": sst_cnt,
    }


@router.post("/group/start", status_code=status.HTTP_201_CREATED)
async def start_group_session(
    data: GroupSessionStart,
    db:   AsyncSession = Depends(get_db),
    _:    Student      = Depends(require_instructor),
):
    """Inicia una sesión evaluativa grupal para varios aprendices."""
    if len(data.student_ids) < 2:
        raise HTTPException(status_code=400, detail="Se requieren al menos 2 aprendices para una sesión grupal.")

    now = datetime.utcnow()
    group = EvalGroup(
        name             = data.name or f"Grupo {now.strftime('%d/%m %H:%M')}",
        student_ids_json = json.dumps(data.student_ids),
        started_at       = now,
        is_active        = True,
    )
    db.add(group)
    await db.flush()  # get group.id

    session_ids = []
    from ..api.websocket import manager as ws_manager
    for sid in data.student_ids:
        # Cerrar TODAS las sesiones activas del aprendiz
        prev_q = await db.execute(
            select(EvalSession).where(EvalSession.student_id == sid, EvalSession.is_active == True)
        )
        for prev in prev_q.scalars().all():
            prev.is_active = False
            prev.ended_at  = now

        s = EvalSession(student_id=sid, started_at=now, is_active=True,
                        notes=f"grupo:{group.id}")
        db.add(s)
        await db.flush()
        session_ids.append(s.id)

        # Notificar a cada estudiante
        stu_q = await db.execute(select(Student).where(Student.id == sid))
        stu   = stu_q.scalar_one_or_none()
        await ws_manager.broadcast_to_student(sid, "eval_session", {
            "active":     True,
            "mode":       "group",
            "group_id":   group.id,
            "group_name": group.name,
            "session_id": s.id,
            "message":    f"El instructor inició una sesión grupal: {group.name}",
        })

    group.session_ids_json = json.dumps(session_ids)
    await db.commit()

    return {
        "group_id":    group.id,
        "name":        group.name,
        "student_ids": data.student_ids,
        "session_ids": session_ids,
        "started_at":  now.isoformat(),
    }


@router.post("/group/end/{group_id}")
async def end_group_session(
    group_id: int,
    db:       AsyncSession = Depends(get_db),
    _:        Student      = Depends(require_instructor),
):
    """Cierra la sesión grupal, calcula puntaje individual + grupal promediado."""
    g_q = await db.execute(select(EvalGroup).where(EvalGroup.id == group_id))
    group = g_q.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    now = datetime.utcnow()
    group.ended_at  = now
    group.is_active = False

    student_ids  = json.loads(group.student_ids_json or "[]")
    session_ids  = json.loads(group.session_ids_json or "[]")
    start        = group.started_at
    individual_scores = []
    results      = []

    from ..api.websocket import manager as ws_manager

    for i, sid in enumerate(student_ids):
        stats = await _calc_student_score(db, sid, start)
        individual_scores.append(stats["score"])

        # Cerrar sesión individual
        if i < len(session_ids):
            s_q = await db.execute(select(EvalSession).where(EvalSession.id == session_ids[i]))
            s   = s_q.scalar_one_or_none()
            if s:
                s.ended_at    = now
                s.is_active   = False
                s.duration_min = (now - start).seconds / 60
                s.score       = stats["score"]

        # Actualizar Student
        stu_q = await db.execute(select(Student).where(Student.id == sid))
        stu   = stu_q.scalar_one_or_none()
        if stu:
            prev_n = stu.total_sessions or 0
            prev_a = stu.avg_score or 0.0
            stu.total_sessions = prev_n + 1
            stu.avg_score      = round(((prev_a * prev_n) + stats["score"]) / (prev_n + 1), 1)

        results.append({
            "student_id":       sid,
            "name":             stu.name if stu else f"#{sid}",
            "individual_score": stats["score"],
            **stats,
        })

    # Score grupal = promedio de todos los individuales
    group_sc    = round(sum(individual_scores) / len(individual_scores), 1) if individual_scores else 0.0
    group.group_score = group_sc

    await db.commit()

    # Notificar a cada estudiante con el resultado individual + grupal
    for r, sid in zip(results, student_ids):
        await ws_manager.broadcast_to_student(sid, "eval_session", {
            "active":         False,
            "mode":           "group",
            "group_name":     group.name,
            "individual_score": r["individual_score"],
            "group_score":    group_sc,
            "message":        f"Sesión grupal finalizada · Tu puntaje: {r['individual_score']}/100 · Puntaje grupal: {group_sc}/100",
        })

    return {
        "group_id":    group_id,
        "group_name":  group.name,
        "group_score": group_sc,
        "duration_min": round((now - start).seconds / 60, 1),
        "results":     results,
    }


@router.get("/group/active")
async def get_active_groups(
    db: AsyncSession = Depends(get_db),
    _:  Student      = Depends(require_instructor),
):
    q    = select(EvalGroup).where(EvalGroup.is_active == True)
    res  = await db.execute(q)
    groups = res.scalars().all()
    out  = []
    for g in groups:
        sids    = json.loads(g.student_ids_json or "[]")
        elapsed = (datetime.utcnow() - g.started_at).seconds // 60
        names   = []
        for sid in sids:
            sq = await db.execute(select(Student).where(Student.id == sid))
            st = sq.scalar_one_or_none()
            names.append(st.name if st else f"#{sid}")
        out.append({
            "id":          g.id,
            "name":        g.name,
            "student_ids": sids,
            "student_names": names,
            "elapsed_min": elapsed,
            "started_at":  g.started_at.isoformat(),
        })
    return out
