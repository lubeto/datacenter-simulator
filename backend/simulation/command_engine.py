"""
DC Monitoring Simulator - Motor de Terminal Simulada
Parsea comandos tipo shell y genera output dinámico coherente con sim_state.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List

from .nodes import DC_NODES, get_node
from .engine import state as sim_state

# Reglas de firewall por estudiante (en memoria)
_iptables_rules: Dict[int, List[str]] = {}

DEFAULT_IPTABLES = [
    "Chain INPUT (policy ACCEPT)",
    "target     prot opt source               destination",
    "ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:80",
    "ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:443",
    "ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:22",
]

SERVICES_BY_TYPE = {
    "server": ["nginx", "sshd", "cron", "php-fpm"],
    "loadbalancer": ["haproxy", "keepalived"],
    "firewall": ["pf", "ids"],
    "router": ["bgpd", "ospfd"],
    "switch": ["snmpd"],
    "storage": ["iscsid", "nfsd"],
}

PROC_NAMES = {
    "server": ["nginx: master process", "php-fpm: pool www", "sshd", "cron", "systemd-journald"],
    "loadbalancer": ["haproxy", "keepalived"],
    "firewall": ["pfctl", "ids-engine"],
    "router": ["bgpd", "ospfd"],
    "switch": ["snmpd"],
    "storage": ["iscsid", "nfsd", "raidmonitor"],
}

ATTACK_PROCESS = {
    "dos": "flood.sh",
    "ddos": "flood.sh",
    "syn_flood": "synflooder",
    "brute_force": "hydra",
    "port_scan": "nmap",
    "memory_leak": "leaky_app",
    "disk_failure": None,
    "thermal": None,
    "unauthorized_access": "backdoor.sh",
    "unauth_access": "backdoor.sh",
}

SYSLOG_TEMPLATES = [
    "kernel: [{t}] eth0: link is up",
    "systemd[1]: Started Daily apt download activities.",
    "CRON[{pid}]: (root) CMD (/usr/bin/check_health.sh)",
    "sshd[{pid}]: Accepted publickey for admin from 10.0.0.{ip}",
]

ATTACK_SYSLOG = {
    "dos": "kernel: [{t}] possible SYN flood on eth0. Sending cookies.",
    "ddos": "kernel: [{t}] possible SYN flood on eth0. Sending cookies.",
    "syn_flood": "kernel: [{t}] possible SYN flood on eth0. Sending cookies.",
    "brute_force": "sshd[{pid}]: Failed password for root from 203.0.113.45 port {port} ssh2",
    "port_scan": "kernel: [{t}] nf_conntrack: table full, dropping packet",
    "memory_leak": "kernel: [{t}] Out of memory: Killed process {pid} (leaky_app)",
    "disk_failure": "kernel: [{t}] sd 2:0:0:0: [sda] tag#{pid} FAILED Result: hostbyte=DID_OK driverbyte=DRIVER_SENSE",
    "thermal": "kernel: [{t}] CPU0: Core temperature above threshold, cpu clock throttled",
    "unauthorized_access": "PAM[{pid}]: unauthorized access attempt detected on door RACK-A",
    "unauth_access": "PAM[{pid}]: unauthorized access attempt detected on door RACK-A",
}

HELP_TEXT = """Comandos disponibles:
  netstat -an              lista conexiones de red
  ps aux                   lista procesos
  ping <node_id>           prueba conectividad a un nodo
  iptables -L              lista reglas de firewall
  iptables -A INPUT ...    agrega una regla
  tail -f /var/log/syslog   últimas líneas del log de sistema
  systemctl status <svc>   estado de un servicio
  systemctl restart <svc>  reinicia un servicio
  df -h                    uso de disco
  free -m                  uso de memoria
  tcpdump -i eth0          captura de paquetes
  help                     muestra esta ayuda
  clear                    limpia la pantalla"""


def _get_node(node_id: str):
    node = get_node(node_id)
    if node is None:
        node = get_node("WEB-01")
        node_id = "WEB-01"
    return node_id, node


def _node_metrics(node_id: str):
    from .engine import generate_node_metrics
    node = get_node(node_id)
    return generate_node_metrics(node)


def _cmd_netstat(node_id: str) -> str:
    metrics = _node_metrics(node_id)
    conns = metrics["connections"]
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")

    lines = ["Proto Recv-Q Send-Q Local Address           Foreign Address         State"]
    n_lines = min(conns, 25)
    for i in range(n_lines):
        if atype in ("dos", "ddos", "syn_flood") and i < n_lines - 3:
            foreign = f"203.0.113.{random.randint(1,254)}:{random.randint(1024,65000)}"
            local_state = "SYN_RECV"
        elif atype == "brute_force" and i < n_lines - 3:
            foreign = f"198.51.100.{random.randint(1,254)}:{random.randint(1024,65000)}"
            local_state = "ESTABLISHED"
        else:
            foreign = f"10.0.{random.randint(1,5)}.{random.randint(2,250)}:{random.randint(1024,65000)}"
            local_state = "ESTABLISHED"
        port = 443 if i % 2 == 0 else 80
        lines.append(f"tcp        0      0 {DC_NODES[node_id].ip}:{port}".ljust(46) + f"{foreign}".ljust(24) + local_state)

    lines.append("")
    lines.append(f"Total de conexiones activas: {conns}")
    if atype in ("dos", "ddos", "syn_flood"):
        lines.append(f"⚠ {conns} conexiones es anormalmente alto (umbral normal < 500)")
    if atype == "brute_force":
        lines.append("⚠ múltiples intentos ESTABLISHED desde la misma subred 198.51.100.0/24")
    return "\n".join(lines)


def _cmd_ps(node_id: str) -> str:
    node = DC_NODES[node_id]
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")
    metrics = _node_metrics(node_id)

    lines = ["USER       PID  %CPU %MEM    VSZ   RSS COMMAND"]
    procs = PROC_NAMES.get(node.node_type, PROC_NAMES["server"])
    pid = 1000
    for proc in procs:
        cpu = round(random.uniform(0.1, 4.0), 1)
        mem = round(random.uniform(0.5, 5.0), 1)
        lines.append(f"root      {pid:<5} {cpu:<5} {mem:<5} 102400 20480 {proc}")
        pid += random.randint(5, 50)

    mal = ATTACK_PROCESS.get(atype)
    if mal:
        cpu = round(40 + metrics["cpu_pct"] * 0.4, 1)
        mem = round(metrics["ram_pct"] * 0.5, 1)
        lines.append(f"root      {pid:<5} {cpu:<5} {mem:<5} 204800 102400 {mal}  ⚠ PROCESO SOSPECHOSO")

    return "\n".join(lines)


def _cmd_ping(target: str) -> str:
    target_id, node = _get_node(target)
    metrics = _node_metrics(target_id)

    if not metrics["is_online"]:
        return (
            f"PING {node.ip} ({target_id}): 56 data bytes\n"
            f"Request timeout for icmp_seq 0\n"
            f"Request timeout for icmp_seq 1\n"
            f"Request timeout for icmp_seq 2\n\n"
            f"--- {target_id} ping statistics ---\n"
            f"3 packets transmitted, 0 received, 100% packet loss"
        )

    lat = metrics["latency_ms"]
    loss = metrics["packet_loss_pct"]
    lines = [f"PING {node.ip} ({target_id}): 56 data bytes"]
    received = 0
    for seq in range(4):
        if random.random() * 100 < loss:
            lines.append(f"Request timeout for icmp_seq {seq}")
        else:
            t = round(max(0.1, random.gauss(lat, lat * 0.1)), 3)
            lines.append(f"64 bytes from {node.ip}: icmp_seq={seq} ttl=64 time={t} ms")
            received += 1
    lines.append("")
    lines.append(f"--- {target_id} ping statistics ---")
    pct = round((4 - received) / 4 * 100, 1)
    lines.append(f"4 packets transmitted, {received} received, {pct}% packet loss")
    if lat > 200:
        lines.append(f"⚠ latencia elevada ({lat} ms) — posible saturación de red")
    return "\n".join(lines)


def _cmd_iptables(args: List[str], student_id: int) -> str:
    rules = _iptables_rules.setdefault(student_id, list(DEFAULT_IPTABLES))

    if not args or args[0] == "-L":
        return "\n".join(rules)

    if args[0] == "-A" and len(args) >= 2:
        rule_str = " ".join(args)
        if "DROP" in args and "-s" in args:
            ip = args[args.index("-s") + 1]
            rules.append(f"DROP       all  --  {ip}".ljust(30) + "0.0.0.0/0            ")
            return f"Regla agregada: bloquear tráfico desde {ip}\n✅ iptables actualizado"
        rules.append(rule_str)
        return f"Regla agregada: {rule_str}"

    if args[0] == "-F":
        _iptables_rules[student_id] = []
        return "Todas las reglas eliminadas (flush)"

    return f"iptables: opción no soportada: {' '.join(args)}"


def _cmd_syslog(node_id: str) -> str:
    now = datetime.utcnow()
    lines = []
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")

    for i in range(8):
        t = (now - timedelta(seconds=(8 - i) * random.randint(1, 5))).strftime("%b %d %H:%M:%S")
        if atype in ATTACK_SYSLOG and i >= 4:
            template = ATTACK_SYSLOG[atype]
        else:
            template = random.choice(SYSLOG_TEMPLATES)
        msg = template.format(t=t, pid=random.randint(1000, 9999), ip=random.randint(2, 250), port=random.randint(40000, 60000))
        lines.append(f"{t} {node_id.lower()} {msg}")
    return "\n".join(lines)


def _cmd_systemctl(args: List[str], node_id: str) -> str:
    node = DC_NODES[node_id]
    services = SERVICES_BY_TYPE.get(node.node_type, SERVICES_BY_TYPE["server"])

    if not args:
        return "Uso: systemctl status|restart <servicio>"

    action = args[0]
    svc = args[1] if len(args) > 1 else (services[0] if services else "nginx")

    if action == "status":
        attack = sim_state.active_attacks.get(node_id, {})
        is_down = node_id in sim_state.offline_nodes
        active = "inactive (dead)" if is_down else "active (running)"
        color = "⚫" if is_down else "🟢"
        return (
            f"● {svc}.service - {svc.capitalize()} Service\n"
            f"   Loaded: loaded (/lib/systemd/system/{svc}.service; enabled)\n"
            f"   Active: {active} {color}\n"
            f"   Main PID: {random.randint(1000, 9999)} ({svc})"
        )

    if action == "restart":
        if node_id in sim_state.offline_nodes:
            return f"⚠ no se puede reiniciar {svc}: el nodo {node_id} está fuera de línea"
        return f"✅ {svc}.service reiniciado correctamente"

    return f"systemctl: acción no soportada: {action}"


def _cmd_df(node_id: str) -> str:
    metrics = _node_metrics(node_id)
    node = DC_NODES[node_id]
    used_pct = metrics["disk_used_pct"]
    total_gb = node.disk_gb
    used_gb = round(total_gb * used_pct / 100)
    avail_gb = total_gb - used_gb
    lines = [
        "Filesystem      Size  Used Avail Use% Mounted on",
        f"/dev/sda1       {total_gb}G  {used_gb}G  {avail_gb}G  {round(used_pct)}% /",
    ]
    if used_pct > 90:
        lines.append("⚠ uso de disco crítico (>90%)")
    return "\n".join(lines)


def _cmd_free(node_id: str) -> str:
    metrics = _node_metrics(node_id)
    node = DC_NODES[node_id]
    total_mb = node.ram_gb * 1024
    used_mb = round(total_mb * metrics["ram_pct"] / 100)
    free_mb = total_mb - used_mb
    lines = [
        "              total        used        free      shared  buff/cache",
        f"Mem:        {total_mb:>8} {used_mb:>11} {free_mb:>11} {0:>11} {round(total_mb*0.05):>11}",
        f"Swap:       {2048:>8} {round(2048*0.02):>11} {round(2048*0.98):>11}",
    ]
    if metrics["ram_pct"] > 85:
        lines.append("⚠ uso de memoria crítico (>85%) — posible memory leak")
    return "\n".join(lines)


def _cmd_tcpdump(node_id: str) -> str:
    metrics = _node_metrics(node_id)
    attack = sim_state.active_attacks.get(node_id, {})
    atype = attack.get("type", "")
    node = DC_NODES[node_id]

    lines = [f"tcpdump: listening on eth0, link-type EN10MB (Ethernet), capture size 262144 bytes"]
    now = datetime.utcnow()
    n = 12 if atype in ("dos", "ddos", "syn_flood", "port_scan") else 6
    for i in range(n):
        t = (now - timedelta(milliseconds=(n - i) * random.randint(1, 50))).strftime("%H:%M:%S.%f")[:-3]
        if atype in ("dos", "ddos", "syn_flood"):
            src = f"203.0.113.{random.randint(1,254)}"
            lines.append(f"{t} IP {src}.{random.randint(1024,65000)} > {node.ip}.443: Flags [S], seq {random.randint(10**8,10**9)}, win 65535, length 0")
        elif atype == "port_scan":
            src = f"198.51.100.{random.randint(1,254)}"
            lines.append(f"{t} IP {src}.{random.randint(1024,65000)} > {node.ip}.{random.randint(1,1024)}: Flags [S], seq {random.randint(10**8,10**9)}, win 1024, length 0")
        else:
            src = f"10.0.{random.randint(1,5)}.{random.randint(2,250)}"
            lines.append(f"{t} IP {src}.{random.randint(1024,65000)} > {node.ip}.443: Flags [P.], seq {random.randint(10**8,10**9)}, ack {random.randint(10**8,10**9)}, win 502, length 64")

    if atype in ("dos", "ddos", "syn_flood", "port_scan"):
        lines.append("")
        lines.append("⚠ patrón anómalo detectado: alto volumen de paquetes SYN desde una sola subred")
    return "\n".join(lines)


def execute_command(raw: str, node_id: str = "WEB-01", student_id: int = 0) -> str:
    """Parsea y ejecuta un comando de terminal, retorna el output como texto."""
    raw = raw.strip()
    if not raw:
        return ""

    parts = raw.split()
    cmd = parts[0]
    args = parts[1:]

    node_id, _ = _get_node(node_id)

    if cmd == "help":
        return HELP_TEXT

    if cmd == "clear":
        return "\x1b[2J\x1b[H"

    if cmd == "netstat":
        return _cmd_netstat(node_id)

    if cmd == "ps":
        return _cmd_ps(node_id)

    if cmd == "ping":
        if not args:
            return "Uso: ping <node_id>"
        return _cmd_ping(args[0].upper())

    if cmd == "iptables":
        return _cmd_iptables(args, student_id)

    if cmd == "tail":
        return _cmd_syslog(node_id)

    if cmd == "systemctl":
        return _cmd_systemctl(args, node_id)

    if cmd == "df":
        return _cmd_df(node_id)

    if cmd == "free":
        return _cmd_free(node_id)

    if cmd == "tcpdump":
        return _cmd_tcpdump(node_id)

    if cmd == "ls":
        return "bin  boot  etc  home  lib  proc  root  tmp  usr  var"

    if cmd in ("whoami",):
        return "root"

    if cmd in ("hostname",):
        return node_id.lower()

    return f"{cmd}: comando no encontrado. Escribe 'help' para ver los comandos disponibles."
