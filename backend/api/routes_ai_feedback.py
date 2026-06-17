"""
DC Monitoring Simulator - Feedback IA de Bitácora via Gemini
"""
import os
import httpx
import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("dc.ai_feedback")

router = APIRouter(prefix="/api/ai", tags=["ai"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
# Orden de preferencia: flash estable → flash exp → pro como último recurso
_MODELS = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash-8b",
]

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
    """Verifica si la funcionalidad IA está disponible (para que el frontend no muestre el botón si no hay clave)."""
    return {"available": bool(GEMINI_API_KEY)}


@router.post("/bitacora-feedback")
async def get_bitacora_feedback(req: FeedbackRequest):
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY no configurada en el servidor.", "available": False}

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
    import json

    last_error = "Error desconocido"
    async with httpx.AsyncClient(timeout=20.0) as client:
        for model in _MODELS:
            url = f"{_GEMINI_BASE}{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                resp = await client.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    result = json.loads(raw.strip())
                    result["available"] = True
                    result["model_used"] = model
                    logger.info(f"AI feedback OK usando modelo {model}")
                    return result
                else:
                    body = resp.text[:300]
                    logger.warning(f"Gemini {model} → HTTP {resp.status_code}: {body}")
                    if resp.status_code == 429:
                        last_error = f"Cuota agotada en modelo {model}. (HTTP 429)"
                    elif resp.status_code == 403:
                        last_error = f"Clave sin acceso al modelo {model}. (HTTP 403) — verifica que la API esté habilitada en Google Cloud."
                    elif resp.status_code == 404:
                        last_error = f"Modelo {model} no existe o no está disponible en tu región."
                    else:
                        last_error = f"HTTP {resp.status_code} en {model}: {body}"
            except Exception as ex:
                logger.warning(f"Gemini {model} excepción: {ex}")
                last_error = str(ex)

    logger.error(f"Todos los modelos Gemini fallaron. Último error: {last_error}")
    return {"error": last_error, "available": False}
