"""
DC Monitoring Simulator - Rutas de Visor de Logs en Crudo
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from ..simulation.log_generator import generate_logs
from ..api.routes_students import get_current_student

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/live")
async def get_live_logs(
    type: str = "access",
    node_id: str = "WEB-01",
    n: int = 40,
    _=Depends(get_current_student)
):
    """Genera logs en crudo (access/auth/system) coherentes con el estado del nodo."""
    if type not in ("access", "auth", "system"):
        raise HTTPException(status_code=400, detail="type debe ser access, auth o system")
    n = max(1, min(n, 100))
    return {"type": type, "node_id": node_id, "lines": generate_logs(type, node_id, n)}
