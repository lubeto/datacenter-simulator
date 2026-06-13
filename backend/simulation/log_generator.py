"""
DC Monitoring Simulator - Generador de Logs en Crudo
Genera líneas de log (access/auth/system) coherentes con el ataque activo.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List

from .nodes import DC_NODES, get_node
from .engine import state as sim_state

LOG_LEVELS = ["INFO", "WARN", "ERROR"]

NORMAL_PATHS = [
    "/", "/index.html", "/api/health", "/static/css/main.css",
    "/static/js/app.js", "/favicon.ico", "/api/v1/users/me",
    "/api/v1/products", "/img/logo.png",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/115.0",
]

NORMAL_USERS = ["admin", "jrodriguez", "mvasquez", "tech01", "deploy"]


def _node_ip(node_id: str) -> str:
    node = get_node(node_id)
    return node.ip if node else "10.0.1.10"


def _ts(offset_sec: int) -> str:
    t = datetime.utcnow() - timedelta(seconds=offset_sec)
    return t.strftime("%d/%b/%Y:%H:%M:%S +0000")


def _ts_syslog(offset_sec: int) -> str:
    t = datetime.utcnow() - timedelta(seconds=offset_sec)
    return t.strftime("%b %d %H:%M:%S")


# ============================================================
# ACCESS LOG (nginx)
# ============================================================
def _generate_access_log(node_id: str, n: int = 40) -> List[Dict]:
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")
    lines = []

    for i in range(n):
        offset = (n - i) * random.randint(1, 3)
        is_attack_line = atype in ("dos", "ddos", "syn_flood", "port_scan", "brute_force") and i >= n - 12

        if is_attack_line:
            if atype == "port_scan":
                ip = f"198.51.100.{random.randint(1,254)}"
                path = random.choice(["/admin", "/.env", "/wp-login.php", "/phpmyadmin", "/.git/config"])
                status = 404
            elif atype == "brute_force":
                ip = f"203.0.113.{random.randint(1,254)}"
                path = "/api/login"
                status = 401
            else:  # ddos / dos / syn_flood
                ip = f"203.0.113.{random.randint(1,254)}"
                path = "/"
                status = random.choice([200, 503, 503, 499])
            ua = "python-requests/2.28.0"
            severity = "warn"
        else:
            ip = f"10.0.{random.randint(1,5)}.{random.randint(2,250)}"
            path = random.choice(NORMAL_PATHS)
            status = random.choice([200, 200, 200, 200, 304, 404])
            ua = random.choice(USER_AGENTS)
            severity = "normal"

        size = random.randint(150, 25000)
        lines.append({
            "timestamp": _ts(offset),
            "raw": f'{ip} - - [{_ts(offset)}] "GET {path} HTTP/1.1" {status} {size} "-" "{ua}"',
            "severity": severity,
        })

    lines.sort(key=lambda l: l["timestamp"])
    return lines


# ============================================================
# AUTH LOG
# ============================================================
def _generate_auth_log(node_id: str, n: int = 40) -> List[Dict]:
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")
    lines = []

    for i in range(n):
        offset = (n - i) * random.randint(2, 6)
        pid = random.randint(1000, 9999)
        is_attack_line = atype == "brute_force" and i >= n - 15
        is_access_line = atype in ("unauthorized_access", "unauth_access") and i >= n - 5

        if is_attack_line:
            ip = "203.0.113.45"
            user = random.choice(["root", "admin", "test", "ubuntu", "oracle"])
            port = random.randint(40000, 60000)
            lines.append({
                "timestamp": _ts_syslog(offset),
                "raw": f"{_ts_syslog(offset)} {node_id.lower()} sshd[{pid}]: Failed password for {user} from {ip} port {port} ssh2",
                "severity": "crit",
            })
        elif is_access_line:
            lines.append({
                "timestamp": _ts_syslog(offset),
                "raw": f"{_ts_syslog(offset)} {node_id.lower()} PAM[{pid}]: unauthorized access attempt — badge denied at RACK-A door",
                "severity": "crit",
            })
        else:
            user = random.choice(NORMAL_USERS)
            ip = f"10.0.{random.randint(1,5)}.{random.randint(2,250)}"
            event = random.choice([
                f"Accepted publickey for {user} from {ip} port {random.randint(40000,60000)} ssh2",
                f"pam_unix(sudo:session): session opened for user {user}",
                f"CRON[{pid}]: (root) CMD (/usr/bin/check_health.sh)",
            ])
            lines.append({
                "timestamp": _ts_syslog(offset),
                "raw": f"{_ts_syslog(offset)} {node_id.lower()} {event}",
                "severity": "normal",
            })

    lines.sort(key=lambda l: l["timestamp"])
    return lines


# ============================================================
# SYSTEM LOG (kernel/systemd)
# ============================================================
SYSTEM_NORMAL = [
    "systemd[1]: Started Daily apt download activities.",
    "systemd[1]: Started Daily apt upgrade and clean activities.",
    "kernel: [{t}] eth0: link is up",
    "systemd-resolved[812]: Server returned error NXDOMAIN, mitigating potential DNS violation",
    "NetworkManager[920]: <info> device (eth0): link connected",
]

SYSTEM_ATTACK = {
    "dos": "kernel: [{t}] possible SYN flooding on port 443. Sending cookies. Check SNMP counters.",
    "ddos": "kernel: [{t}] possible SYN flooding on port 443. Sending cookies. Check SNMP counters.",
    "syn_flood": "kernel: [{t}] possible SYN flooding on port 443. Sending cookies. Check SNMP counters.",
    "brute_force": "sshd[{pid}]: error: maximum authentication attempts exceeded for root from 203.0.113.45",
    "port_scan": "kernel: [{t}] nf_conntrack: table full, dropping packet",
    "memory_leak": "kernel: [{t}] Out of memory: Killed process {pid} (leaky_app) total-vm:2048000kB",
    "disk_failure": "kernel: [{t}] sd 2:0:0:0: [sda] tag#{pid} FAILED Result: hostbyte=DID_OK driverbyte=DRIVER_SENSE",
    "thermal": "kernel: [{t}] CPU0: Core temperature above threshold, cpu clock throttled",
    "unauthorized_access": "PAM[{pid}]: unauthorized access attempt detected on door RACK-A",
    "unauth_access": "PAM[{pid}]: unauthorized access attempt detected on door RACK-A",
}


def _generate_system_log(node_id: str, n: int = 40) -> List[Dict]:
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")
    lines = []

    for i in range(n):
        offset = (n - i) * random.randint(2, 8)
        pid = random.randint(1000, 9999)
        t = _ts_syslog(offset)
        is_attack_line = atype in SYSTEM_ATTACK and i >= n - 8

        if is_attack_line:
            msg = SYSTEM_ATTACK[atype].format(t=t, pid=pid)
            severity = "crit"
        else:
            msg = random.choice(SYSTEM_NORMAL).format(t=t)
            severity = "normal"

        lines.append({
            "timestamp": t,
            "raw": f"{t} {node_id.lower()} {msg}",
            "severity": severity,
        })

    lines.sort(key=lambda l: l["timestamp"])
    return lines


def generate_logs(log_type: str, node_id: str, n: int = 40) -> List[Dict]:
    """Genera n líneas de log del tipo solicitado para el nodo dado."""
    if node_id not in DC_NODES:
        node_id = "WEB-01"

    if log_type == "access":
        return _generate_access_log(node_id, n)
    elif log_type == "auth":
        return _generate_auth_log(node_id, n)
    else:  # "system"
        return _generate_system_log(node_id, n)
