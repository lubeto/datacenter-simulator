"""
DC Monitoring Simulator — Rutas de administración
Endpoint protegido para reset de actividad estudiantil.
Solo accesible por instructores autenticados.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, delete, update

from ..database.db import get_db
from ..database import models
from .routes_students import require_instructor

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reset-activity")
async def reset_student_activity(
    _=Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
):
    """
    Borra toda la actividad estudiantil conservando las cuentas de los aprendices.

    Tablas que se vacían:
      bitacoras, eval_groups, sst_protocol_sessions, practice_sessions,
      guided_sessions, reports, mitigation_actions, alerts, incidents,
      sessions, metrics, sst_readings, ssl_certificates

    También resetea los contadores acumulados de cada estudiante a cero.
    """
    counts = {}

    # Orden: hijos antes que padres (FK seguro)
    tables_in_order = [
        ("bitacoras",              models.Bitacora),
        ("eval_groups",            models.EvalGroup),
        ("sst_protocol_sessions",  models.SSTProtocolSession),
        ("practice_sessions",      models.PracticeSession),
        ("guided_sessions",        models.GuidedSession),
        ("reports",                models.Report),
        ("mitigation_actions",     models.MitigationAction),
        ("alerts",                 models.Alert),
        ("incidents",              models.Incident),
        ("sessions",               models.Session),
        ("metrics",                models.Metric),
        ("sst_readings",           models.SSTReading),
        ("ssl_certificates",       models.SSLCertificate),
    ]

    for table_name, model_class in tables_in_order:
        # Contar antes de borrar
        result = await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        counts[table_name] = result.scalar()
        # Borrar
        await db.execute(delete(model_class))

    # Resetear métricas acumuladas de estudiantes (conservar cuenta)
    await db.execute(
        update(models.Student).values(
            total_sessions=0,
            total_incidents=0,
            avg_mttd_seconds=0.0,
            avg_mttr_seconds=0.0,
            avg_score=0.0,
        )
    )

    await db.commit()

    total_deleted = sum(counts.values())

    return {
        "status": "ok",
        "message": "Actividad estudiantil eliminada. Cuentas conservadas.",
        "deleted_counts": counts,
        "total_records_deleted": total_deleted,
    }
