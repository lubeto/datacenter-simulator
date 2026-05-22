"""
DC Monitoring Simulator - Rutas de Estudiantes y Auth
"""
import os
from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from collections import defaultdict
import time as _time

from ..database.db import get_db
from ..database import crud
from ..auth.jwt_handler import (
    hash_password, verify_password,
    create_access_token, decode_token, EXPIRE_MIN
)

# ── Rate limiting en memoria (por IP) ────────────────────────
_login_attempts: dict = defaultdict(list)
_LOGIN_WINDOW = 60    # segundos
_LOGIN_MAX    = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))

def _check_login_rate(ip: str):
    now = _time.monotonic()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW]
    if len(_login_attempts[ip]) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos de login. Espera {_LOGIN_WINDOW}s.",
            headers={"Retry-After": str(_LOGIN_WINDOW)},
        )
    _login_attempts[ip].append(now)

router = APIRouter(prefix="/api/students", tags=["students"])
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Schemas ──────────────────────────────────────────────────
class StudentCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "student"

class StudentOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    total_sessions: int
    avg_mttd_seconds: float
    avg_mttr_seconds: float
    avg_score: float

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    student: StudentOut

class SessionStart(BaseModel):
    student_id: int

class SessionClose(BaseModel):
    session_id: int


# ── Dependency: obtener usuario actual ───────────────────────
async def get_current_student(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    student = await crud.get_student_by_id(db, int(payload.get("sub", 0)))
    if not student:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return student


async def require_instructor(student=Depends(get_current_student)):
    if student.role != "instructor":
        raise HTTPException(status_code=403, detail="Solo instructores pueden acceder")
    return student


# ── Auth Routes ───────────────────────────────────────────────
@auth_router.post("/register", response_model=StudentOut)
async def register(
    data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Registrar nuevo estudiante. Solo instructores autenticados pueden crear cuentas."""
    existing = await crud.get_student_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    hashed = hash_password(data.password)
    student = await crud.create_student(db, data.name, data.email, hashed, data.role)
    return student


@auth_router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP", "")
        or (request.client.host if request.client else "unknown")
    )
    _check_login_rate(client_ip)
    student = await crud.get_student_by_email(db, form.username)
    if not student or not verify_password(form.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_access_token(
        {"sub": str(student.id), "email": student.email, "role": student.role},
        timedelta(minutes=EXPIRE_MIN)
    )
    return {"access_token": token, "token_type": "bearer", "student": student}


@auth_router.get("/me", response_model=StudentOut)
async def get_me(current=Depends(get_current_student)):
    return current


# ── Student Routes ───────────────────────────────────────────
@router.get("/", response_model=List[StudentOut])
async def list_students(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    return await crud.get_all_students(db)


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    if current.role != "instructor" and current.id != student_id:
        raise HTTPException(status_code=403, detail="Sin permiso")
    student = await crud.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return student


@router.delete("/{student_id}")
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    """Eliminar cuenta de estudiante (solo instructor). Limpia registros relacionados primero."""
    from sqlalchemy import delete as sql_delete
    from ..database.models import (
        Session as SessionModel, Report, MitigationAction,
        Alert, PracticeSession, GuidedSession, SSTProtocolSession
    )

    student = await crud.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    if student.role == "instructor":
        raise HTTPException(status_code=403, detail="No se puede eliminar una cuenta de instructor")

    # Eliminar registros dependientes en orden correcto
    await db.execute(sql_delete(GuidedSession).where(GuidedSession.student_id == student_id))
    await db.execute(sql_delete(SSTProtocolSession).where(SSTProtocolSession.student_id == student_id))
    await db.execute(sql_delete(PracticeSession).where(PracticeSession.student_id == student_id))
    await db.execute(sql_delete(MitigationAction).where(MitigationAction.student_id == student_id))
    await db.execute(sql_delete(Report).where(Report.student_id == student_id))
    # Alertas acknowledgeadas por este estudiante → desasociar
    await db.execute(
        sql_delete(Alert).where(Alert.acknowledged_by == student_id)
    )
    # Sesiones del estudiante (y sus incidentes asociados los dejamos huérfanos nullable)
    await db.execute(sql_delete(SessionModel).where(SessionModel.student_id == student_id))

    await db.delete(student)
    await db.commit()
    return {"ok": True, "deleted_id": student_id}


@router.post("/sessions/start")
async def start_session(
    data: SessionStart,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    session = await crud.create_session(db, data.student_id)
    return {"session_id": session.id, "started_at": session.started_at}


@router.post("/sessions/close")
async def close_session(
    data: SessionClose,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    session = await crud.close_session(db, data.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return {"session_id": session.id, "duration_min": session.duration_min, "score": session.score}


@router.get("/sessions/active")
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_instructor)
):
    sessions = await crud.get_active_sessions(db)
    return sessions
