"""
DC Monitoring Simulator - Motor de Generación de Métricas
Genera datos realistas con ruido gaussiano, patrones diurnos y efectos de ataques
"""
import random
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List
import numpy as np

from .nodes import DC_NODES, SST_SENSORS, Node, SSTSensor


# ============================================================
# ESTADO GLOBAL DEL SIMULADOR
# ============================================================
class SimulatorState:
    """Estado mutable compartido del simulador."""
    def __init__(self):
        self.active_attacks: Dict[str, dict] = {}     # node_id -> attack_info
        self.node_overrides: Dict[str, dict] = {}     # node_id -> forced values
        self.offline_nodes: set = set()               # node_ids caídos
        self.maintenance_nodes: set = set()           # nodos en mantenimiento
        self.sst_overrides: Dict[str, dict] = {}      # sensor_id -> forced values
        self.simulation_time_offset: int = 0          # offset en horas (simula hora del día)
        self.is_paused: bool = False                  # pausa global (Modo Clase en Vivo)

    def get_simulated_hour(self) -> int:
        """Hora del día para patrones de carga (0-23)."""
        real_hour = datetime.utcnow().hour
        return (real_hour + self.simulation_time_offset) % 24


# Instancia global
state = SimulatorState()


# ============================================================
# PATRONES DE CARGA POR HORA
# ============================================================
LOAD_PATTERN = {
    0: 0.15, 1: 0.12, 2: 0.10, 3: 0.10, 4: 0.11, 5: 0.15,
    6: 0.20, 7: 0.30, 8: 0.55, 9: 0.75, 10: 0.85, 11: 0.90,
    12: 0.80, 13: 0.88, 14: 0.92, 15: 0.90, 16: 0.85, 17: 0.75,
    18: 0.60, 19: 0.45, 20: 0.35, 21: 0.28, 22: 0.22, 23: 0.18,
}

NODE_BASE_LOAD = {
    "server":      {"cpu": 0.35, "ram": 0.55, "net": 0.20},
    "loadbalancer":{"cpu": 0.25, "ram": 0.40, "net": 0.60},
    "firewall":    {"cpu": 0.20, "ram": 0.30, "net": 0.70},
    "router":      {"cpu": 0.15, "ram": 0.20, "net": 0.80},
    "switch":      {"cpu": 0.10, "ram": 0.15, "net": 0.75},
    "storage":     {"cpu": 0.30, "ram": 0.60, "net": 0.25},
    "database":    {"cpu": 0.50, "ram": 0.70, "net": 0.15},
}


def _gaussian_noise(value: float, std_pct: float = 0.05) -> float:
    """Añade ruido gaussiano realista."""
    noise = np.random.normal(0, std_pct * value)
    return max(0.0, value + noise)


def _clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def _hourly_factor(hour: int, base: float) -> float:
    """Multiplica la carga base por el patrón horario."""
    return base + (1.0 - base) * LOAD_PATTERN.get(hour, 0.5)


# ============================================================
# GENERADOR DE MÉTRICAS DE NODO
# ============================================================
def generate_node_metrics(node: Node) -> Dict[str, Any]:
    """Genera métricas realistas para un nodo."""

    # Nodo offline
    if node.id in state.offline_nodes:
        return {
            "cpu_pct": 0.0, "ram_pct": 0.0,
            "disk_io_mbps": 0.0, "disk_used_pct": _clamp(random.uniform(40, 80), 0, 100),
            "net_in_mbps": 0.0, "net_out_mbps": 0.0,
            "latency_ms": 9999.0, "packet_loss_pct": 100.0,
            "connections": 0, "is_online": False, "uptime_pct": 0.0
        }

    hour = state.get_simulated_hour()
    base = NODE_BASE_LOAD.get(node.node_type, NODE_BASE_LOAD["server"])
    load_factor = LOAD_PATTERN.get(hour, 0.5)

    # Base de CPU y RAM según tipo + hora
    cpu_base = _hourly_factor(hour, base["cpu"]) * 100
    ram_base = base["ram"] * 100 + load_factor * 15

    # DB servers: más RAM, más I/O
    disk_io_base = 50.0 if node.node_type == "storage" else 20.0
    if "postgresql" in node.services or "mysql" in node.services:
        ram_base *= 1.3
        disk_io_base *= 2.5

    # Red: switches y routers tienen más tráfico
    net_base = base["net"] * node.bandwidth_mbps * load_factor

    # Aplicar ruido
    cpu = _clamp(_gaussian_noise(cpu_base, 0.08), 0, 100)
    ram = _clamp(_gaussian_noise(ram_base, 0.04), 20, 95)
    disk_io = _clamp(_gaussian_noise(disk_io_base, 0.15), 0, 500)
    disk_used = _clamp(random.uniform(35, 70) + load_factor * 10, 0, 98)
    net_in = _clamp(_gaussian_noise(net_base * 0.6, 0.12), 0, node.bandwidth_mbps)
    net_out = _clamp(_gaussian_noise(net_base * 0.4, 0.12), 0, node.bandwidth_mbps)
    latency = _clamp(_gaussian_noise(2.0 + load_factor * 3, 0.20), 0.1, 999)
    pkt_loss = _clamp(np.random.exponential(0.01), 0, 5)
    connections = int(_clamp(_gaussian_noise(load_factor * 500, 0.10), 0, 65000))

    # ── Efectos de ataques activos ──────────────────────────
    attack = state.active_attacks.get(node.id)
    if attack:
        atype = attack.get("type", "")
        intensity = attack.get("intensity", 0.5)   # 0.0 - 1.0
        elapsed = attack.get("elapsed_sec", 0)
        ramp = min(1.0, elapsed / 30.0)            # 30s para escalar

        if atype in ("dos", "ddos", "syn_flood"):
            net_in   = _clamp(net_in   + node.bandwidth_mbps * intensity * ramp * 0.9, 0, node.bandwidth_mbps * 1.1)
            net_out  = _clamp(net_out  + node.bandwidth_mbps * 0.1 * ramp, 0, node.bandwidth_mbps)
            cpu      = _clamp(cpu      + 40 * intensity * ramp, 0, 100)
            latency  = _clamp(latency  + 500 * intensity * ramp, 0, 9999)
            pkt_loss = _clamp(pkt_loss + 30 * intensity * ramp, 0, 100)
            connections = int(_clamp(connections + 50000 * intensity * ramp, 0, 65535))

        elif atype == "brute_force":
            cpu      = _clamp(cpu + 15 * intensity, 0, 100)
            connections = int(_clamp(connections + 2000 * ramp, 0, 65535))

        elif atype == "port_scan":
            net_in   = _clamp(net_in + 50 * ramp, 0, node.bandwidth_mbps)
            connections = int(_clamp(connections + 5000 * ramp, 0, 65535))

        elif atype == "memory_leak":
            # RAM sube ~3% por minuto desde el inicio, mínimo garantizado 82% para que sea visible
            ram = _clamp(max(ram + 3 * elapsed / 60.0, 82.0), 0, 100)

        elif atype == "disk_failure":
            # Disk I/O supera umbral (>150) desde el inicio; ramp solo amplifica
            disk_io  = _clamp(disk_io + 160 + 200 * ramp * intensity, 0, 2000)
            pkt_loss = _clamp(pkt_loss + 5 * ramp, 0, 100)
            disk_used = _clamp(disk_used + 20 * ramp, 0, 100)

        elif atype == "thermal":
            cpu      = _clamp(cpu * (1 - 0.3 * ramp), 0, 100)  # throttling

    # Flags de ataque para el diagnóstico guiado
    smart_errors = 0
    access_alert = False
    if attack:
        atype = attack.get("type", "")
        if atype == "disk_failure":
            smart_errors = random.randint(5, 20)
        elif atype in ("unauthorized_access", "unauth_access"):
            access_alert = True

    # ── Overrides manuales del instructor ──────────────────
    overrides = state.node_overrides.get(node.id, {})
    if overrides:
        if "cpu_pct" in overrides:    cpu    = overrides["cpu_pct"]
        if "ram_pct" in overrides:    ram    = overrides["ram_pct"]
        if "net_in_mbps" in overrides: net_in = overrides["net_in_mbps"]

    return {
        "cpu_pct":         round(cpu, 2),
        "ram_pct":         round(ram, 2),
        "disk_io_mbps":    round(disk_io, 2),
        "disk_used_pct":   round(disk_used, 2),
        "net_in_mbps":     round(net_in, 2),
        "net_out_mbps":    round(net_out, 2),
        "latency_ms":      round(latency, 3),
        "packet_loss_pct": round(pkt_loss, 4),
        "connections":     connections,
        "smart_errors":    smart_errors,
        "access_alert":    access_alert,
        "is_online":       node.id not in state.offline_nodes,
        "uptime_pct":      99.9 if node.id not in state.offline_nodes else 0.0,
    }


# ============================================================
# GENERADOR DE MÉTRICAS SST
# ============================================================
def generate_sst_reading(sensor: SSTSensor) -> Dict[str, Any]:
    """Genera una lectura realista de sensor SST."""
    override = state.sst_overrides.get(sensor.id, {})

    if sensor.sensor_type == "temperature":
        base_temp = 22.0 + random.uniform(-1, 1)
        # Calor extra en horas pico
        hour = state.get_simulated_hour()
        base_temp += LOAD_PATTERN.get(hour, 0.5) * 3
        temp = override.get("temperature_c", _gaussian_noise(base_temp, 0.02))
        temp = _clamp(temp, 10, 60)
        level = "normal"
        if temp >= sensor.critical_threshold: level = "critical"
        elif temp >= sensor.warning_threshold: level = "warning"
        return {
            "temperature_c": round(temp, 2),
            "alert_level": level
        }

    elif sensor.sensor_type == "humidity":
        hum = override.get("humidity_pct", _gaussian_noise(50.0, 0.05))
        hum = _clamp(hum, 20, 90)
        level = "normal"
        if hum >= sensor.critical_threshold or hum <= 30: level = "critical"
        elif hum >= sensor.warning_threshold or hum <= 35: level = "warning"
        return {
            "humidity_pct": round(hum, 2),
            "alert_level": level
        }

    elif sensor.sensor_type == "smoke":
        smoke_ppm = override.get("smoke_ppm", abs(np.random.exponential(0.5)))
        smoke_ppm = _clamp(smoke_ppm, 0, 100)
        detected = smoke_ppm > sensor.warning_threshold
        level = "normal"
        if smoke_ppm >= sensor.critical_threshold: level = "critical"
        elif smoke_ppm >= sensor.warning_threshold: level = "warning"
        return {
            "smoke_ppm": round(smoke_ppm, 3),
            "smoke_detected": detected,
            "alert_level": level
        }

    elif sensor.sensor_type == "ups":
        battery = override.get("ups_battery_pct", _gaussian_noise(95.0, 0.01))
        battery = _clamp(battery, 0, 100)
        load = override.get("ups_load_pct", _gaussian_noise(45.0, 0.05))
        load = _clamp(load, 0, 100)
        level = "normal"
        if battery <= sensor.critical_threshold: level = "critical"
        elif battery <= sensor.warning_threshold: level = "warning"
        return {
            "ups_battery_pct": round(battery, 2),
            "ups_load_pct": round(load, 2),
            "alert_level": level
        }

    elif sensor.sensor_type == "power":
        hour = state.get_simulated_hour()
        base_kw = 80 + LOAD_PATTERN.get(hour, 0.5) * 70
        power = override.get("power_kw", _gaussian_noise(base_kw, 0.04))
        power = _clamp(power, 0, 250)
        it_load = power * 0.7
        pue = round(power / max(it_load, 1), 3) if it_load > 0 else 1.5
        level = "normal"
        if power >= sensor.critical_threshold: level = "critical"
        elif power >= sensor.warning_threshold: level = "warning"
        return {
            "power_kw": round(power, 2),
            "pue": pue,
            "alert_level": level
        }

    elif sensor.sensor_type == "access":
        event = override.get("access_event", None)
        unauthorized = override.get("unauthorized", False)
        if event is None:
            events = [None, None, None, None, None,  # sin evento (80%)
                      "CARD_OK:admin@dc.edu",
                      "CARD_OK:tech01@dc.edu"]
            event = random.choice(events)
        return {
            "access_event": event,
            "unauthorized": unauthorized,
            "alert_level": "critical" if unauthorized else "normal"
        }

    return {"alert_level": "normal"}


# ============================================================
# SNAPSHOT COMPLETO DEL DC
# ============================================================
def generate_full_snapshot() -> Dict[str, Any]:
    """Genera el estado completo de todos los nodos y sensores."""
    timestamp = datetime.utcnow().isoformat()

    nodes_data = {}
    for node_id, node in DC_NODES.items():
        metrics = generate_node_metrics(node)
        nodes_data[node_id] = {
            "id": node.id,
            "name": node.name,
            "type": node.node_type,
            "ip": node.ip,
            "zone": node.zone,
            "services": node.services,
            "metrics": metrics,
            "has_attack": node_id in state.active_attacks,
            "attack_type": state.active_attacks.get(node_id, {}).get("type"),
            "in_maintenance": node_id in state.maintenance_nodes,
        }

    sst_data = {}
    for sensor_id, sensor in SST_SENSORS.items():
        reading = generate_sst_reading(sensor)
        sst_data[sensor_id] = {
            "id": sensor.id,
            "name": sensor.name,
            "type": sensor.sensor_type,
            "zone": sensor.zone,
            "unit": sensor.unit,
            **reading
        }

    # Resumen de estado del DC
    online_count = sum(1 for n in DC_NODES if n not in state.offline_nodes)
    attack_count = len(state.active_attacks)
    critical_sst = sum(1 for s in sst_data.values() if s.get("alert_level") == "critical")

    return {
        "timestamp": timestamp,
        "nodes": nodes_data,
        "sst": sst_data,
        "summary": {
            "total_nodes": len(DC_NODES),
            "online_nodes": online_count,
            "offline_nodes": len(state.offline_nodes),
            "active_attacks": attack_count,
            "critical_sst_alerts": critical_sst,
            "simulated_hour": state.get_simulated_hour(),
        }
    }


def tick_attacks():
    """Actualiza el tiempo transcurrido de ataques activos."""
    for node_id in list(state.active_attacks.keys()):
        state.active_attacks[node_id]["elapsed_sec"] = \
            state.active_attacks[node_id].get("elapsed_sec", 0) + 2
        # Auto-resolver ataques después de su duración máxima
        max_dur = state.active_attacks[node_id].get("max_duration_sec", 300)
        if state.active_attacks[node_id]["elapsed_sec"] >= max_dur:
            del state.active_attacks[node_id]
