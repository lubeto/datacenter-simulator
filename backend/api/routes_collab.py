"""
DC Monitoring Simulator - Sala Colaborativa
Rutas para gestión de salas, miembros, acciones y chat en tiempo real.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..database.db import get_db
from ..database.models import CollabRoom, CollabMember, CollabAction, Student
from ..api.routes_students import get_current_student
from ..api.websocket import manager as ws_manager

router = APIRouter(prefix="/api/collab", tags=["collab"])

VALID_ROLES = {"T1-Monitor", "T2-Analista", "Responder", "Comunicador"}


# ── Schemas ──────────────────────────────────────────────────

class RoomCreate(BaseModel):
    name: str
    attack_type: Optional[str] = None
    node_id: Optional[str] = None


class MemberAdd(BaseModel):
    student_id: int
    role: str  # T1-Monitor | T2-Analista | Responder | Comunicador


class ActionCreate(BaseModel):
    action_type: str   # block_ip | restart_service | terminal_cmd | chat
    detail: str
    is_chat: bool = False


# ── Helpers ───────────────────────────────────────────────────

async def _get_room_or_404(db: AsyncSession, room_id: int) -> CollabRoom:
    result = await db.execute(select(CollabRoom).where(CollabRoom.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return room


def _room_dict(room: CollabRoom) -> dict:
    return {
        "id": room.id,
        "name": room.name,
        "instructor_id": room.instructor_id,
        "attack_type": room.attack_type,
        "node_id": room.node_id,
        "is_active": room.is_active,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "ended_at": room.ended_at.isoformat() if room.ended_at else None,
    }


def _member_dict(m: CollabMember, name: str = "") -> dict:
    return {
        "id": m.id,
        "room_id": m.room_id,
        "student_id": m.student_id,
        "student_name": name,
        "role": m.role,
        "joined_at": m.joined_at.isoformat() if m.joined_at else None,
    }


def _action_dict(a: CollabAction, student_name: str = "") -> dict:
    return {
        "id": a.id,
        "room_id": a.room_id,
        "student_id": a.student_id,
        "student_name": student_name,
        "action_type": a.action_type,
        "detail": a.detail,
        "is_chat": a.is_chat,
        "timestamp": a.timestamp.isoformat() if a.timestamp else None,
    }


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/rooms")
async def create_room(
    body: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Instructor crea una sala colaborativa."""
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores pueden crear salas")

    room = CollabRoom(
        name=body.name,
        instructor_id=current.id,
        attack_type=body.attack_type,
        node_id=body.node_id,
        is_active=True,
    )
    db.add(room)
    await db.flush()
    await db.refresh(room)
    await db.commit()

    await ws_manager.broadcast("collab_room_created", _room_dict(room))
    return _room_dict(room)


@router.get("/rooms")
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Lista salas activas. Instructor ve todas; estudiante ve solo las suyas."""
    if current.role == "instructor":
        result = await db.execute(
            select(CollabRoom).where(CollabRoom.is_active == True).order_by(CollabRoom.created_at.desc())
        )
        rooms = result.scalars().all()
        return [_room_dict(r) for r in rooms]
    else:
        # Estudiante: solo salas donde es miembro
        result = await db.execute(
            select(CollabRoom)
            .join(CollabMember, CollabMember.room_id == CollabRoom.id)
            .where(CollabMember.student_id == current.id)
            .where(CollabRoom.is_active == True)
        )
        rooms = result.scalars().all()
        return [_room_dict(r) for r in rooms]


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Detalle de sala con miembros y sus roles."""
    room = await _get_room_or_404(db, room_id)

    # Cargar miembros con nombres
    members_result = await db.execute(
        select(CollabMember, Student.name)
        .join(Student, Student.id == CollabMember.student_id)
        .where(CollabMember.room_id == room_id)
    )
    members = [_member_dict(m, name) for m, name in members_result.all()]

    data = _room_dict(room)
    data["members"] = members
    return data


@router.post("/rooms/{room_id}/members")
async def add_member(
    room_id: int,
    body: MemberAdd,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Instructor agrega estudiante con rol a la sala."""
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores pueden asignar miembros")

    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Válidos: {VALID_ROLES}")

    room = await _get_room_or_404(db, room_id)

    # Verificar que el estudiante existe
    st = await db.execute(select(Student).where(Student.id == body.student_id))
    student = st.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Verificar que no esté ya en la sala
    existing = await db.execute(
        select(CollabMember).where(
            CollabMember.room_id == room_id,
            CollabMember.student_id == body.student_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Estudiante ya está en la sala")

    member = CollabMember(room_id=room_id, student_id=body.student_id, role=body.role)
    db.add(member)
    await db.flush()
    await db.refresh(member)
    await db.commit()

    payload = _member_dict(member, student.name)
    await ws_manager.broadcast("collab_member_added", {"room_id": room_id, "member": payload})
    return payload


@router.delete("/rooms/{room_id}/members/{student_id}")
async def remove_member(
    room_id: int,
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Instructor remueve estudiante de la sala."""
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores pueden remover miembros")

    result = await db.execute(
        select(CollabMember).where(
            CollabMember.room_id == room_id,
            CollabMember.student_id == student_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Miembro no encontrado en la sala")

    await db.delete(member)
    await db.commit()
    await ws_manager.broadcast("collab_member_removed", {"room_id": room_id, "student_id": student_id})
    return {"ok": True}


@router.delete("/rooms/{room_id}")
async def close_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Instructor cierra la sala."""
    if current.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores pueden cerrar salas")

    room = await _get_room_or_404(db, room_id)
    room.is_active = False
    room.ended_at = datetime.utcnow()
    await db.commit()

    await ws_manager.broadcast("collab_room_closed", {"room_id": room_id})
    return {"ok": True}


@router.get("/rooms/{room_id}/actions")
async def get_actions(
    room_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Log de acciones y chat de la sala (más recientes primero)."""
    result = await db.execute(
        select(CollabAction, Student.name)
        .join(Student, Student.id == CollabAction.student_id)
        .where(CollabAction.room_id == room_id)
        .order_by(CollabAction.timestamp.desc())
        .limit(limit)
    )
    rows = result.all()
    # Invertir para orden cronológico
    return [_action_dict(a, name) for a, name in reversed(rows)]


@router.post("/rooms/{room_id}/actions")
async def post_action(
    room_id: int,
    body: ActionCreate,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Estudiante o instructor registra una acción técnica o mensaje de chat."""
    await _get_room_or_404(db, room_id)

    action = CollabAction(
        room_id=room_id,
        student_id=current.id,
        action_type=body.action_type,
        detail=body.detail,
        is_chat=body.is_chat,
    )
    db.add(action)
    await db.flush()
    await db.refresh(action)
    await db.commit()

    payload = _action_dict(action, current.name)
    # Broadcast solo a miembros de esta sala via WS (usamos evento con room_id para filtrar en frontend)
    await ws_manager.broadcast("collab_action", {"room_id": room_id, "action": payload})
    return payload


@router.get("/my-room")
async def my_room(
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Estudiante obtiene su sala activa + rol asignado."""
    result = await db.execute(
        select(CollabRoom, CollabMember.role)
        .join(CollabMember, CollabMember.room_id == CollabRoom.id)
        .where(CollabMember.student_id == current.id)
        .where(CollabRoom.is_active == True)
        .order_by(CollabRoom.created_at.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return {"room": None, "role": None}

    room, role = row
    data = _room_dict(room)
    data["my_role"] = role

    # Cargar miembros
    members_result = await db.execute(
        select(CollabMember, Student.name)
        .join(Student, Student.id == CollabMember.student_id)
        .where(CollabMember.room_id == room.id)
    )
    data["members"] = [_member_dict(m, name) for m, name in members_result.all()]
    return {"room": data, "role": role}
