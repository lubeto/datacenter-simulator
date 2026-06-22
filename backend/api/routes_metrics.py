"""
DC Monitoring Simulator - Rutas de Metricas, SST y SSL
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.db import get_db
from ..database import crud
from ..simulation.engine import generate_full_snapshot, state as sim_state
from ..simulation.nodes import get_all_nodes, get_all_sensors
from ..api.routes_students import get_current_student
from ..utils_time import iso_utc

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/snapshot")
async def get_snapshot():
    return generate_full_snapshot()


@router.get("/nodes")
async def get_nodes():
    nodes = get_all_nodes()
    return [
        {
            "id": n.id, "name": n.name, "type": n.node_type,
            "ip": n.ip, "zone": n.zone, "services": n.services,
            "is_online": n.id not in sim_state.offline_nodes,
            "has_ssl": n.has_ssl, "ssl_domain": n.ssl_domain,
            "bandwidth_mbps": n.bandwidth_mbps,
        }
        for n in nodes
    ]


@router.get("/history/{node_id}")
async def get_node_history(
    node_id: str,
    limit: int = Query(60, le=500),
    minutes: Optional[int] = Query(None, description="Ultimos N minutos"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_student)
):
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from ..database.models import Metric

    async with db as session:
        q = select(Metric).where(Metric.node_id == node_id)
        if minutes:
            since = datetime.utcnow() - timedelta(minutes=minutes)
            q = q.where(Metric.timestamp >= since)
        q = q.order_by(Metric.timestamp.desc()).limit(limit)
        result = await session.execute(q)
        metrics = list(reversed(result.scalars().all()))

    return [
        {
            "timestamp":       iso_utc(m.timestamp) if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            "cpu_pct":         m.cpu_pct,
            "ram_pct":         m.ram_pct,
            "net_in_mbps":     m.net_in_mbps,
            "net_out_mbps":    m.net_out_mbps,
            "latency_ms":      m.latency_ms,
            "packet_loss_pct": m.packet_loss_pct,
            "disk_used_pct":   m.disk_used_pct,
            "disk_io_mbps":    m.disk_io_mbps,
            "connections":     m.connections,
            "is_online":       m.is_online,
        }
        for m in metrics
    ]


@router.get("/summary")
async def get_metrics_summary(
    _=Depends(get_current_student)
):
    snapshot = generate_full_snapshot()
    nodes = snapshot.get("nodes", {})
    total = len(nodes)
    online  = sum(1 for n in nodes.values() if n.get("metrics", {}).get("is_online", True))
    cpu_avg = sum(n.get("metrics", {}).get("cpu_pct", 0) for n in nodes.values()) / max(total, 1)
    ram_avg = sum(n.get("metrics", {}).get("ram_pct", 0) for n in nodes.values()) / max(total, 1)
    net_in  = sum(n.get("metrics", {}).get("net_in_mbps", 0) for n in nodes.values())
    net_out = sum(n.get("metrics", {}).get("net_out_mbps", 0) for n in nodes.values())
    return {
        "total_nodes":        total,
        "online_nodes":       online,
        "offline_nodes":      total - online,
        "cpu_avg_pct":        round(cpu_avg, 1),
        "ram_avg_pct":        round(ram_avg, 1),
        "net_in_total_mbps":  round(net_in, 1),
        "net_out_total_mbps": round(net_out, 1),
        "active_attacks":     len(sim_state.active_attacks),
        "timestamp":          snapshot.get("timestamp"),
    }


@router.get("/sst")
async def get_sst_status():
    from ..simulation.engine import generate_sst_reading
    sensors = get_all_sensors()
    result = []
    for sensor in sensors:
        reading = generate_sst_reading(sensor)
        result.append({
            "id":                 sensor.id,
            "name":               sensor.name,
            "type":               sensor.sensor_type,
            "zone":               sensor.zone,
            "unit":               sensor.unit,
            "normal_min":         sensor.normal_min,
            "normal_max":         sensor.normal_max,
            "warning_threshold":  sensor.warning_threshold,
            "critical_threshold": sensor.critical_threshold,
            **reading
        })
    return result


@router.get("/ssl")
async def get_ssl_status(db: AsyncSession = Depends(get_db)):
    certs = await crud.get_all_ssl_certs(db)
    return certs


@router.get("/alerts")
async def get_active_alerts(db: AsyncSession = Depends(get_db)):
    alerts = await crud.get_active_alerts(db)
    return alerts


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_student)
):
    alert = await crud.acknowledge_alert(db, alert_id, current.id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return {"acknowledged": True, "alert_id": alert_id}
