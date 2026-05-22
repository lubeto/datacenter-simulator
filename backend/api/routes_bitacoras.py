"""
DC Monitoring Simulator — Rutas de Bitácoras
POST /api/bitacoras          → guardar nueva bitácora
GET  /api/bitacoras          → listar (instructor ve todas, estudiante ve las suyas)
GET  /api/bitacoras/{id}     → detalle de una bitácora
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..database.db import get_db
from ..database.models import Bitacora, Student
from .routes_students import get_current_student

router = APIRouter(prefix="/api/bitacoras", tags=["bitacoras"])


# ── Esquemas ──────────────────────────────────────────────────

class BitacoraCreate(BaseModel):
    node_id:             str
    attack_type:         str
    severity:            Optional[str] = None
    score:               float = 0.0
    correct_answers:     int   = 0
    total_questions:     int   = 4
    hints_used:          int   = 0
    mttd_seconds:        Optional[float] = None
    duration_sec:        float = 0.0
    incident_id:         Optional[int] = None

    sintomas_observados: str = Field(..., min_length=20)
    causa_raiz:          str = Field(..., min_length=20)
    acciones_tomadas:    str = Field(..., min_length=20)
    lecciones:           str = Field(..., min_length=20)


class BitacoraOut(BaseModel):
    id:                  int
    student_id:          int
    student_name:        Optional[str] = None
    node_id:             str
    attack_type:         str
    severity:            Optional[str]
    score:               float
    correct_answers:     int
    total_questions:     int
    hints_used:          int
    mttd_seconds:        Optional[float]
    duration_sec:        float
    sintomas_observados: str
    causa_raiz:          str
    acciones_tomadas:    str
    lecciones:           str
    created_at:          datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────

@router.post("", response_model=BitacoraOut, status_code=status.HTTP_201_CREATED)
async def create_bitacora(
    data: BitacoraCreate,
    db:   AsyncSession = Depends(get_db),
    me:   Student      = Depends(get_current_student),
):
    """El aprendiz guarda su bitácora al completar el diagnóstico guiado."""
    b = Bitacora(
        student_id          = me.id,
        incident_id         = data.incident_id,
        node_id             = data.node_id,
        attack_type         = data.attack_type,
        severity            = data.severity,
        score               = data.score,
        correct_answers     = data.correct_answers,
        total_questions     = data.total_questions,
        hints_used          = data.hints_used,
        mttd_seconds        = data.mttd_seconds,
        duration_sec        = data.duration_sec,
        sintomas_observados = data.sintomas_observados,
        causa_raiz          = data.causa_raiz,
        acciones_tomadas    = data.acciones_tomadas,
        lecciones           = data.lecciones,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)

    # Cargar nombre del estudiante para la respuesta
    result = await db.execute(select(Student).where(Student.id == me.id))
    student = result.scalar_one_or_none()
    out = BitacoraOut.model_validate(b)
    out.student_name = student.name if student else None
    return out


@router.get("", response_model=List[BitacoraOut])
async def list_bitacoras(
    student_id: Optional[int] = None,
    db:         AsyncSession  = Depends(get_db),
    me:         Student       = Depends(get_current_student),
):
    """
    Instructor: ve todas las bitácoras (filtrable por student_id).
    Aprendiz: solo ve las suyas.
    """
    if me.role == "student":
        q = select(Bitacora).where(Bitacora.student_id == me.id).order_by(desc(Bitacora.created_at))
    else:
        q = select(Bitacora).order_by(desc(Bitacora.created_at))
        if student_id:
            q = select(Bitacora).where(Bitacora.student_id == student_id).order_by(desc(Bitacora.created_at))

    result = await db.execute(q)
    bitacoras = result.scalars().all()

    # Enriquecer con nombre del estudiante
    out_list = []
    for b in bitacoras:
        sr = await db.execute(select(Student).where(Student.id == b.student_id))
        stu = sr.scalar_one_or_none()
        item = BitacoraOut.model_validate(b)
        item.student_name = stu.name if stu else "Desconocido"
        out_list.append(item)

    return out_list


@router.get("/{bitacora_id}", response_model=BitacoraOut)
async def get_bitacora(
    bitacora_id: int,
    db:          AsyncSession = Depends(get_db),
    me:          Student      = Depends(get_current_student),
):
    result = await db.execute(select(Bitacora).where(Bitacora.id == bitacora_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Bitácora no encontrada")
    # Aprendiz solo puede ver las suyas
    if me.role == "student" and b.student_id != me.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    sr = await db.execute(select(Student).where(Student.id == b.student_id))
    stu = sr.scalar_one_or_none()
    out = BitacoraOut.model_validate(b)
    out.student_name = stu.name if stu else "Desconocido"
    return out
