"""
DC Monitoring Simulator - Motor de Ataques y Fallos
Simula: DoS, DDoS, SYN Flood, Brute Force, Port Scan, ARP Spoofing,
        Memory Leak, Disk Failure, Thermal Event, Power Failure, SSL/TLS Issues
"""
import random
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List

from .engine import state as sim_state
from .nodes import DC_NODES, SST_SENSORS


# ============================================================
# CATÁLOGO DE ATAQUES Y FALLOS
# ============================================================
ATTACK_CATALOG = {
    # ── Ataques de Red ──────────────────────────────────────
    "dos": {
        "name": "Ataque DoS",
        "category": "attack",
        "description": "Inundación de paquetes desde una sola IP. Satura el ancho de banda del nodo objetivo.",
        "severity": "critical",
        "target_types": ["server", "loadbalancer", "firewall", "router"],
        "default_duration_sec": 240,
        "indicators": ["net_in_mbps > 800", "latency_ms > 200", "packet_loss_pct > 10"],
        "mitigation_steps": [
            "Identificar IP origen en logs del firewall",
            "Aplicar ACL para bloquear IP atacante",
            "Activar rate limiting en FW-01",
            "Notificar al ISP si el ataque es externo",
            "Monitorear durante 15 min post-bloqueo",
        ]
    },
    "ddos": {
        "name": "Ataque DDoS Distribuido",
        "category": "attack",
        "description": "Ataque coordinado desde múltiples IPs. Alta volumetría, difícil de bloquear por IP.",
        "severity": "critical",
        "target_types": ["server", "loadbalancer", "firewall", "router"],
        "default_duration_sec": 360,
        "indicators": ["net_in_mbps > 900", "connections > 50000", "packet_loss_pct > 25"],
        "mitigation_steps": [
            "Activar scrubbing center / CDN DDoS protection",
            "Implementar blackhole routing (RTBH)",
            "Distribuir carga entre múltiples servidores",
            "Contactar al proveedor de upstream",
            "Activar modo de degradación controlada",
        ]
    },
    "syn_flood": {
        "name": "SYN Flood",
        "category": "attack",
        "description": "Explotación del handshake TCP. Agota la tabla de conexiones semi-abiertas.",
        "severity": "critical",
        "target_types": ["server", "loadbalancer", "firewall"],
        "default_duration_sec": 180,
        "indicators": ["connections > 60000", "cpu_pct > 85", "latency_ms > 300"],
        "mitigation_steps": [
            "Habilitar SYN Cookies en el kernel",
            "Reducir timeout de conexiones TCP",
            "Implementar SYN proxy en el firewall",
            "Filtrar por geolocalización si aplica",
        ]
    },
    "brute_force": {
        "name": "Brute Force SSH",
        "category": "attack",
        "description": "Intentos masivos de autenticación SSH desde IP externa.",
        "severity": "warning",
        "target_types": ["server"],
        "default_duration_sec": 300,
        "indicators": ["auth_failures > 100/min", "connections > +200"],
        "mitigation_steps": [
            "Bloquear IP atacante con fail2ban",
            "Cambiar puerto SSH a no estándar",
            "Deshabilitar login por contraseña (usar solo llaves)",
            "Revisar /var/log/auth.log para IPs adicionales",
            "Verificar que ningún usuario fue comprometido",
        ]
    },
    "port_scan": {
        "name": "Escaneo de Puertos",
        "category": "attack",
        "description": "Reconocimiento activo. Un atacante mapea los servicios expuestos.",
        "severity": "warning",
        "target_types": ["server", "firewall", "router"],
        "default_duration_sec": 120,
        "indicators": ["net_in_mbps spike", "connections desde 1 IP a múltiples puertos"],
        "mitigation_steps": [
            "Identificar IP origen en logs",
            "Bloquear IP en firewall perimetral",
            "Revisar qué puertos fueron escaneados",
            "Verificar que no hay puertos innecesarios abiertos",
            "Documentar el incidente de reconocimiento",
        ]
    },
    "arp_spoofing": {
        "name": "ARP Spoofing / MITM",
        "category": "attack",
        "description": "Envenenamiento de caché ARP. El atacante redirige tráfico de red.",
        "severity": "critical",
        "target_types": ["switch", "server"],
        "default_duration_sec": 200,
        "indicators": ["tablas ARP inconsistentes", "latency aumenta", "SSL warnings"],
        "mitigation_steps": [
            "Activar Dynamic ARP Inspection en switches",
            "Implementar ARP estático para IPs críticas",
            "Aislar el segmento de red afectado",
            "Identificar MAC address del atacante",
            "Revisar integridad de tráfico SSL",
        ]
    },

    # ── Fallos de Hardware ──────────────────────────────────
    "disk_failure": {
        "name": "Falla de Disco RAID",
        "category": "hardware",
        "description": "Disco del array RAID reporta errores SMART. Degradación progresiva.",
        "severity": "critical",
        "target_types": ["server", "storage"],
        "default_duration_sec": 600,
        "indicators": ["disk_io_mbps > 400", "SMART errors", "I/O wait spike"],
        "mitigation_steps": [
            "Verificar estado RAID: mdadm --detail /dev/md0",
            "Identificar disco fallando con smartctl -a /dev/sdX",
            "Iniciar reconstrucción RAID con disco de repuesto",
            "Crear snapshot de datos críticos",
            "Ordenar disco de reemplazo urgente",
        ]
    },
    "memory_leak": {
        "name": "Memory Leak (Fuga de Memoria)",
        "category": "hardware",
        "description": "Proceso con fuga de memoria. RAM se agota progresivamente (+2% /min).",
        "severity": "warning",
        "target_types": ["server"],
        "default_duration_sec": 480,
        "indicators": ["ram_pct sube progresivamente", "swap activo", "OOM killer"],
        "mitigation_steps": [
            "Identificar proceso con 'top' o 'htop'",
            "Verificar consumo: ps aux --sort=-%mem | head",
            "Reiniciar el servicio afectado",
            "Aplicar parche o actualizar el proceso",
            "Implementar watchdog para reinicio automático",
        ]
    },

    # ── Fallos SST ──────────────────────────────────────────
    "thermal": {
        "name": "Sobrecalentamiento",
        "category": "sst",
        "description": "Falla de unidad CRAC. Temperatura sube 0.5°C/min. CPUs hacen throttling.",
        "severity": "critical",
        "target_types": ["server"],
        "default_duration_sec": 720,
        "indicators": ["temp > 28°C", "CPU throttling", "fan speed máx"],
        "mitigation_steps": [
            "Verificar estado de unidades CRAC/CRAH",
            "Activar enfriamiento de emergencia",
            "Migrar cargas críticas a otros racks",
            "Apagar servidores no críticos",
            "Abrir puertas del pasillo frío si es necesario",
        ]
    },
    "power_failure": {
        "name": "Corte de Energía",
        "category": "sst",
        "description": "PDU principal falla. UPS entra en acción (duración: 15 min).",
        "severity": "critical",
        "target_types": [],  # afecta todo el DC
        "default_duration_sec": 300,
        "indicators": ["UPS activo", "baterías drenando", "generador no arranca"],
        "mitigation_steps": [
            "Verificar estado del UPS: apcupsd status",
            "Intentar activar generador de emergencia",
            "Apagar sistemas no críticos para conservar batería",
            "Notificar al proveedor eléctrico",
            "Activar plan de continuidad de negocio",
        ]
    },
    "smoke_alert": {
        "name": "Alerta de Humo / Incendio",
        "category": "sst",
        "description": "Sensor de humo detecta partículas. Posible inicio de incendio.",
        "severity": "critical",
        "target_types": [],
        "default_duration_sec": 180,
        "indicators": ["smoke_ppm > 10", "detector activado", "temperatura en zona"],
        "mitigation_steps": [
            "Verificar zona con personal físicamente",
            "Activar sistema de supresión FM-200 si confirmado",
            "Evacuar personal del DC",
            "Llamar a bomberos si se confirma incendio",
            "Activar plan de evacuación y contingencia",
        ]
    },
    "unauthorized_access": {
        "name": "Acceso No Autorizado",
        "category": "sst",
        "description": "Intento de acceso físico sin credenciales válidas al DC.",
        "severity": "critical",
        "target_types": [],
        "default_duration_sec": 120,
        "indicators": ["ACCESS DENIED en zona restringida", "badge inválido"],
        "mitigation_steps": [
            "Revisar cámara CCTV del punto de acceso",
            "Bloquear la tarjeta de acceso reportada",
            "Notificar a seguridad física",
            "Revisar logs de acceso de las últimas 24h",
            "Presentar reporte a RRHH si es empleado",
        ]
    },

    # ── Seguridad Física Avanzada ───────────────────────────
    "biometric_bypass": {
        "name": "Violación de Biometría",
        "category": "sst",
        "description": "Huella dactilar o retina clonada. Acceso físico a zona restringida con credencial biométrica falsificada.",
        "severity": "critical",
        "target_types": [],
        "default_duration_sec": 180,
        "indicators": ["ACCESS GRANTED con biometría sospechosa", "hora inusual de acceso", "badge + biometría no coinciden"],
        "mitigation_steps": [
            "Bloquear inmediatamente el lector biométrico comprometido",
            "Revisar grabación CCTV de la zona en las últimas 2 horas",
            "Revocar template biométrico del usuario afectado",
            "Verificar integridad del lector (posible skimmer)",
            "Emitir alerta a seguridad física y escalar a RRHH",
            "Auditar logs de acceso de los últimos 30 días del punto comprometido",
        ]
    },
    "tailgating": {
        "name": "Tailgating (Seguimiento no autorizado)",
        "category": "sst",
        "description": "Persona no autorizada accede al datacenter siguiendo a un empleado legítimo sin registrar entrada propia.",
        "severity": "critical",
        "target_types": [],
        "default_duration_sec": 240,
        "indicators": ["sensor de doble entrada activado", "CCTV muestra 2 personas en 1 acceso", "badge sin contrapartida de salida"],
        "mitigation_steps": [
            "Activar bloqueo de mantrap (cámara de seguridad entre puertas)",
            "Verificar CCTV e identificar a la persona no autorizada",
            "Contactar al empleado que generó el acceso para entrevista",
            "Registrar el incidente en el sistema de control de acceso",
            "Reforzar capacitación: ningún visitante sin escolta",
            "Instalar sensor de antipassback si no existe",
        ]
    },
    "badge_cloning": {
        "name": "Clonación de Tarjeta RFID",
        "category": "sst",
        "description": "Tarjeta de acceso RFID duplicada ilegalmente. Acceso físico con credencial válida pero de persona no autorizada.",
        "severity": "critical",
        "target_types": [],
        "default_duration_sec": 300,
        "indicators": ["badge activo en dos ubicaciones simultáneas", "acceso en horario no habitual", "reporte de tarjeta robada"],
        "mitigation_steps": [
            "Revocar inmediatamente el UID de la tarjeta comprometida",
            "Emitir nueva tarjeta con UID diferente al empleado afectado",
            "Revisar todos los accesos realizados con esa tarjeta en 72h",
            "Verificar si hay lectores RFID con anomalías (skimmers)",
            "Migrar a tecnología RFID cifrada si se usan tarjetas antiguas",
            "Reportar a seguridad y evaluar reposición de sistema de acceso",
        ]
    },
    "cctv_tampering": {
        "name": "Sabotaje de Cámaras CCTV",
        "category": "sst",
        "description": "Cámara de seguridad bloqueada, girada o desconectada. Punto ciego en monitoreo físico del datacenter.",
        "severity": "warning",
        "target_types": [],
        "default_duration_sec": 600,
        "indicators": ["señal de cámara perdida", "imagen congelada", "cámara girada sin registro de mantenimiento"],
        "mitigation_steps": [
            "Verificar estado de la cámara afectada físicamente",
            "Activar cámara de respaldo si existe en la zona",
            "Revisar logs de acceso a la zona sin cobertura visual",
            "Incrementar patrullaje físico mientras se restaura la cámara",
            "Investigar si el sabotaje fue intencional (cruzar con logs de acceso)",
            "Generar ticket de mantenimiento urgente para reparación",
        ]
    },

    # ── Daños de Red Interna ────────────────────────────────
    "vlan_hopping": {
        "name": "VLAN Hopping (Salto de VLAN)",
        "category": "attack",
        "description": "Atacante interno explota trunking 802.1Q para saltar entre VLANs sin autorización. Rompe la segmentación de red.",
        "severity": "critical",
        "target_types": ["switch"],
        "default_duration_sec": 300,
        "indicators": ["tráfico entre VLANs sin gateway", "doble encapsulación 802.1Q detectada", "VLAN nativa sin cifrar"],
        "mitigation_steps": [
            "Deshabilitar trunking automático (DTP) en puertos de acceso",
            "Cambiar VLAN nativa a una VLAN sin uso (ej. VLAN 999)",
            "Activar VLAN pruning para eliminar VLANs no necesarias en trunks",
            "Implementar Private VLANs en segmentos sensibles",
            "Auditar configuración de todos los switches con 'show interfaces trunk'",
        ]
    },
    "rogue_dhcp": {
        "name": "Servidor DHCP Falso",
        "category": "attack",
        "description": "Servidor DHCP no autorizado en red interna asigna IPs falsas y redirige tráfico. Permite MITM masivo.",
        "severity": "critical",
        "target_types": ["switch", "server"],
        "default_duration_sec": 420,
        "indicators": ["clientes con IPs inesperadas", "gateway incorrecto asignado", "múltiples DHCP OFFER en red"],
        "mitigation_steps": [
            "Activar DHCP Snooping en todos los switches: 'ip dhcp snooping'",
            "Identificar y apagar el puerto del servidor DHCP falso",
            "Marcar solo los puertos con DHCP legítimo como 'trusted'",
            "Renovar IPs de todos los clientes afectados: 'ipconfig /renew'",
            "Revisar quién conectó el dispositivo no autorizado (CCTV + logs)",
        ]
    },
    "dns_spoofing": {
        "name": "DNS Spoofing (Envenenamiento DNS)",
        "category": "attack",
        "description": "Caché DNS envenenada. Usuarios son redirigidos a sitios maliciosos aunque escriban la URL correcta.",
        "severity": "critical",
        "target_types": ["server"],
        "default_duration_sec": 360,
        "indicators": ["resoluciones DNS inconsistentes", "certificado SSL no coincide con dominio", "usuarios reportan redirecciones"],
        "mitigation_steps": [
            "Limpiar caché DNS en todos los servidores: 'rndc flush'",
            "Habilitar DNSSEC para validación criptográfica de respuestas",
            "Configurar DNS sobre HTTPS (DoH) o DNS sobre TLS (DoT)",
            "Verificar integridad del archivo /etc/hosts en servidores",
            "Monitorear respuestas DNS con 'dig' para detectar anomalías",
        ]
    },
    "spanning_tree_attack": {
        "name": "Ataque STP (Spanning Tree)",
        "category": "attack",
        "description": "Atacante inyecta BPDUs falsos para convertirse en Root Bridge. Genera bucles de red o desvía todo el tráfico.",
        "severity": "critical",
        "target_types": ["switch"],
        "default_duration_sec": 480,
        "indicators": ["root bridge cambia inesperadamente", "bucles de red activos", "tráfico interrumpido en segmento"],
        "mitigation_steps": [
            "Habilitar BPDU Guard en puertos de acceso: 'spanning-tree bpduguard enable'",
            "Configurar Root Guard en puertos de uplink legítimos",
            "Definir manualmente el Root Bridge con prioridad baja (0)",
            "Activar PortFast solo en puertos de end-devices",
            "Monitorear topología STP con 'show spanning-tree detail'",
        ]
    },

    # ── Amenaza Interna (Insider Threat) ────────────────────
    "privilege_escalation": {
        "name": "Escalada de Privilegios",
        "category": "attack",
        "description": "Usuario o proceso obtiene permisos de administrador/root sin autorización. Puede comprometer todo el sistema.",
        "severity": "critical",
        "target_types": ["server"],
        "default_duration_sec": 360,
        "indicators": ["sudo inusual en logs", "proceso no-root con UID=0", "cambios en /etc/sudoers", "setuid inesperado"],
        "mitigation_steps": [
            "Identificar proceso/usuario con 'ps aux' y 'id <user>'",
            "Revocar permisos inmediatamente: 'usermod -G <USER>' sin grupo admin",
            "Auditar /etc/sudoers y /etc/passwd en busca de cambios",
            "Buscar binarios con setuid sospechosos: 'find / -perm -4000'",
            "Revisar historial de comandos: /root/.bash_history",
            "Aislar el servidor si el compromiso fue exitoso",
        ]
    },
    "data_exfiltration": {
        "name": "Exfiltración de Datos",
        "category": "attack",
        "description": "Transferencia masiva de datos hacia destino externo no autorizado. Posible fuga de información confidencial.",
        "severity": "critical",
        "target_types": ["server", "storage"],
        "default_duration_sec": 600,
        "indicators": ["net_out_mbps alto sostenido", "conexiones a IPs externas inusuales", "acceso masivo a base de datos"],
        "mitigation_steps": [
            "Bloquear IP destino en firewall inmediatamente",
            "Identificar proceso generando el tráfico: 'netstat -tulnp'",
            "Terminar conexión sospechosa: 'kill -9 <PID>'",
            "Capturar tráfico para evidencia forense: 'tcpdump -w evidencia.pcap'",
            "Auditar qué datos fueron accedidos en las últimas 24h",
            "Notificar al DPO (oficial de protección de datos) según normativa",
        ]
    },

    # ── SSL / TLS ───────────────────────────────────────────
    "ssl_expired": {
        "name": "Certificado SSL Expirado",
        "category": "ssl",
        "description": "Certificado SSL/TLS venció. Los browsers muestran error de seguridad.",
        "severity": "critical",
        "target_types": ["server", "loadbalancer"],
        "default_duration_sec": 0,   # permanente hasta resolución
        "indicators": ["days_to_expire <= 0", "browser SSL error", "HTTPS down"],
        "mitigation_steps": [
            "Generar nuevo CSR para el dominio",
            "Adquirir o renovar certificado con la CA",
            "Instalar certificado en el servidor",
            "Reiniciar nginx/apache para aplicar",
            "Verificar con SSL Labs: ssllabs.com/ssltest",
        ]
    },
    "ssl_expiring_soon": {
        "name": "SSL Próximo a Vencer",
        "category": "ssl",
        "description": "Certificado vence en menos de 30 días. Requiere renovación urgente.",
        "severity": "warning",
        "target_types": ["server", "loadbalancer"],
        "default_duration_sec": 0,
        "indicators": ["days_to_expire < 30"],
        "mitigation_steps": [
            "Programar renovación del certificado",
            "Verificar proceso de renovación automática (Let's Encrypt)",
            "Notificar al equipo responsable",
        ]
    },
    "ssl_tls_downgrade": {
        "name": "Downgrade de TLS",
        "category": "ssl",
        "description": "Atacante fuerza negociación a TLS 1.0. Comunicación vulnerable.",
        "severity": "critical",
        "target_types": ["server", "loadbalancer", "firewall"],
        "default_duration_sec": 300,
        "indicators": ["TLS 1.0 detectado", "POODLE/BEAST vulnerability"],
        "mitigation_steps": [
            "Deshabilitar TLS 1.0 y 1.1 en nginx/apache",
            "Forzar TLS 1.2 mínimo (idealmente 1.3)",
            "Revisar cipher suites configuradas",
            "Ejecutar audit SSL con testssl.sh",
            "Actualizar configuración de todos los servicios HTTPS",
        ]
    },
}


# ============================================================
# GESTOR DE ATAQUES ACTIVOS
# ============================================================
class AttackManager:
    """Gestiona el ciclo de vida de los ataques simulados."""

    def inject_attack(self, attack_type: str, node_id: str,
                      intensity: float = 0.7,
                      duration_sec: int = None,
                      auto: bool = False) -> Dict[str, Any]:
        """Inyecta un ataque sobre un nodo."""
        catalog = ATTACK_CATALOG.get(attack_type)
        if not catalog:
            return {"error": f"Tipo de ataque '{attack_type}' no encontrado"}

        _SST_GLOBAL = {"power_failure", "smoke_alert", "unauthorized_access",
                       "biometric_bypass", "tailgating", "badge_cloning", "cctv_tampering"}
        if node_id not in DC_NODES and attack_type not in _SST_GLOBAL:
            return {"error": f"Nodo '{node_id}' no existe"}

        duration = duration_sec or catalog["default_duration_sec"]

        # IP atacante única por incidente para que el aprendiz la identifique en logs/netstat
        _ATTACKER_RANGES = {
            "dos": "203.0.113", "ddos": "203.0.113", "syn_flood": "203.0.113",
            "brute_force": "198.51.100", "port_scan": "198.51.100",
            "unauthorized_access": "185.220.101", "unauth_access": "185.220.101",
            "ssl_tls_downgrade": "91.108.4", "tls_downgrade": "91.108.4",
        }
        base = _ATTACKER_RANGES.get(attack_type)
        attacker_ip = f"{base}.{random.randint(2, 254)}" if base else None

        attack_info = {
            "type": attack_type,
            "name": catalog["name"],
            "category": catalog["category"],
            "node_id": node_id,
            "severity": catalog["severity"],
            "intensity": _clamp(intensity, 0.1, 1.0),
            "started_at": datetime.utcnow().isoformat(),
            "elapsed_sec": 0,
            "max_duration_sec": duration,
            "auto_injected": auto,
            "mitigation_steps": catalog["mitigation_steps"],
            "indicators": catalog["indicators"],
            "description": catalog["description"],
            "attacker_ip": attacker_ip,
        }

        sim_state.active_attacks[node_id] = attack_info

        # Efectos especiales por tipo
        if attack_type == "thermal":
            self._apply_thermal_effect(node_id)
        elif attack_type == "power_failure":
            self._apply_power_failure()
        elif attack_type == "smoke_alert":
            self._apply_smoke_alert()
        elif attack_type == "unauthorized_access":
            sim_state.sst_overrides["ACCESS-MAIN"] = {
                "unauthorized": True,
                "access_event": "ACCESS_DENIED:badge_unknown"
            }

        return attack_info

    def resolve_attack(self, node_id: str) -> bool:
        """Elimina un ataque activo de un nodo."""
        if node_id in sim_state.active_attacks:
            attack_type = sim_state.active_attacks[node_id].get("type")
            del sim_state.active_attacks[node_id]
            # Limpiar efectos especiales
            if attack_type == "thermal":
                for sid in list(sim_state.sst_overrides):
                    if "TEMP" in sid:
                        del sim_state.sst_overrides[sid]
            elif attack_type == "power_failure":
                sim_state.sst_overrides.pop("UPS-MAIN", None)
                sim_state.sst_overrides.pop("PWR-MAIN", None)
            elif attack_type == "unauthorized_access":
                sim_state.sst_overrides.pop("ACCESS-MAIN", None)
            return True
        return False

    def set_node_offline(self, node_id: str):
        sim_state.offline_nodes.add(node_id)

    def set_node_online(self, node_id: str):
        sim_state.offline_nodes.discard(node_id)
        sim_state.active_attacks.pop(node_id, None)

    def get_active_attacks(self) -> List[Dict]:
        return list(sim_state.active_attacks.values())

    def _apply_thermal_effect(self, node_id: str):
        """Simula calor progresivo en la zona del nodo."""
        node = DC_NODES.get(node_id)
        if node:
            zone = node.zone
            # Buscar sensores de temperatura en esa zona
            for sid, sensor in SST_SENSORS.items():
                if "TEMP" in sid and sensor.zone == zone:
                    sim_state.sst_overrides[sid] = {"temperature_c": 32.0}

    def _apply_power_failure(self):
        sim_state.sst_overrides["UPS-MAIN"] = {
            "ups_battery_pct": 75.0,
            "ups_load_pct": 95.0,
        }
        sim_state.sst_overrides["PWR-MAIN"] = {"power_kw": 0.0}

    def _apply_smoke_alert(self):
        sim_state.sst_overrides["SMOKE-RACK-AB"] = {
            "smoke_ppm": 35.0,
            "smoke_detected": True
        }

    def get_random_attack_scenario(self) -> Optional[Dict]:
        """Genera un escenario de ataque aleatorio para práctica."""
        attack_types = list(ATTACK_CATALOG.keys())
        attack_type = random.choice(attack_types)
        catalog = ATTACK_CATALOG[attack_type]

        target_types = catalog.get("target_types", [])
        if target_types:
            candidates = [n for n in DC_NODES.values()
                         if n.node_type in target_types and n.id not in sim_state.offline_nodes]
        else:
            candidates = list(DC_NODES.values())

        if not candidates:
            return None

        node = random.choice(candidates)
        intensity = random.uniform(0.4, 0.9)

        return {
            "attack_type": attack_type,
            "node_id": node.id,
            "intensity": round(intensity, 2),
        }


def _clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


# Instancia global
attack_manager = AttackManager()
