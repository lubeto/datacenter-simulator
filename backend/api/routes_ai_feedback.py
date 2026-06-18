"""
DC Monitoring Simulator - Feedback IA de Bitácora via Anthropic Claude
"""
import os
import httpx
import json
import logging
from fastapi import APIRouter
from pydantic import BaseModel

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
async def get_bitacora_feedback(req: FeedbackRequest):
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
async def get_terminal_hint(req: TerminalHintRequest):
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
