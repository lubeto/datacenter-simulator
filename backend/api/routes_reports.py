"""
DC Monitoring Simulator - Rutas de Reportes
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.db import get_db
from ..database import crud
from ..database.models import Report
from ..api.routes_students import get_current_student, require_instructor
from ..utils_time import iso_utc

router = APIRouter(prefix="/api/reports", tags=["reports"])

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reports_output")
os.makedirs(REPORTS_DIR, exist_ok=True)


class ReportRequest(BaseModel):
    report_type: str   # incident | health | student_shift | ssl | sst | full
    student_id: Optional[int] = None
    session_id: Optional[int] = None
    title: Optional[str] = None


@router.post("/generate")
async def generate_report(
    req: ReportRequest,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Genera un reporte PDF."""
    from ..reports.pdf_generator import generate_pdf_report

    student_id = req.student_id or current.id
    title = req.title or f"Reporte {req.report_type.upper()} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    # Recopilar datos según el tipo
    report_data = await _collect_report_data(db, req.report_type, student_id, req.session_id)

    # Generar PDF
    filename = f"{req.report_type}_{student_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    success = generate_pdf_report(
        report_type=req.report_type,
        title=title,
        data=report_data,
        output_path=filepath
    )

    if not success:
        raise HTTPException(status_code=500, detail="Error generando el reporte PDF")

    # Guardar en DB
    report = await crud.save_report(db, {
        "student_id": student_id,
        "session_id": req.session_id,
        "report_type": req.report_type,
        "title": title,
        "file_path": filepath,
        "file_format": "pdf",
        "summary_json": json.dumps({"rows": len(report_data)}),
        "period_from": datetime.utcnow(),
        "period_to": datetime.utcnow(),
    })

    return {
        "report_id": report.id,
        "title": title,
        "filename": filename,
        "download_url": f"/api/reports/download/{report.id}",
    }


@router.get("/download/{report_id}")
async def download_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Descarga un reporte PDF generado."""
    reports = await crud.get_all_reports(db)
    report = next((r for r in reports if r.id == report_id), None)

    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    if current.role != "instructor" and report.student_id != current.id:
        raise HTTPException(status_code=403, detail="Sin permiso para este reporte")

    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Archivo de reporte no encontrado")

    return FileResponse(
        report.file_path,
        media_type="application/pdf",
        filename=os.path.basename(report.file_path)
    )


def _serialize_report(r) -> dict:
    """Convierte un objeto Report ORM a dict compatible con el frontend."""
    return {
        "id":           r.id,
        "title":        r.title or "—",
        "report_type":  r.report_type,
        "format":       r.file_format or "pdf",   # alias para el frontend
        "file_format":  r.file_format or "pdf",
        "generated_at": iso_utc(r.generated_at) if r.generated_at else None,
        "student_id":   r.student_id,
        "student_name": r.student.name if r.student else None,
        "download_url": f"/api/reports/download/{r.id}",
    }


@router.get("/my-reports")
async def my_reports(
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    """Reportes del estudiante actual."""
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(Report).options(selectinload(Report.student))
        .where(Report.student_id == current.id)
        .order_by(Report.generated_at.desc())
    )
    return [_serialize_report(r) for r in result.scalars().all()]


@router.get("/all")
async def all_reports(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Todos los reportes (solo instructor)."""
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(Report).options(selectinload(Report.student))
        .order_by(Report.generated_at.desc()).limit(100)
    )
    return [_serialize_report(r) for r in result.scalars().all()]


async def _collect_report_data(db: AsyncSession, report_type: str,
                                student_id: int, session_id: int) -> list:
    """Recopila datos según el tipo de reporte."""
    from ..simulation.engine import generate_full_snapshot
    from ..simulation.nodes import get_all_sensors
    from ..simulation.engine import generate_sst_reading

    if report_type == "incident":
        incidents = await crud.get_incidents_history(db, limit=50)
        return [
            {
                "id": i.id, "type": i.incident_type, "severity": i.severity,
                "node": i.node_affected, "started": str(i.started_at),
                "resolved": str(i.resolved_at) if i.resolved_at else "Activo",
                "mttd_sec": i.mttd_seconds, "mttr_sec": i.mttr_seconds,
                "status": i.status, "root_cause": i.root_cause or "",
            }
            for i in incidents
        ]

    elif report_type == "health":
        snapshot = generate_full_snapshot()
        return [
            {
                "node": nid, "type": ndata["type"],
                "cpu_pct": ndata["metrics"]["cpu_pct"],
                "ram_pct": ndata["metrics"]["ram_pct"],
                "latency_ms": ndata["metrics"]["latency_ms"],
                "packet_loss": ndata["metrics"]["packet_loss_pct"],
                "online": ndata["metrics"]["is_online"],
            }
            for nid, ndata in snapshot["nodes"].items()
        ]

    elif report_type == "ssl":
        certs = await crud.get_all_ssl_certs(db)
        return [
            {
                "node": c.node_id, "domain": c.domain,
                "days_to_expire": c.days_to_expire,
                "tls_version": c.tls_version,
                "is_valid": c.is_valid, "alert_level": c.alert_level,
                "alert_message": c.alert_message or "",
            }
            for c in certs
        ]

    elif report_type == "sst":
        sensors = get_all_sensors()
        return [
            {
                "sensor": s.id, "name": s.name, "zone": s.zone,
                "type": s.sensor_type, "unit": s.unit,
                **generate_sst_reading(s)
            }
            for s in sensors
        ]

    elif report_type == "student_shift":
        student = await crud.get_student_by_id(db, student_id)
        incidents = await crud.get_incidents_history(db, limit=20)
        return [{
            "student": student.name if student else "Unknown",
            "sessions": student.total_sessions if student else 0,
            "avg_mttd": student.avg_mttd_seconds if student else 0,
            "avg_mttr": student.avg_mttr_seconds if student else 0,
            "avg_score": student.avg_score if student else 0,
            "incidents_total": len(incidents),
        }]

    elif report_type == "full_summary":
        from ..simulation.engine import generate_full_snapshot
        from sqlalchemy import select as _sel
        from ..database.models import Bitacora, GuidedSession, SSTProtocolSession, PracticeSession

        snapshot  = generate_full_snapshot()
        incidents = await crud.get_incidents_history(db, limit=50)
        student   = await crud.get_student_by_id(db, student_id)
        certs     = await crud.get_all_ssl_certs(db)

        bq = await db.execute(
            _sel(Bitacora).where(Bitacora.student_id == student_id)
            .order_by(Bitacora.created_at.desc()).limit(30)
        )
        bitacoras = bq.scalars().all()

        gq = await db.execute(
            _sel(GuidedSession).where(GuidedSession.student_id == student_id)
            .order_by(GuidedSession.completed_at.desc()).limit(30)
        )
        guided = gq.scalars().all()

        sq = await db.execute(
            _sel(SSTProtocolSession).where(SSTProtocolSession.student_id == student_id)
            .order_by(SSTProtocolSession.completed_at.desc()).limit(20)
        )
        sst_sessions = sq.scalars().all()

        lq = await db.execute(
            _sel(PracticeSession).where(PracticeSession.student_id == student_id)
            .order_by(PracticeSession.completed_at.desc()).limit(20)
        )
        labs = lq.scalars().all()

        student_data = [{"section": "student_header",
            "name": student.name if student else "—",
            "email": student.email if student else "—",
            "sessions": student.total_sessions if student else 0,
            "avg_mttd": round(student.avg_mttd_seconds or 0, 1) if student else 0,
            "avg_mttr": round(student.avg_mttr_seconds or 0, 1) if student else 0,
            "avg_score": round(student.avg_score or 0, 1) if student else 0,
            "incidents": student.total_incidents if student else 0,
            "guided_count": len(guided),
            "sst_count": len(sst_sessions),
            "lab_count": len(labs),
            "bitacora_count": len(bitacoras),
        }]

        sessions_data = [{"section": "eval_session",
            "id": s.id, "started": str(s.completed_at)[:19],
            "score": round(s.score or 0, 1),
            "correct": s.correct_answers or 0,
            "total": s.total_questions or 4,
            "hints": s.hints_used or 0,
            "attack": s.attack_type or "—",
            "node": s.node_id or "—",
            "duration": int(s.duration_sec or 0),
        } for s in guided]

        sst_data = [{"section": "sst_session",
            "id": s.id, "date": str(s.completed_at)[:19],
            "protocol": s.protocol_name or "—",
            "sensor": s.sensor_name or "—",
            "value": s.sensor_value or "—",
            "score": round(s.score or 0, 1),
            "correct": s.correct_answers or 0,
            "total": s.total_questions or 4,
            "bitacora": s.bitacora or "",
            "duration": int(s.duration_sec or 0),
        } for s in sst_sessions]

        lab_data = [{"section": "lab_session",
            "id": s.id, "date": str(s.completed_at)[:19],
            "scenario": s.scenario_name or s.scenario_type or "—",
            "score": round(s.score or 0, 1),
            "duration": int(s.duration_sec or 0),
            "steps": s.steps_completed or 0,
            "total_steps": s.total_steps or 0,
        } for s in labs]

        bitacoras_data = [{"section": "bitacora",
            "id": b.id,
            "date": str(b.created_at)[:19],
            "attack": b.attack_type or "—",
            "node": b.node_id or "—",
            "score": round(b.score or 0, 1),
            "correct": b.correct_answers or 0,
            "hints": b.hints_used or 0,
            "sintomas": b.sintomas_observados or "",
            "causa": b.causa_raiz or "",
            "acciones": b.acciones_tomadas or "",
            "lecciones": b.lecciones or "",
            "duration": int(b.duration_sec or 0),
        } for b in bitacoras]

        incidents_data = [{"section": "incident",
            "id": i.id, "type": i.incident_type, "severity": i.severity,
            "node": i.node_affected, "started": str(i.started_at)[:19],
            "resolved": str(i.resolved_at)[:19] if i.resolved_at else "Activo",
            "mttd": round(i.mttd_seconds or 0, 1),
            "mttr": round(i.mttr_seconds or 0, 1),
            "status": i.status,
        } for i in incidents]

        nodes_data = [{"section": "health",
            "node": nid, "type": ndata["type"],
            "cpu_pct": ndata["metrics"]["cpu_pct"],
            "ram_pct": ndata["metrics"]["ram_pct"],
            "latency_ms": ndata["metrics"]["latency_ms"],
            "online": ndata["metrics"]["is_online"],
        } for nid, ndata in snapshot["nodes"].items()]

        ssl_data = [{"section": "ssl",
            "node": c.node_id, "domain": c.domain,
            "days_to_expire": c.days_to_expire,
            "tls_version": c.tls_version,
            "is_valid": c.is_valid,
            "is_expired": c.is_expired,
            "alert_level": c.alert_level or "ok",
            "alert_message": c.alert_message or "",
        } for c in certs]

        return (student_data + sessions_data + sst_data + lab_data +
                bitacoras_data + incidents_data + nodes_data + ssl_data)

    return []
