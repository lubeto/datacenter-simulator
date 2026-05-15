"""
DC Monitoring Simulator - Definición de Nodos Virtuales
12 nodos que simulan la infraestructura de un centro de datos
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Node:
    id: str
    name: str
    node_type: str        # server, switch, router, firewall, storage, loadbalancer
    ip: str
    zone: str             # zona física en el DC
    os: Optional[str] = None
    services: List[str] = field(default_factory=list)
    # Capacidades base
    cpu_cores: int = 4
    ram_gb: int = 16
    disk_gb: int = 500
    bandwidth_mbps: int = 1000
    # Estado
    is_online: bool = True
    has_ssl: bool = False
    ssl_domain: Optional[str] = None


# ============================================================
# DEFINICIÓN DE LOS 12 NODOS DEL DC
# ============================================================
DC_NODES: Dict[str, Node] = {

    # --- SERVIDORES WEB ---
    "WEB-01": Node(
        id="WEB-01", name="Web Server 01",
        node_type="server", ip="10.0.1.10",
        zone="Rack-A", os="Ubuntu 22.04 LTS",
        services=["nginx", "php-fpm", "ssl"],
        cpu_cores=8, ram_gb=32, disk_gb=500,
        bandwidth_mbps=1000,
        has_ssl=True, ssl_domain="portal.datacenter.edu"
    ),
    "WEB-02": Node(
        id="WEB-02", name="Web Server 02",
        node_type="server", ip="10.0.1.11",
        zone="Rack-A", os="Ubuntu 22.04 LTS",
        services=["nginx", "php-fpm", "ssl"],
        cpu_cores=8, ram_gb=32, disk_gb=500,
        bandwidth_mbps=1000,
        has_ssl=True, ssl_domain="api.datacenter.edu"
    ),

    # --- SERVIDORES DE BASE DE DATOS ---
    "DB-01": Node(
        id="DB-01", name="Database Primary",
        node_type="server", ip="10.0.2.10",
        zone="Rack-B", os="CentOS 8",
        services=["postgresql", "pg_backup"],
        cpu_cores=16, ram_gb=64, disk_gb=2000,
        bandwidth_mbps=10000,
        has_ssl=True, ssl_domain="db-primary.datacenter.edu"
    ),
    "DB-02": Node(
        id="DB-02", name="Database Replica",
        node_type="server", ip="10.0.2.11",
        zone="Rack-B", os="CentOS 8",
        services=["postgresql", "replication"],
        cpu_cores=16, ram_gb=64, disk_gb=2000,
        bandwidth_mbps=10000
    ),

    # --- SERVIDORES DE APLICACIÓN ---
    "APP-01": Node(
        id="APP-01", name="App Server 01",
        node_type="server", ip="10.0.3.10",
        zone="Rack-C", os="Debian 12",
        services=["python", "fastapi", "redis", "ssl"],
        cpu_cores=12, ram_gb=48, disk_gb=1000,
        bandwidth_mbps=1000,
        has_ssl=True, ssl_domain="app01.datacenter.edu"
    ),
    "APP-02": Node(
        id="APP-02", name="App Server 02",
        node_type="server", ip="10.0.3.11",
        zone="Rack-C", os="Debian 12",
        services=["python", "fastapi", "redis"],
        cpu_cores=12, ram_gb=48, disk_gb=1000,
        bandwidth_mbps=1000
    ),

    # --- INFRAESTRUCTURA DE RED ---
    "LB-01": Node(
        id="LB-01", name="Load Balancer",
        node_type="loadbalancer", ip="10.0.0.5",
        zone="Rack-DMZ", os="HAProxy",
        services=["haproxy", "keepalived", "ssl"],
        cpu_cores=4, ram_gb=8, disk_gb=100,
        bandwidth_mbps=10000,
        has_ssl=True, ssl_domain="www.datacenter.edu"
    ),
    "FW-01": Node(
        id="FW-01", name="Firewall Principal",
        node_type="firewall", ip="10.0.0.1",
        zone="Rack-DMZ",
        services=["pf", "ids", "vpn"],
        cpu_cores=4, ram_gb=8, disk_gb=100,
        bandwidth_mbps=10000
    ),
    "RTR-EDGE": Node(
        id="RTR-EDGE", name="Router Edge",
        node_type="router", ip="192.168.1.1",
        zone="Rack-DMZ",
        services=["bgp", "ospf", "nat"],
        cpu_cores=2, ram_gb=4, disk_gb=50,
        bandwidth_mbps=10000
    ),
    "SW-CORE": Node(
        id="SW-CORE", name="Switch Core",
        node_type="switch", ip="10.0.0.2",
        zone="Rack-Core",
        services=["vlan", "stp", "lacp"],
        bandwidth_mbps=40000
    ),
    "SW-ACC-01": Node(
        id="SW-ACC-01", name="Switch Acceso 01",
        node_type="switch", ip="10.0.0.3",
        zone="Rack-A",
        services=["vlan", "poe"],
        bandwidth_mbps=10000
    ),

    # --- ALMACENAMIENTO ---
    "STORAGE-01": Node(
        id="STORAGE-01", name="SAN Storage",
        node_type="storage", ip="10.0.4.10",
        zone="Rack-D",
        services=["iscsi", "nfs", "raid6"],
        cpu_cores=4, ram_gb=16, disk_gb=20000,
        bandwidth_mbps=10000
    ),
}


# ============================================================
# SENSORES SST (Salud y Seguridad en el Trabajo)
# ============================================================
@dataclass
class SSTSensor:
    id: str
    sensor_type: str   # temperature, humidity, smoke, ups, access, power
    zone: str
    name: str
    # Umbrales normales
    normal_min: float = 0.0
    normal_max: float = 100.0
    warning_threshold: float = 80.0
    critical_threshold: float = 90.0
    unit: str = ""


SST_SENSORS: Dict[str, SSTSensor] = {
    # Temperatura por zona
    "TEMP-RACK-A":   SSTSensor("TEMP-RACK-A",   "temperature", "Rack-A",   "Sensor Temp Rack A",   18.0, 27.0, 28.0, 35.0, "°C"),
    "TEMP-RACK-B":   SSTSensor("TEMP-RACK-B",   "temperature", "Rack-B",   "Sensor Temp Rack B",   18.0, 27.0, 28.0, 35.0, "°C"),
    "TEMP-RACK-C":   SSTSensor("TEMP-RACK-C",   "temperature", "Rack-C",   "Sensor Temp Rack C",   18.0, 27.0, 28.0, 35.0, "°C"),
    "TEMP-RACK-D":   SSTSensor("TEMP-RACK-D",   "temperature", "Rack-D",   "Sensor Temp Rack D",   18.0, 27.0, 28.0, 35.0, "°C"),
    "TEMP-PASILLO":  SSTSensor("TEMP-PASILLO",  "temperature", "Pasillo",  "Sensor Pasillo Frío",  16.0, 24.0, 26.0, 32.0, "°C"),

    # Humedad relativa
    "HUM-SALA":      SSTSensor("HUM-SALA",      "humidity",    "Sala",     "Humedad Sala Serv.",   40.0, 60.0, 65.0, 75.0, "%"),

    # Humo / Incendio
    "SMOKE-RACK-AB": SSTSensor("SMOKE-RACK-AB", "smoke",       "Rack-A/B", "Detector Humo AB",     0.0,  5.0,  10.0, 25.0, "ppm"),
    "SMOKE-RACK-CD": SSTSensor("SMOKE-RACK-CD", "smoke",       "Rack-C/D", "Detector Humo CD",     0.0,  5.0,  10.0, 25.0, "ppm"),

    # UPS / Energía
    "UPS-MAIN":      SSTSensor("UPS-MAIN",      "ups",         "UPS-Room", "UPS Principal",        80.0, 100.0, 50.0, 20.0, "%"),
    "UPS-BACKUP":    SSTSensor("UPS-BACKUP",     "ups",         "UPS-Room", "UPS Respaldo",         80.0, 100.0, 50.0, 20.0, "%"),
    "PWR-MAIN":      SSTSensor("PWR-MAIN",       "power",       "PDU",      "Consumo Energético",   0.0, 150.0, 170.0, 200.0, "kW"),

    # Control de acceso
    "ACCESS-MAIN":   SSTSensor("ACCESS-MAIN",   "access",      "Entrada",  "Control Acceso Ppal.", 0.0, 0.0, 0.0, 0.0, ""),
    "ACCESS-RACK":   SSTSensor("ACCESS-RACK",   "access",      "Rack-Room","Control Acceso Racks", 0.0, 0.0, 0.0, 0.0, ""),
}


def get_all_nodes() -> List[Node]:
    return list(DC_NODES.values())


def get_node(node_id: str) -> Optional[Node]:
    return DC_NODES.get(node_id)


def get_nodes_with_ssl() -> List[Node]:
    return [n for n in DC_NODES.values() if n.has_ssl]


def get_all_sensors() -> List[SSTSensor]:
    return list(SST_SENSORS.values())
