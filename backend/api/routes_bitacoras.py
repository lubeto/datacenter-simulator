"""
DC Monitoring Simulator - Rutas de Bitacoras
POST /api/bitacoras          -> guardar nueva bitacora
GET  /api/bitacoras          -> listar (instructor ve todas, estudiante ve las suyas)
GET  /api/bitacoras/{id}     -> detalle de una bitacora
"""
import re
import math
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date, timedelta

from ..database.db import get_db
from ..database.models import Bitacora, Student
from .routes_students import get_current_student
from ..api.websocket import manager as ws_manager

router = APIRouter(prefix="/api/bitacoras", tags=["bitacoras"])


# -- Esquemas --------------------------------------------------

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
    collab_room_id:      Optional[int] = None

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


# -- Analisis de calidad textual -------------------------------
KEYBOARD_ROWS = [
    "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "poiuytrewq", "lkjhgfdsa", "mnbvcxz",
]


def _text_quality(text: str) -> float:
    """
    Devuelve un factor de calidad 0.0-1.0 para el texto de la bitacora.
    Detecta: caracteres repetidos, baja diversidad lexica, patrones de teclado.
    1.0 = texto de alta calidad. 0.0 = texto basura total.
    """
    if not text or len(text.strip()) < 10:
        return 0.1

    t = text.lower().strip()
    total = len(t)

    # 1. Penalizar caracteres repetidos consecutivos (ej: "fffffffff")
    longest_run = max((len(m.group(0)) for m in re.finditer(r'(.)\1+', t)), default=1)
    repeat_penalty = max(0.0, 1.0 - (longest_run - 2) * 0.15)  # 3 repeticiones = -0.15

    # 2. Diversidad de caracteres (letras unicas / total letras)
    letters = re.sub(r'[^a-z]', '', t)
    if not letters:
        return 0.05
    unique_ratio = len(set(letters)) / len(letters)
    diversity_score = min(unique_ratio * 5, 1.0)   # 0.2 ratio unico = score 1.0

    # 3. Palabras unicas (vocabulario)
    words = re.findall(r'[a-z]{3,}', t)
    unique_words = len(set(words))
    vocab_score = min(unique_words / 4, 1.0)   # 4 palabras unicas = score 1.0

    # 4. Penalizar patrones de teclado (ej: "asdfasdf", "qwerty")
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


def _bitacora_quality_score(data) -> tuple:
    """
    Calcula el factor de calidad promedio de los 4 campos de la bitacora.
    Devuelve (factor 0-1, descripcion).
    """
    fields = [
        data.sintomas_observados,
        data.causa_raiz,
        data.acciones_tomadas,
        data.lecciones,
    ]
    scores = [_text_quality(f) for f in fields]
    avg = sum(scores) / len(scores)

    if avg >= 0.75:
        label = "alta"
    elif avg >= 0.45:
        label = "media"
    elif avg >= 0.20:
        label = "baja"
    else:
        label = "muy baja (texto basura detectado)"

    return round(avg, 3), label


# -- Endpoints ------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bitacora(
    data: BitacoraCreate,
    db:   AsyncSession = Depends(get_db),
    me:   Student      = Depends(get_current_student),
):
    """El aprendiz guarda su bitacora al completar el diagnostico guiado."""
    # Analisis de calidad del texto
    quality_factor, quality_label = _bitacora_quality_score(data)

    # Penalizar score segun calidad del texto:
    #   Calidad alta (>=0.75)  -> sin penalizacion
    #   Calidad media (0.45-0.75) -> multiplicar por 0.80 (-20%)
    #   Calidad baja (0.20-0.45)  -> multiplicar por 0.50 (-50%)
    #   Calidad muy baja (<0.20)  -> score maximo 20
    base_score = data.score or 0
    if quality_factor >= 0.75:
        final_score = base_score
    elif quality_factor >= 0.45:
        final_score = round(base_score * 0.80, 1)
    elif quality_factor >= 0.20:
        final_score = round(base_score * 0.50, 1)
    else:
        final_score = min(base_score, 20.0)

    b = Bitacora(
        student_id          = me.id,
        incident_id         = data.incident_id,
        node_id             = data.node_id,
        attack_type         = data.attack_type,
        severity            = data.severity,
        score               = final_score,
        correct_answers     = data.correct_answers,
        total_questions     = data.total_questions,
        hints_used          = data.hints_used,
        mttd_seconds        = data.mttd_seconds,
        duration_sec        = data.duration_sec,
        sintomas_observados = data.sintomas_observados,
        causa_raiz          = data.causa_raiz,
        acciones_tomadas    = data.acciones_tomadas,
        lecciones           = data.lecciones,
        collab_room_id      = data.collab_room_id,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)

    # Cargar nombre del estudiante para la respuesta
    result = await db.execute(select(Student).where(Student.id == me.id))
    student = result.scalar_one_or_none()
    out = BitacoraOut.model_validate(b)
    out.student_name = student.name if student else None
    out_dict = out.model_dump()
    out_dict["quality_factor"] = quality_factor
    out_dict["quality_label"]  = quality_label
    out_dict["score_original"] = base_score
    out_dict["score_adjusted"] = final_score
    out_dict["score_penalized"] = final_score < base_score

    # Notificar al instructor en tiempo real
    try:
        await ws_manager.broadcast("new_bitacora", {
            "student_id":    me.id,
            "student_name":  student.name if student else "Aprendiz",
            "attack_type":   data.attack_type,
            "node_id":       data.node_id,
            "score":         final_score,
            "quality_label": quality_label,
            "penalized":     final_score < base_score,
            "timestamp":     datetime.utcnow().isoformat(),
        })
    except Exception:
        pass  # no bloquear si falla el broadcast

    return out_dict


@router.get("", response_model=List[BitacoraOut])
async def list_bitacoras(
    student_id: Optional[int]  = None,
    date_str:   Optional[str]  = None,
    limit:      Optional[int]  = 100,
    db:         AsyncSession   = Depends(get_db),
    me:         Student        = Depends(get_current_student),
):
    """
    Instructor: ve todas las bitacoras (filtrable por student_id y/o fecha).
    Aprendiz: solo ve las suyas.
    date_str: filtro por dia exacto, formato YYYY-MM-DD.
    """
    filters = []
    if me.role == "student":
        filters.append(Bitacora.student_id == me.id)
    elif student_id:
        filters.append(Bitacora.student_id == student_id)

    if date_str:
        try:
            day = date.fromisoformat(date_str)
            day_start = datetime(day.year, day.month, day.day, 0, 0, 0)
            day_end   = day_start + timedelta(days=1)
            filters.append(Bitacora.created_at >= day_start)
            filters.append(Bitacora.created_at <  day_end)
        except ValueError:
            pass

    q = select(Bitacora).order_by(desc(Bitacora.created_at)).limit(limit)
    if filters:
        q = select(Bitacora).where(and_(*filters)).order_by(desc(Bitacora.created_at)).limit(limit)

    result = await db.execute(q)
    bitacoras = result.scalars().all()

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
        raise HTTPException(status_code=404, detail="Bitacora no encontrada")
    if me.role == "student" and b.student_id != me.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    sr = await db.execute(select(Student).where(Student.id == b.student_id))
    stu = sr.scalar_one_or_none()
    out = BitacoraOut.model_validate(b)
    out.student_name = stu.name if stu else "Desconocido"
    return out
