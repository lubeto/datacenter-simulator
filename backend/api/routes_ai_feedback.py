"""
DC Monitoring Simulator - Feedback IA de Bitácora via Anthropic Claude
"""
import os
import httpx
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.routes_students import get_current_student
from ..database.db import get_db
from ..database.models import EvalGroup, Student, Bitacora, CollabMember, CollabRoom, CollabBitacora

logger = logging.getLogger("dc.ai_feedback")

router = APIRouter(prefix="/api/ai", tags=["ai"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5"

PROMPT_TEMPLATE = """Eres un evaluador técnico de bitácoras de incidentes de ciberseguridad en un datacenter educativo.

El aprendiz escribió esta bitácora de incidente:
---
{texto}
---

Evalúa en tres dimensiones (puntaje del 1 al 5):
1. Claridad: ¿Es fácil de entender? ¿Está bien redactada?
2. Completitud: ¿Describe qué pasó, por qué pasó y qué se hizo para resolverlo?
3. Terminología técnica: ¿Usa correctamente términos como IP, puerto, firewall, DDoS, CPU, RAM, latencia, etc.?

Luego da exactamente 3 sugerencias concretas y breves (máximo 15 palabras cada una) para mejorar la bitácora.

Responde ÚNICAMENTE en este formato JSON exacto, sin texto adicional:
{{
  "claridad": <número 1-5>,
  "completitud": <número 1-5>,
  "terminologia": <número 1-5>,
  "sugerencias": [
    "<sugerencia 1>",
    "<sugerencia 2>",
    "<sugerencia 3>"
  ],
  "resumen": "<una frase de 10 palabras máximo resumiendo la calidad general>"
}}"""


class FeedbackRequest(BaseModel):
    texto: str


@router.get("/bitacora-feedback/status")
async def get_feedback_status():
    """Verifica si la funcionalidad IA está disponible."""
    return {"available": bool(ANTHROPIC_API_KEY)}


@router.post("/bitacora-feedback")
async def get_bitacora_feedback(req: FeedbackRequest, current=Depends(get_current_student)):
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY no configurada en el servidor.", "available": False}

    texto = req.texto.strip()
    if len(texto) < 20:
        return {
            "available": True,
            "claridad": 1, "completitud": 1, "terminologia": 1,
            "sugerencias": [
                "Escribe al menos 2-3 oraciones describiendo el incidente",
                "Indica qué ataque ocurrió y en qué nodo",
                "Describe qué acción tomaste para resolverlo"
            ],
            "resumen": "Bitácora demasiado corta para evaluar"
        }

    prompt = PROMPT_TEMPLATE.format(texto=texto[:2000])

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "max_tokens": 400,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )

        if resp.status_code != 200:
            body = resp.text[:400]
            logger.error(f"Claude API HTTP {resp.status_code}: {body}")
            return {"error": f"Error de IA: HTTP {resp.status_code} — {body[:200]}", "available": False}

        data = resp.json()
        raw = data["content"][0]["text"].strip()

        # Limpiar bloque markdown si viene envuelto en ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        result["available"] = True
        result["model_used"] = _MODEL
        logger.info(f"AI feedback OK con {_MODEL}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido de Claude: {e} — raw: {raw[:200]}")
        return {"error": "La IA devolvió una respuesta con formato inválido.", "available": False}
    except Exception as ex:
        logger.error(f"Error llamando Claude API: {ex}")
        return {"error": f"Error de conexión con IA: {str(ex)}", "available": False}


TERMINAL_HINT_PROMPT = """Eres un asistente técnico de ciberseguridad en un datacenter educativo.
Un aprendiz acaba de ejecutar un comando en la terminal mientras responde a un incidente.

Ataque activo: {attack_type}
Nodo afectado: {node_id}
Comando ejecutado: {command}
Output obtenido:
{output}

Da UNA sola pista breve (máximo 20 palabras) que ayude al aprendiz a entender qué debe buscar
o qué acción tomar a continuación. Sé concreto y educativo.
NO des la respuesta directa — guía al aprendiz a descubrirla.
Responde SOLO la pista, sin prefijos ni explicaciones adicionales."""


class TerminalHintRequest(BaseModel):
    command: str
    output: str
    attack_type: str
    node_id: str


@router.post("/terminal-hint")
async def get_terminal_hint(req: TerminalHintRequest, current=Depends(get_current_student)):
    if not ANTHROPIC_API_KEY:
        return {"hint": None, "available": False}

    # Solo dar pista para comandos de diagnóstico relevantes
    diagnostic_cmds = ["netstat", "ps", "top", "tcpdump", "ss", "iptables", "cat", "tail", "grep", "df", "free"]
    if not any(req.command.strip().startswith(c) for c in diagnostic_cmds):
        return {"hint": None, "available": True}

    prompt = TERMINAL_HINT_PROMPT.format(
        attack_type=req.attack_type,
        node_id=req.node_id,
        command=req.command[:200],
        output=req.output[:800],
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "max_tokens": 80,
                    "temperature": 0.3,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )

        if resp.status_code != 200:
            return {"hint": None, "available": False}

        data = resp.json()
        hint = data["content"][0]["text"].strip()
        logger.info(f"Terminal hint OK para {req.command[:30]}")
        return {"hint": hint, "available": True}

    except Exception as ex:
        logger.warning(f"Terminal hint error: {ex}")
        return {"hint": None, "available": False}


COLLAB_HINT_PROMPT = """Eres un asistente técnico de ciberseguridad en una sala colaborativa de aprendices de datacenter.
El grupo está respondiendo a un incidente en vivo.

Incidente activo: {attack_type} en nodo {node_id}
Pregunta del aprendiz: {question}

Responde de forma breve y educativa (máximo 3 oraciones).
Guía al grupo hacia la solución — no la des directamente.
Usa terminología técnica correcta. Responde en español."""


class CollabHintRequest(BaseModel):
    question: str
    attack_type: str = ""
    node_id: str = ""


@router.post("/collab-hint")
async def get_collab_hint(req: CollabHintRequest, current=Depends(get_current_student)):
    if not ANTHROPIC_API_KEY:
        return {"hint": None, "available": False}

    question = req.question.strip()
    # Quitar prefijos @IA o ?
    for prefix in ["@ia", "@IA", "@Ia"]:
        if question.lower().startswith(prefix.lower()):
            question = question[len(prefix):].strip()
    if question.startswith("?"):
        question = question[1:].strip()

    if len(question) < 3:
        return {"hint": "¿Tienes alguna pregunta sobre el incidente? Escribe @IA seguido de tu pregunta.", "available": True}

    prompt = COLLAB_HINT_PROMPT.format(
        attack_type=req.attack_type or "desconocido",
        node_id=req.node_id or "—",
        question=question[:400],
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "max_tokens": 150,
                    "temperature": 0.4,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )

        if resp.status_code != 200:
            return {"hint": None, "available": False}

        data = resp.json()
        hint = data["content"][0]["text"].strip()
        logger.info(f"Collab hint OK para pregunta: {question[:40]}")
        return {"hint": hint, "available": True}

    except Exception as ex:
        logger.warning(f"Collab hint error: {ex}")
        return {"hint": None, "available": False}


BITACORA_TUTOR_PROMPT = """Eres un tutor socrático de ciberseguridad ayudando a un aprendiz a ESCRIBIR su propia
bitácora de incidente — nunca le redactas el texto, solo le haces preguntas que lo guíen a pensar y describir
con sus propias palabras.

Campo de la bitácora que está completando: {campo}
Ataque: {attack_type} en nodo {node_id}
Lo que el aprendiz ha escrito hasta ahora en este campo: "{texto_actual}"

Responde con 1-2 preguntas breves (máximo 25 palabras en total) que lo ayuden a profundizar o corregir
ese campo específico. NO le digas qué escribir, NO redactes frases para que copie. Solo preguntas guía.
Si el campo ya está vacío o muy corto, pregunta por lo más básico (qué observó, qué nodo, qué hizo).
Responde en español, solo las preguntas, sin prefijos."""


class BitacoraTutorRequest(BaseModel):
    campo: str            # "sintomas" | "causa" | "acciones" | "lecciones"
    texto_actual: str = ""
    attack_type: str = ""
    node_id: str = ""


_CAMPO_LABELS = {
    "sintomas": "Síntomas observados",
    "causa": "Causa raíz identificada",
    "acciones": "Acciones tomadas",
    "lecciones": "Lecciones aprendidas",
}


@router.post("/bitacora-tutor")
async def get_bitacora_tutor_hint(req: BitacoraTutorRequest, current=Depends(get_current_student)):
    """Tutor socrático: hace preguntas guía para que el aprendiz redacte su propia
    bitácora, en vez de generar el texto por él (evita que la IA reemplace el copia-pega)."""
    if not ANTHROPIC_API_KEY:
        return {"hint": None, "available": False}

    prompt = BITACORA_TUTOR_PROMPT.format(
        campo=_CAMPO_LABELS.get(req.campo, req.campo),
        attack_type=req.attack_type or "desconocido",
        node_id=req.node_id or "—",
        texto_actual=(req.texto_actual or "(vacío)")[:500],
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "max_tokens": 120,
                    "temperature": 0.4,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )

        if resp.status_code != 200:
            return {"hint": None, "available": False}

        data = resp.json()
        hint = data["content"][0]["text"].strip()
        logger.info(f"Bitacora tutor OK para campo: {req.campo}")
        return {"hint": hint, "available": True}

    except Exception as ex:
        logger.warning(f"Bitacora tutor error: {ex}")
        return {"hint": None, "available": False}


GROUP_REPORT_PROMPT = """Eres un redactor técnico encargado de producir el informe formal de cierre de un
ejercicio grupal de respuesta a incidentes de ciberseguridad, en un datacenter educativo del SENA.

Grupo: {group_name}
Integrantes: {member_names}

A continuación, el material registrado durante el ejercicio (varios días, varios incidentes):
las bitácoras individuales de cada integrante, y las bitácoras de sesiones colaborativas
("Sesión Colaborativa") donde el grupo trabajó junto, dividido por rol (T1-Monitor, T2-Analista,
Responder, Comunicador):

{bitacoras_block}

Redacta un INFORME FORMAL GRUPAL en español, en este formato exacto con encabezados markdown:

## Resumen Ejecutivo
(3-4 oraciones resumiendo el desempeño general del grupo durante el ejercicio)

## Incidentes Atendidos
(lista cada incidente único atendido por el grupo: tipo de ataque, nodo, quién lo documentó, y un resumen de causa raíz y acciones tomadas en 1-2 oraciones)

## Contribución por Integrante
(una línea por integrante resumiendo qué incidentes documentó y la calidad de su análisis)

## Lecciones Aprendidas del Grupo
(3-5 lecciones técnicas consolidadas, sintetizando lo que escribieron los integrantes — no inventes información que no esté en las bitácoras)

## Recomendaciones
(2-3 recomendaciones concretas para mejorar como equipo de respuesta a incidentes)

Usa únicamente la información de las bitácoras provistas. No inventes incidentes ni datos que no estén ahí.
Sé profesional, técnico y conciso."""


class GroupReportRequest(BaseModel):
    group_id: int


@router.post("/group-report")
async def generate_group_report(
    req: GroupReportRequest,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student),
):
    """Genera un informe formal grupal con IA a partir de las bitácoras de todos
    los integrantes de un EvalGroup (sesión grupal evaluativa)."""
    if not ANTHROPIC_API_KEY:
        return {"available": False, "error": "ANTHROPIC_API_KEY no configurada en el servidor."}

    group = (await db.execute(
        select(EvalGroup).where(EvalGroup.id == req.group_id)
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")

    student_ids = json.loads(group.student_ids_json or "[]")
    if current.role != "instructor" and current.id not in student_ids:
        raise HTTPException(status_code=403, detail="No perteneces a este grupo")

    member_names = []
    bitacoras_block_parts = []
    for sid in student_ids:
        student = (await db.execute(select(Student).where(Student.id == sid))).scalar_one_or_none()
        name = student.name if student else f"Estudiante #{sid}"
        member_names.append(name)

        bits = (await db.execute(
            select(Bitacora).where(Bitacora.student_id == sid).order_by(Bitacora.created_at)
        )).scalars().all()

        if not bits:
            bitacoras_block_parts.append(f"### {name}\n(sin bitácoras registradas)\n")
            continue

        lines = [f"### {name}"]
        for b in bits:
            lines.append(
                f"- **{b.attack_type}** en {b.node_id} (score {b.score:.0f}/100)\n"
                f"  Síntomas: {b.sintomas_observados}\n"
                f"  Causa raíz: {b.causa_raiz}\n"
                f"  Acciones: {b.acciones_tomadas}\n"
                f"  Lecciones: {b.lecciones}"
            )
        bitacoras_block_parts.append("\n".join(lines))

    # Sesiones colaborativas (Sala Colaborativa): la bitácora ahí vive en
    # CollabBitacora (una por sala, 4 secciones por rol) — no en Bitacora
    # individual. Se busca cualquier sala donde haya participado algún
    # integrante del grupo y se agrega su contenido también.
    has_collab_content = False
    member_room_ids = (await db.execute(
        select(CollabMember.room_id).where(CollabMember.student_id.in_(student_ids)).distinct()
    )).scalars().all()

    for room_id in member_room_ids:
        room = (await db.execute(select(CollabRoom).where(CollabRoom.id == room_id))).scalar_one_or_none()
        cb = (await db.execute(select(CollabBitacora).where(CollabBitacora.room_id == room_id))).scalar_one_or_none()
        if not room:
            continue

        sections = []
        if cb:
            sec_map = [
                ("T1-Monitor (síntomas)", cb.t1_student_id, cb.t1_sintomas),
                ("T2-Analista (causa raíz)", cb.t2_student_id, cb.t2_causa),
                ("Responder (acciones)", cb.resp_student_id, cb.resp_acciones),
                ("Comunicador (lecciones)", cb.com_student_id, cb.com_lecciones),
            ]
            for label, sid, text in sec_map:
                if not text:
                    continue
                sec_name = "?"
                if sid:
                    sec_student = (await db.execute(select(Student).where(Student.id == sid))).scalar_one_or_none()
                    sec_name = sec_student.name if sec_student else f"#{sid}"
                sections.append(f"  {label} — {sec_name}: {text}")
                has_collab_content = True

        if sections:
            bitacoras_block_parts.append(
                f"### Sesión Colaborativa — {room.name} ({room.attack_type or '?'} en {room.node_id or '?'})\n"
                + "\n".join(sections)
            )

    bitacoras_block = "\n\n".join(bitacoras_block_parts)
    if len(bitacoras_block) > 14000:
        bitacoras_block = bitacoras_block[:14000] + "\n[... contenido truncado por longitud ...]"

    has_individual_content = any(b.strip() and "sin bitácoras" not in b for b in bitacoras_block_parts[:len(student_ids)])
    if not has_individual_content and not has_collab_content:
        return {"available": True, "error": "El grupo no tiene bitácoras ni sesiones colaborativas registradas todavía. Genera el informe después de que los integrantes documenten al menos un incidente."}

    prompt = GROUP_REPORT_PROMPT.format(
        group_name=group.name or f"Grupo #{group.id}",
        member_names=", ".join(member_names),
        bitacoras_block=bitacoras_block,
    )

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "max_tokens": 1800,
                    "temperature": 0.3,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )

        if resp.status_code != 200:
            body = resp.text[:300]
            logger.error(f"Group report Claude API HTTP {resp.status_code}: {body}")
            return {"available": False, "error": f"Error de IA: HTTP {resp.status_code}"}

        data = resp.json()
        report_text = data["content"][0]["text"].strip()
        logger.info(f"Group report OK para grupo {group.id} ({group.name})")
        return {
            "available": True,
            "report": report_text,
            "group_name": group.name or f"Grupo #{group.id}",
            "member_names": member_names,
            "model_used": _MODEL,
        }

    except Exception as ex:
        logger.error(f"Group report error: {ex}")
        return {"available": False, "error": f"Error de conexión con IA: {str(ex)}"}
