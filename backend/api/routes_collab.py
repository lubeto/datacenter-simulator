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
from ..database.models import CollabRoom, CollabMember, CollabAction, CollabBitacora, Student
from ..api.routes_students import get_current_student
from ..api.websocket import manager as ws_manager
from ..utils_time import iso_utc
from ..simulation.engine import state as sim_state

router = APIRouter(prefix="/api/collab", tags=["collab"])

VALID_ROLES = {"T1-Monitor", "T2-Analista", "Responder", "Comunicador"}


async def is_student_in_active_room(db: AsyncSession, student_id: int) -> bool:
    """¿El estudiante es miembro de alguna sala colaborativa activa?"""
    result = await db.execute(
        select(CollabMember.id)
        .join(CollabRoom, CollabRoom.id == CollabMember.room_id)
        .where(CollabMember.student_id == student_id, CollabRoom.is_active == True)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def check_collab_exclusive_lock(db: AsyncSession, current: Student) -> None:
    """Bloquea acciones individuales mientras el instructor activó el Modo
    Exclusivo de Sala Colaborativa, salvo para el instructor o estudiantes
    que sí pertenecen a una sala activa."""
    if not sim_state.collab_exclusive or current.role == "instructor":
        return
    if await is_student_in_active_room(db, current.id):
        return
    raise HTTPException(
        status_code=423,
        detail="El instructor activó el Modo Exclusivo de Sala Colaborativa. "
               "Solo los aprendices asignados a una sala pueden interactuar.",
    )


@router.get("/exclusive-status")
async def exclusive_status(
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Estado del Modo Exclusivo + si el estudiante actual está exento (en sala activa)."""
    exempt = current.role == "instructor" or await is_student_in_active_room(db, current.id)
    return {"active": sim_state.collab_exclusive, "exempt": exempt}


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
        "created_at": iso_utc(room.created_at) if room.created_at else None,
        "ended_at": iso_utc(room.ended_at) if room.ended_at else None,
    }


def _member_dict(m: CollabMember, name: str = "") -> dict:
    return {
        "id": m.id,
        "room_id": m.room_id,
        "student_id": m.student_id,
        "student_name": name,
        "role": m.role,
        "joined_at": iso_utc(m.joined_at) if m.joined_at else None,
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
        "timestamp": iso_utc(a.timestamp) if a.timestamp else None,
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

    # Si la sala viene con ataque + nodo asignado, inyectarlo de verdad en la
    # simulación — antes esto era solo metadata informativa: el banner de la
    # sala decía "DDoS en RTR-EDGE" pero el mapa de red nunca lo reflejaba
    # porque no había ningún incidente real corriendo en ese nodo.
    inject_error = None
    if body.attack_type and body.node_id:
        from ..api.routes_attacks import inject_attack_full
        try:
            await inject_attack_full(db, body.attack_type, body.node_id, tag="SALA")
        except HTTPException as e:
            inject_error = e.detail

    await ws_manager.broadcast("collab_room_created", _room_dict(room))
    out = _room_dict(room)
    if inject_error:
        out["inject_warning"] = f"La sala se creó, pero no se pudo inyectar el ataque: {inject_error}"
    return out


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

    # Registrar en sala WS para mensajes privados
    ws_manager.join_room(room_id, body.student_id)

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
    ws_manager.leave_room(room_id, student_id)
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

    ws_manager.close_room(room_id)
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
    # Solo miembros de esta sala reciben el evento (canal privado)
    await ws_manager.broadcast_to_room(room_id, "collab_action", {"room_id": room_id, "action": payload})
    return payload


@router.post("/rooms/{room_id}/join")
async def ws_join_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Estudiante notifica al servidor que está activo en la sala (restaura canal WS tras reconexión)."""
    await _get_room_or_404(db, room_id)
    ws_manager.join_room(room_id, current.id)
    return {"ok": True, "room_id": room_id, "student_id": current.id}


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


# ── Bitácora Colaborativa ──────────────────────────────────────

_ROLE_FIELD = {
    "T1-Monitor": ("t1_student_id", "t1_sintomas", "t1_saved_at"),
    "T2-Analista": ("t2_student_id", "t2_causa", "t2_saved_at"),
    "Responder":   ("resp_student_id", "resp_acciones", "resp_saved_at"),
    "Comunicador": ("com_student_id", "com_lecciones", "com_saved_at"),
}


def _bitacora_dict(b: CollabBitacora, names: dict) -> dict:
    return {
        "id": b.id,
        "room_id": b.room_id,
        "incident_type": b.incident_type,
        "node_id": b.node_id,
        "sections": {
            "T1-Monitor":  {"text": b.t1_sintomas,   "student_id": b.t1_student_id,   "name": names.get(b.t1_student_id),   "saved_at": iso_utc(b.t1_saved_at)   if b.t1_saved_at   else None},
            "T2-Analista": {"text": b.t2_causa,       "student_id": b.t2_student_id,   "name": names.get(b.t2_student_id),   "saved_at": iso_utc(b.t2_saved_at)   if b.t2_saved_at   else None},
            "Responder":   {"text": b.resp_acciones,  "student_id": b.resp_student_id, "name": names.get(b.resp_student_id), "saved_at": iso_utc(b.resp_saved_at) if b.resp_saved_at else None},
            "Comunicador": {"text": b.com_lecciones,  "student_id": b.com_student_id,  "name": names.get(b.com_student_id),  "saved_at": iso_utc(b.com_saved_at)  if b.com_saved_at  else None},
        },
        "created_at": iso_utc(b.created_at) if b.created_at else None,
        "completed_at": iso_utc(b.completed_at) if b.completed_at else None,
    }


async def _load_names(db: AsyncSession, *ids) -> dict:
    ids = [i for i in ids if i]
    if not ids:
        return {}
    result = await db.execute(select(Student.id, Student.name).where(Student.id.in_(ids)))
    return {r.id: r.name for r in result.all()}


class BitacoraRoomInit(BaseModel):
    incident_type: Optional[str] = None
    node_id: Optional[str] = None


class BitacoraSection(BaseModel):
    text: str


@router.get("/rooms/{room_id}/bitacora")
async def get_bitacora(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Obtiene la bitácora colaborativa de la sala (crea una vacía si no existe)."""
    room = await _get_room_or_404(db, room_id)
    result = await db.execute(select(CollabBitacora).where(CollabBitacora.room_id == room_id))
    bit = result.scalar_one_or_none()
    if not bit:
        bit = CollabBitacora(room_id=room_id, incident_type=room.attack_type, node_id=room.node_id)
        db.add(bit)
        await db.flush()
        await db.refresh(bit)
        await db.commit()
    names = await _load_names(db, bit.t1_student_id, bit.t2_student_id, bit.resp_student_id, bit.com_student_id)
    return _bitacora_dict(bit, names)


@router.patch("/rooms/{room_id}/bitacora")
async def save_bitacora_section(
    room_id: int,
    body: BitacoraSection,
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Estudiante guarda su sección en la bitácora colaborativa según su rol."""
    await _get_room_or_404(db, room_id)

    # Obtener rol del estudiante en esta sala
    mr = await db.execute(
        select(CollabMember.role).where(
            CollabMember.room_id == room_id,
            CollabMember.student_id == current.id,
        )
    )
    role = mr.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=403, detail="No eres miembro de esta sala")
    if role not in _ROLE_FIELD:
        raise HTTPException(status_code=400, detail=f"Rol {role} no tiene sección en la bitácora")

    sid_col, text_col, ts_col = _ROLE_FIELD[role]

    result = await db.execute(select(CollabBitacora).where(CollabBitacora.room_id == room_id))
    bit = result.scalar_one_or_none()
    if not bit:
        room = await _get_room_or_404(db, room_id)
        bit = CollabBitacora(room_id=room_id, incident_type=room.attack_type, node_id=room.node_id)
        db.add(bit)
        await db.flush()

    setattr(bit, sid_col, current.id)
    setattr(bit, text_col, body.text)
    setattr(bit, ts_col, datetime.utcnow())

    # Marcar como completa si los 4 roles guardaron
    if all([bit.t1_sintomas, bit.t2_causa, bit.resp_acciones, bit.com_lecciones]):
        bit.completed_at = bit.completed_at or datetime.utcnow()

    await db.commit()
    await db.refresh(bit)

    names = await _load_names(db, bit.t1_student_id, bit.t2_student_id, bit.resp_student_id, bit.com_student_id)
    payload = _bitacora_dict(bit, names)
    await ws_manager.broadcast_to_room(room_id, "collab_bitacora_updated", {"room_id": room_id, "bitacora": payload})
    return payload


@router.get("/bitacoras")
async def list_bitacoras(
    db: AsyncSession = Depends(get_db),
    current: Student = Depends(get_current_student),
):
    """Instructor: lista todas las bitácoras colaborativas."""
    if current.role != "instructor":
        raise HTTPException(status_code=403)
    result = await db.execute(select(CollabBitacora).order_by(CollabBitacora.created_at.desc()))
    bits = result.scalars().all()
    out = []
    for b in bits:
        names = await _load_names(db, b.t1_student_id, b.t2_student_id, b.resp_student_id, b.com_student_id)
        out.append(_bitacora_dict(b, names))
    return out
