"""
DC Monitoring Simulator - Rutas de Terminal Simulada
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends

from ..simulation.command_engine import execute_command
from ..api.routes_students import get_current_student

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


class TerminalExecRequest(BaseModel):
    command: str
    node_id: str = "WEB-01"


@router.post("/exec")
async def exec_command(
    req: TerminalExecRequest,
    current=Depends(get_current_student)
):
    """Ejecuta un comando en la terminal simulada y retorna el output."""
    output = execute_command(req.command, req.node_id, current.id)
    return {"output": output}
