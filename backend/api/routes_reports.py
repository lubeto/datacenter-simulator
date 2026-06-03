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
        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
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
        # Reporte completo: salud + incidentes + SSL + resumen del aprendiz
        from ..simulation.engine import generate_full_snapshot
        snapshot = generate_full_snapshot()
        incidents = await crud.get_incidents_history(db, limit=20)
        student   = await crud.get_student_by_id(db, student_id)
        certs     = await crud.get_all_ssl_certs(db)

        nodes_data = [
            {"section": "health", "node": nid, "type": ndata["type"],
             "cpu_pct": ndata["metrics"]["cpu_pct"], "ram_pct": ndata["metrics"]["ram_pct"],
             "latency_ms": ndata["metrics"]["latency_ms"], "online": ndata["metrics"]["is_online"]}
            for nid, ndata in snapshot["nodes"].items()
        ]
        incidents_data = [
            {"section": "incident", "id": i.id, "type": i.incident_type,
             "severity": i.severity, "node": i.node_affected,
             "started": str(i.started_at), "status": i.status}
            for i in incidents
        ]
        ssl_data = [
            {"section": "ssl", "node": c.node_id, "days_to_expire": c.days_to_expire,
             "tls_version": c.tls_version, "alert_level": c.alert_level}
            for c in certs
        ]
        student_data = [{
            "section": "student", "student": student.name if student else "—",
            "sessions": student.total_sessions if student else 0,
            "avg_score": student.avg_score if student else 0,
        }]
        return student_data + nodes_data + incidents_data + ssl_data

    return []
