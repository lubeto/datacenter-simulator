"""
DC Monitoring Simulator - WebSocket Manager
Maneja conexiones en tiempo real para el dashboard
"""
import json
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("dc.websocket")


class ConnectionManager:
    """Gestiona todas las conexiones WebSocket activas."""

    def __init__(self):
        self.active: Set[WebSocket] = set()
        self.student_map: Dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket, student_info: dict = None):
        await ws.accept()
        self.active.add(ws)
        if student_info:
            self.student_map[ws] = student_info
        logger.info(f"WS conectado. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        self.student_map.pop(ws, None)
        logger.info(f"WS desconectado. Total: {len(self.active)}")

    async def broadcast(self, event_type: str, data: Any):
        """Envía un mensaje a todos los clientes conectados."""
        if not self.active:
            return
        message = json.dumps({"event": event_type, "data": data})
        disconnected = set()
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self.disconnect(ws)

    async def send_to(self, ws: WebSocket, event_type: str, data: Any):
        """Envía un mensaje a un cliente específico."""
        try:
            await ws.send_text(json.dumps({"event": event_type, "data": data}))
        except Exception:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self.active)

    async def broadcast_to_student(self, student_id: int, event_type: str, data: Any):
        """Envía un mensaje solo al WebSocket de un estudiante específico."""
        message = json.dumps({"event": event_type, "data": data})
        for ws, info in list(self.student_map.items()):
            if info and info.get("id") == student_id:
                try:
                    await ws.send_text(message)
                except Exception:
                    self.disconnect(ws)

    def get_connected_students(self):
        return list(self.student_map.values())


# Instancia global
manager = ConnectionManager()
