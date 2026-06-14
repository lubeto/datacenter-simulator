"""
DC Monitoring Simulator - Rutas del Editor de Reglas de Firewall
"""
from typing import Optional, Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from ..simulation.command_engine import (
    get_rules, add_block_ip, add_block_port, remove_rule, flush_rules,
)
from ..simulation.engine import state as sim_state
from ..api.routes_students import get_current_student

router = APIRouter(prefix="/api/firewall", tags=["firewall"])


class FirewallRuleRequest(BaseModel):
    action: Literal["block_ip", "block_port", "flush", "remove"]
    ip: Optional[str] = None
    port: Optional[int] = None
    proto: str = "tcp"
    index: Optional[int] = None


def _attacks_summary():
    return [
        {
            "node_id": node_id,
            "type": attack.get("type"),
            "name": attack.get("name"),
            "severity": attack.get("severity"),
            "mitigated": attack.get("mitigated", False),
        }
        for node_id, attack in sim_state.active_attacks.items()
    ]


@router.get("/status")
async def firewall_status(current=Depends(get_current_student)):
    """Retorna las reglas actuales del estudiante y los ataques activos (con su estado de mitigación)."""
    return {"rules": get_rules(current.id), "attacks": _attacks_summary()}


@router.post("/rules")
async def manage_rule(req: FirewallRuleRequest, current=Depends(get_current_student)):
    """Agrega, elimina o limpia reglas de iptables del estudiante."""
    try:
        if req.action == "block_ip":
            if not req.ip:
                raise HTTPException(status_code=400, detail="Se requiere 'ip'")
            msg = add_block_ip(current.id, req.ip)
        elif req.action == "block_port":
            if not req.port:
                raise HTTPException(status_code=400, detail="Se requiere 'port'")
            msg = add_block_port(current.id, req.port, req.proto)
        elif req.action == "remove":
            if req.index is None:
                raise HTTPException(status_code=400, detail="Se requiere 'index'")
            msg = remove_rule(current.id, req.index)
        else:  # flush
            msg = flush_rules(current.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": msg, "rules": get_rules(current.id), "attacks": _attacks_summary()}
