"""
DC Monitoring Simulator - Operaciones CRUD
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update, func
from .models import (
    Student, Session, Metric, Incident, Alert,
    MitigationAction, Report, SSTReading, SSLCertificate
)


# ============================================================
# STUDENTS
# ============================================================
async def create_student(db: AsyncSession, name: str, email: str,
                         password_hash: str, role: str = "student") -> Student:
    student = Student(name=name, email=email,
                      password_hash=password_hash, role=role)
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def get_student_by_email(db: AsyncSession, email: str) -> Optional[Student]:
    result = await db.execute(select(Student).where(Student.email == email))
    return result.scalar_one_or_none()


async def get_student_by_id(db: AsyncSession, student_id: int) -> Optional[Student]:
    result = await db.execute(select(Student).where(Student.id == student_id))
    return result.scalar_one_or_none()


async def get_all_students(db: AsyncSession) -> List[Student]:
    result = await db.execute(select(Student).order_by(Student.name))
    return result.scalars().all()


async def update_student_stats(db: AsyncSession, student_id: int,
                               mttd: float, mttr: float, score: float):
    student = await get_student_by_id(db, student_id)
    if student:
        n = student.total_sessions or 1
        student.avg_mttd_seconds = ((student.avg_mttd_seconds * (n - 1)) + mttd) / n
        student.avg_mttr_seconds = ((student.avg_mttr_seconds * (n - 1)) + mttr) / n
        student.avg_score = ((student.avg_score * (n - 1)) + score) / n
        await db.commit()


# ============================================================
# SESSIONS
# ============================================================
async def create_session(db: AsyncSession, student_id: int) -> Session:
    session = Session(student_id=student_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    # Incrementar contador de sesiones del estudiante
    await db.execute(
        update(Student).where(Student.id == student_id)
        .values(total_sessions=Student.total_sessions + 1)
    )
    await db.commit()
    return session


async def close_session(db: AsyncSession, session_id: int) -> Optional[Session]:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session:
        now = datetime.utcnow()
        session.ended_at = now
        session.is_active = False
        delta = (now - session.started_at).total_seconds() / 60
        session.duration_min = round(delta, 2)
        await db.commit()
        await db.refresh(session)
    return session


async def get_active_sessions(db: AsyncSession) -> List[Session]:
    result = await db.execute(
        select(Session).where(Session.is_active == True)
        .order_by(desc(Session.started_at))
    )
    return result.scalars().all()


# ============================================================
# METRICS
# ============================================================
async def save_metric(db: AsyncSession, node_id: str, node_type: str,
                      data: dict) -> Metric:
    metric = Metric(node_id=node_id, node_type=node_type, **data)
    db.add(metric)
    await db.commit()
    return metric


async def get_metrics_by_node(db: AsyncSession, node_id: str,
                               limit: int = 100) -> List[Metric]:
    result = await db.execute(
        select(Metric).where(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp)).limit(limit)
    )
    return result.scalars().all()


async def get_latest_metrics(db: AsyncSession) -> List[Metric]:
    """Última métrica por nodo."""
    subq = (
        select(Metric.node_id, func.max(Metric.timestamp).label("max_ts"))
        .group_by(Metric.node_id)
        .subquery()
    )
    result = await db.execute(
        select(Metric).join(
            subq, (Metric.node_id == subq.c.node_id) &
                  (Metric.timestamp == subq.c.max_ts)
        )
    )
    return result.scalars().all()


# ============================================================
# SST READINGS
# ============================================================
async def save_sst_reading(db: AsyncSession, sensor_id: str,
                           sensor_type: str, zone: str, data: dict) -> SSTReading:
    reading = SSTReading(sensor_id=sensor_id, sensor_type=sensor_type,
                         zone=zone, **data)
    db.add(reading)
    await db.commit()
    return reading


async def get_latest_sst(db: AsyncSession) -> List[SSTReading]:
    subq = (
        select(SSTReading.sensor_id, func.max(SSTReading.timestamp).label("max_ts"))
        .group_by(SSTReading.sensor_id)
        .subquery()
    )
    result = await db.execute(
        select(SSTReading).join(
            subq, (SSTReading.sensor_id == subq.c.sensor_id) &
                  (SSTReading.timestamp == subq.c.max_ts)
        )
    )
    return result.scalars().all()


# ============================================================
# SSL CERTIFICATES
# ============================================================
async def upsert_ssl_cert(db: AsyncSession, node_id: str, data: dict) -> SSLCertificate:
    result = await db.execute(
        select(SSLCertificate).where(SSLCertificate.node_id == node_id)
    )
    cert = result.scalar_one_or_none()
    if cert:
        for k, v in data.items():
            setattr(cert, k, v)
        cert.last_checked = datetime.utcnow()
    else:
        cert = SSLCertificate(node_id=node_id, **data)
        db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


async def get_all_ssl_certs(db: AsyncSession) -> List[SSLCertificate]:
    result = await db.execute(select(SSLCertificate).order_by(SSLCertificate.days_to_expire))
    return result.scalars().all()


# ============================================================
# INCIDENTS
# ============================================================
async def create_incident(db: AsyncSession, data: dict) -> Incident:
    incident = Incident(**data)
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


async def get_active_incidents(db: AsyncSession) -> List[Incident]:
    result = await db.execute(
        select(Incident).where(
            Incident.status.in_(["active", "detected", "mitigating"])
        ).order_by(desc(Incident.started_at))
    )
    return result.scalars().all()


async def resolve_incident(db: AsyncSession, incident_id: int,
                           notes: str = "", root_cause: str = "") -> Optional[Incident]:
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident and incident.resolved_at is None:
        now = datetime.utcnow()
        incident.resolved_at = now
        incident.status = "resolved"
        incident.resolution_notes = notes
        incident.root_cause = root_cause
        if incident.detected_at:
            incident.mttr_seconds = (now - incident.detected_at).total_seconds()
        await db.commit()
        await db.refresh(incident)
    return incident


async def detect_incident(db: AsyncSession, incident_id: int,
                          session_id: int) -> Optional[Incident]:
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident and incident.detected_at is None:
        now = datetime.utcnow()
        incident.detected_at = now
        incident.status = "detected"
        incident.session_id = session_id
        incident.mttd_seconds = (now - incident.started_at).total_seconds()
        await db.commit()
        await db.refresh(incident)
    return incident


async def get_incidents_history(db: AsyncSession, limit: int = 50) -> List[Incident]:
    result = await db.execute(
        select(Incident).order_by(desc(Incident.started_at)).limit(limit)
    )
    return result.scalars().all()


# ============================================================
# ALERTS
# ============================================================
async def create_alert(db: AsyncSession, node_id: str, alert_type: str,
                       severity: str, message: str,
                       incident_id: int = None,
                       metric_name: str = None,
                       metric_value: float = None,
                       threshold: float = None) -> Alert:
    alert = Alert(
        node_id=node_id, alert_type=alert_type,
        severity=severity, message=message,
        incident_id=incident_id,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold=threshold
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def get_active_alerts(db: AsyncSession) -> List[Alert]:
    result = await db.execute(
        select(Alert).where(Alert.is_active == True)
        .order_by(desc(Alert.timestamp))
    )
    return result.scalars().all()


async def acknowledge_alert(db: AsyncSession, alert_id: int,
                            student_id: int) -> Optional[Alert]:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert:
        alert.acknowledged = True
        alert.acknowledged_by = student_id
        alert.acknowledged_at = datetime.utcnow()
        alert.is_active = False  # sacar de la lista activa tras ACK
        await db.commit()
        await db.refresh(alert)
    return alert


# ============================================================
# MITIGATION ACTIONS
# ============================================================
async def log_mitigation(db: AsyncSession, incident_id: int, student_id: int,
                         action: str, category: str = "",
                         correct: bool = True,
                         effectiveness: float = 100.0,
                         notes: str = "") -> MitigationAction:
    ma = MitigationAction(
        incident_id=incident_id, student_id=student_id,
        action_taken=action, action_category=category,
        was_correct=correct, effectiveness_pct=effectiveness,
        notes=notes
    )
    db.add(ma)
    await db.commit()
    await db.refresh(ma)
    return ma


# ============================================================
# REPORTS
# ============================================================
async def save_report(db: AsyncSession, data: dict) -> Report:
    report = Report(**data)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def get_reports_by_student(db: AsyncSession,
                                  student_id: int) -> List[Report]:
    result = await db.execute(
        select(Report).where(Report.student_id == student_id)
        .order_by(desc(Report.generated_at))
    )
    return result.scalars().all()


async def get_all_reports(db: AsyncSession, limit: int = 100) -> List[Report]:
    result = await db.execute(
        select(Report).order_by(desc(Report.generated_at)).limit(limit)
    )
    return result.scalars().all()


# ── Practice Sessions (Lab de Mitigación) ────────────────────
async def save_practice_session(
    db: AsyncSession,
    student_id: int,
    scenario_type: str,
    scenario_name: str,
    score: float,
    duration_sec: float,
    steps_completed: int,
    total_steps: int,
):
    from .models import PracticeSession
    ps = PracticeSession(
        student_id=student_id,
        scenario_type=scenario_type,
        scenario_name=scenario_name,
        score=round(score, 1),
        duration_sec=round(duration_sec, 1),
        steps_completed=steps_completed,
        total_steps=total_steps,
    )
    db.add(ps)
    await db.commit()
    await db.refresh(ps)
    return ps


async def get_practice_sessions_by_student(db: AsyncSession, student_id: int):
    from .models import PracticeSession
    result = await db.execute(
        select(PracticeSession)
        .where(PracticeSession.student_id == student_id)
        .order_by(desc(PracticeSession.completed_at))
    )
    return result.scalars().all()


async def get_all_practice_sessions(db: AsyncSession):
    from .models import PracticeSession
    result = await db.execute(
        select(PracticeSession).order_by(desc(PracticeSession.completed_at))
    )
    return result.scalars().all()


# ============================================================
# MANTENIMIENTO — Rotación de métricas para evitar disco lleno
# ============================================================
async def cleanup_old_metrics(db: AsyncSession, keep_hours: int = 24) -> int:
    """Elimina métricas y lecturas SST más antiguas que keep_hours horas.
    Llama esto periódicamente para evitar que el disco se llene."""
    from datetime import timedelta
    from sqlalchemy import delete
    cutoff = datetime.utcnow() - timedelta(hours=keep_hours)
    r1 = await db.execute(delete(Metric).where(Metric.timestamp < cutoff))
    r2 = await db.execute(delete(SSTReading).where(SSTReading.timestamp < cutoff))
    await db.commit()
    return (r1.rowcount or 0) + (r2.rowcount or 0)
