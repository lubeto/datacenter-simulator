"""
DC Monitoring Simulator - Motor de Mitigacion Automatica
Reglas inteligentes de contramedida por tipo de ataque.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any


# ── REGLAS DE MITIGACION POR TIPO DE ATAQUE ──────────────────────────────────
MITIGATION_RULES: Dict[str, Dict] = {
    "dos": {
        "name": "Mitigacion DoS",
        "steps": [
            {"action": "rate_limit",      "desc": "Aplicar rate limiting: max 100 req/s en FW-01",          "command": "iptables -A INPUT -p tcp --dport 80 -m limit --limit 100/s -j ACCEPT"},
            {"action": "blacklist_ip",    "desc": "Bloquear IP origen en firewall perimetral",              "command": "fail2ban-client set sshd banip <ATTACKER_IP>"},
            {"action": "cdn_shield",      "desc": "Activar proteccion CDN / scrubbing center",              "command": "cloudflare-cli enable-under-attack-mode"},
            {"action": "load_balance",    "desc": "Redistribuir trafico hacia nodo de respaldo",            "command": "haproxy -f /etc/haproxy/haproxy.cfg -sf $(cat /var/run/haproxy.pid)"},
        ],
        "auto_actions": ["rate_limit"],
        "expected_recovery_sec": 120,
        "severity_impact": "high",
    },
    "ddos": {
        "name": "Mitigacion DDoS",
        "steps": [
            {"action": "anycast_routing",  "desc": "Activar enrutamiento anycast para absorber trafico",   "command": "bgp-anycast enable --prefix 10.0.0.0/24"},
            {"action": "scrubbing",        "desc": "Redirigir trafico a centro de scrubbing",               "command": "scrubbing-center redirect --target <NODE_IP>"},
            {"action": "geo_block",        "desc": "Bloquear rangos geograficos sospechosos",               "command": "ipset create geoblock hash:net && ipset add geoblock <CIDR>"},
            {"action": "upstream_filter",  "desc": "Solicitar filtrado en ISP upstream",                    "command": "noc-ticket create --type ddos-mitigation --node <NODE_ID>"},
        ],
        "auto_actions": ["anycast_routing", "scrubbing"],
        "expected_recovery_sec": 300,
        "severity_impact": "critical",
    },
    "syn_flood": {
        "name": "Mitigacion SYN Flood",
        "steps": [
            {"action": "syn_cookies",     "desc": "Habilitar SYN cookies en kernel",                        "command": "sysctl -w net.ipv4.tcp_syncookies=1"},
            {"action": "syn_backlog",     "desc": "Aumentar cola de backlog TCP",                           "command": "sysctl -w net.ipv4.tcp_max_syn_backlog=2048"},
            {"action": "iptables_limit",  "desc": "Limitar nuevas conexiones SYN por minuto",              "command": "iptables -A INPUT -p tcp --syn -m limit --limit 50/m --limit-burst 100 -j ACCEPT"},
            {"action": "rst_flood",       "desc": "Enviar RST a conexiones a medio establecer",             "command": "hping3 --rst -p 80 -a <SOURCE_IP>"},
        ],
        "auto_actions": ["syn_cookies", "syn_backlog"],
        "expected_recovery_sec": 90,
        "severity_impact": "high",
    },
    "brute_force": {
        "name": "Mitigacion Brute Force SSH",
        "steps": [
            {"action": "fail2ban",        "desc": "Activar fail2ban: banear IP tras 5 intentos",            "command": "fail2ban-client start sshd"},
            {"action": "change_port",     "desc": "Cambiar puerto SSH de 22 a puerto no estandar",          "command": "sed -i 's/Port 22/Port 2222/' /etc/ssh/sshd_config && systemctl restart sshd"},
            {"action": "key_only",        "desc": "Deshabilitar autenticacion por password en SSH",         "command": "sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config"},
            {"action": "2fa",             "desc": "Habilitar autenticacion de dos factores",                "command": "apt install libpam-google-authenticator && auth required pam_google_authenticator.so"},
        ],
        "auto_actions": ["fail2ban"],
        "expected_recovery_sec": 60,
        "severity_impact": "medium",
    },
    "port_scan": {
        "name": "Mitigacion Port Scan",
        "steps": [
            {"action": "psad_enable",     "desc": "Activar PSAD para deteccion de port scanning",          "command": "psad --Status && systemctl enable psad"},
            {"action": "port_knocking",   "desc": "Implementar port knocking para servicios criticos",      "command": "knockd -c /etc/knockd.conf -i eth0"},
            {"action": "stealth_mode",    "desc": "Configurar firewall en modo stealth (DROP vs REJECT)",   "command": "iptables -P INPUT DROP && iptables -P FORWARD DROP"},
            {"action": "honeypot",        "desc": "Redirigir scanner a honeypot para analisis",             "command": "honeytrap -c /etc/honeytrap/honeytrap.conf start"},
        ],
        "auto_actions": ["psad_enable", "stealth_mode"],
        "expected_recovery_sec": 45,
        "severity_impact": "low",
    },
    "arp_spoofing": {
        "name": "Mitigacion ARP Spoofing",
        "steps": [
            {"action": "arp_static",      "desc": "Agregar entradas ARP estaticas para gateways criticos",  "command": "arp -s 10.0.0.1 aa:bb:cc:dd:ee:ff"},
            {"action": "dynamic_arp",     "desc": "Habilitar Dynamic ARP Inspection en switch",             "command": "vlan 10 ip arp inspection"},
            {"action": "arpwatch",        "desc": "Activar arpwatch para monitoreo continuo",               "command": "systemctl start arpwatch"},
            {"action": "vlan_segment",    "desc": "Segmentar VLANs para aislar el segmento afectado",       "command": "vlan-isolate --segment <VLAN_ID>"},
        ],
        "auto_actions": ["arp_static", "arpwatch"],
        "expected_recovery_sec": 60,
        "severity_impact": "high",
    },
    "memory_leak": {
        "name": "Mitigacion Memory Leak",
        "steps": [
            {"action": "process_restart", "desc": "Reiniciar proceso con memory leak de forma controlada",  "command": "systemctl restart <SERVICE_NAME>"},
            {"action": "oom_config",      "desc": "Configurar OOM killer con prioridad adecuada",           "command": "echo 500 > /proc/<PID>/oom_score_adj"},
            {"action": "swap_expand",     "desc": "Expandir swap temporalmente",                            "command": "fallocate -l 4G /swapfile && mkswap /swapfile && swapon /swapfile"},
            {"action": "mem_limit",       "desc": "Aplicar cgroup memory limit al proceso afectado",        "command": "systemd-run --scope -p MemoryLimit=2G -- <PROCESS>"},
        ],
        "auto_actions": ["oom_config"],
        "expected_recovery_sec": 180,
        "severity_impact": "high",
    },
    "disk_failure": {
        "name": "Mitigacion Falla de Disco",
        "steps": [
            {"action": "raid_rebuild",    "desc": "Iniciar reconstruccion RAID desde disco de respaldo",    "command": "mdadm --manage /dev/md0 --add /dev/sdc"},
            {"action": "snapshot_mount",  "desc": "Montar snapshot LVM como respaldo inmediato",            "command": "lvcreate -L10G -s -n snap /dev/vg0/lv0"},
            {"action": "disk_check",      "desc": "Ejecutar fsck en modo solo lectura",                     "command": "fsck -n /dev/sdb"},
            {"action": "replication",     "desc": "Activar replicacion a nodo secundario",                  "command": "rsync -avz --delete /data/ backup-server:/data/"},
        ],
        "auto_actions": ["snapshot_mount"],
        "expected_recovery_sec": 600,
        "severity_impact": "critical",
    },
    "thermal": {
        "name": "Mitigacion Sobrecalentamiento",
        "steps": [
            {"action": "cpu_throttle",    "desc": "Aplicar throttling de CPU para reducir temperatura",    "command": "cpupower frequency-set -g powersave"},
            {"action": "workload_migrate","desc": "Migrar workloads a nodos con temperatura normal",         "command": "virsh migrate --live <VM_ID> qemu+ssh://coolnode/system"},
            {"action": "crac_increase",   "desc": "Aumentar capacidad de enfriamiento CRAC urgente",        "command": "crac-controller set-cooling-level 100"},
            {"action": "graceful_shutdown","desc": "Apagado graceful si temperatura > 85C",                 "command": "shutdown -h now # EMERGENCIA TERMICA"},
        ],
        "auto_actions": ["cpu_throttle"],
        "expected_recovery_sec": 300,
        "severity_impact": "critical",
    },
    "power_failure": {
        "name": "Mitigacion Falla Electrica",
        "steps": [
            {"action": "ups_activate",    "desc": "Verificar estado UPS y autonomia disponible",            "command": "upsc ups@localhost battery.charge"},
            {"action": "load_shed",       "desc": "Apagar sistemas no criticos para extender autonomia",    "command": "pdu-control --off non-critical-outlets"},
            {"action": "generator_start", "desc": "Arrancar generador de emergencia",                       "command": "generator-control start --auto-transfer"},
            {"action": "graceful_save",   "desc": "Guardar estado y hacer checkpoint de VMs criticas",      "command": "virsh list | awk '{print $2}' | xargs -I{} virsh save {} {}.checkpoint"},
        ],
        "auto_actions": ["ups_activate", "load_shed"],
        "expected_recovery_sec": 120,
        "severity_impact": "critical",
    },
    "smoke_alert": {
        "name": "Protocolo de Alerta de Humo",
        "steps": [
            {"action": "fire_suppression","desc": "Activar sistema de supresion de incendios (CO2/FM200)", "command": "fire-panel activate-zone <ZONE_ID>"},
            {"action": "evacuate",        "desc": "Activar protocolo de evacuacion del personal",           "command": "building-control evacuate-zone <ZONE_ID>"},
            {"action": "emergency_shutdown","desc": "Apagado de emergencia de equipos en zona afectada",   "command": "pdu emergency-shutoff --zone <ZONE_ID>"},
            {"action": "notify_brigade",  "desc": "Notificar a brigada de emergencia y bomberos",           "command": "alert-system notify --type fire --zone <ZONE_ID>"},
        ],
        "auto_actions": ["fire_suppression", "evacuate"],
        "expected_recovery_sec": 1800,
        "severity_impact": "critical",
    },
    "unauthorized_access": {
        "name": "Mitigacion Acceso No Autorizado",
        "steps": [
            {"action": "revoke_access",   "desc": "Revocar credenciales y sesiones activas inmediatamente", "command": "pkill -u <USERNAME> && passwd -l <USERNAME>"},
            {"action": "isolate_segment", "desc": "Aislar segmento de red comprometido",                    "command": "iptables -I INPUT -s <COMPROMISED_SUBNET> -j DROP"},
            {"action": "audit_log",       "desc": "Capturar logs de auditoria completos para forensics",    "command": "ausearch -ua <USERNAME> --start today | aureport"},
            {"action": "notify_soc",      "desc": "Escalar a SOC y generar ticket de seguridad",            "command": "soc-ticket create --severity critical --type unauthorized-access"},
        ],
        "auto_actions": ["isolate_segment"],
        "expected_recovery_sec": 900,
        "severity_impact": "critical",
    },
    "ssl_expired": {
        "name": "Renovacion SSL Expirado",
        "steps": [
            {"action": "lets_encrypt",    "desc": "Renovar certificado con Let's Encrypt (certbot)",        "command": "certbot renew --force-renewal --nginx"},
            {"action": "temp_cert",       "desc": "Instalar certificado temporal self-signed de emergencia","command": "openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 30 -nodes"},
            {"action": "reload_nginx",    "desc": "Recargar configuracion de Nginx sin downtime",           "command": "nginx -t && systemctl reload nginx"},
            {"action": "monitor_expiry",  "desc": "Configurar alerta de expiracion con 30 dias de anticipo","command": "certbot renew --deploy-hook 'systemctl reload nginx' >> /etc/cron.d/certbot"},
        ],
        "auto_actions": ["lets_encrypt", "reload_nginx"],
        "expected_recovery_sec": 30,
        "severity_impact": "high",
    },
    "ssl_expiring_soon": {
        "name": "Renovacion SSL Preventiva",
        "steps": [
            {"action": "schedule_renew",  "desc": "Programar renovacion automatica de certificado",         "command": "certbot renew --deploy-hook 'systemctl reload nginx'"},
            {"action": "test_renewal",    "desc": "Probar proceso de renovacion en ambiente de staging",    "command": "certbot renew --dry-run"},
            {"action": "calendar_alert",  "desc": "Crear alerta en calendario 15 dias antes de expiracion", "command": "crontab -e # 0 9 <DAY> <MONTH> * certbot renew"},
        ],
        "auto_actions": ["schedule_renew"],
        "expected_recovery_sec": 0,
        "severity_impact": "low",
    },
    # ── Seguridad Física Avanzada ─────────────────────────────
    "biometric_bypass": {
        "name": "Mitigacion Violacion Biometrica",
        "steps": [
            {"action": "lock_reader",     "desc": "Bloquear lector biométrico comprometido de forma remota",  "command": "access-control disable-reader --id <READER_ID>"},
            {"action": "revoke_template", "desc": "Revocar template biométrico del usuario afectado",         "command": "biometric-mgr revoke --uid <USER_ID> --type fingerprint"},
            {"action": "cctv_review",     "desc": "Revisar grabación CCTV de las últimas 2 horas",            "command": "cctv-review --zone <ZONE_ID> --from -2h --to now"},
            {"action": "audit_access",    "desc": "Auditar todos los accesos del lector en las últimas 72h",  "command": "access-log query --reader <READER_ID> --hours 72"},
        ],
        "auto_actions": ["lock_reader"],
        "expected_recovery_sec": 900,
        "severity_impact": "critical",
    },
    "tailgating": {
        "name": "Mitigacion Tailgating",
        "steps": [
            {"action": "mantrap_lock",    "desc": "Activar bloqueo de mantrap entre puertas de acceso",       "command": "access-control mantrap-lockdown --zone <ZONE_ID>"},
            {"action": "cctv_review",     "desc": "Identificar a la persona no autorizada en CCTV",           "command": "cctv-review --zone <ZONE_ID> --from -1h --to now"},
            {"action": "employee_alert",  "desc": "Notificar al empleado que generó el acceso",               "command": "notify-employee --id <EMPLOYEE_ID> --type tailgating-incident"},
            {"action": "patrol_increase", "desc": "Incrementar frecuencia de patrullaje físico",               "command": "security-dispatch patrol --zone <ZONE_ID> --frequency 15min"},
        ],
        "auto_actions": ["mantrap_lock"],
        "expected_recovery_sec": 600,
        "severity_impact": "critical",
    },
    "badge_cloning": {
        "name": "Mitigacion Clonacion RFID",
        "steps": [
            {"action": "revoke_badge",    "desc": "Revocar UID de la tarjeta comprometida inmediatamente",    "command": "access-control revoke-badge --uid <BADGE_UID>"},
            {"action": "access_audit",    "desc": "Revisar todos los accesos con esa tarjeta en 72 horas",    "command": "access-log query --badge <BADGE_UID> --hours 72"},
            {"action": "issue_new_badge", "desc": "Emitir nueva tarjeta con UID diferente al empleado",       "command": "badge-mgr issue-new --employee <EMPLOYEE_ID> --type encrypted"},
            {"action": "reader_audit",    "desc": "Verificar lectores RFID en busca de skimmers físicos",     "command": "security-dispatch inspect-readers --all"},
        ],
        "auto_actions": ["revoke_badge"],
        "expected_recovery_sec": 1200,
        "severity_impact": "critical",
    },
    "cctv_tampering": {
        "name": "Mitigacion Sabotaje CCTV",
        "steps": [
            {"action": "backup_cam",      "desc": "Activar cámara de respaldo en zona afectada",              "command": "cctv-mgr activate-backup --zone <ZONE_ID>"},
            {"action": "physical_check",  "desc": "Enviar seguridad a verificar cámara físicamente",          "command": "security-dispatch check-camera --id <CAM_ID>"},
            {"action": "access_cross",    "desc": "Cruzar logs de acceso con la ventana sin cobertura visual", "command": "access-log query --zone <ZONE_ID> --from <TAMPER_START>"},
            {"action": "maintenance",     "desc": "Generar ticket urgente de reparación de cámara",            "command": "helpdesk ticket create --priority critical --type cctv-repair"},
        ],
        "auto_actions": ["backup_cam"],
        "expected_recovery_sec": 3600,
        "severity_impact": "high",
    },

    # ── Daños de Red Interna ──────────────────────────────────
    "vlan_hopping": {
        "name": "Mitigacion VLAN Hopping",
        "steps": [
            {"action": "disable_dtp",     "desc": "Deshabilitar DTP en puertos de acceso para evitar trunk auto", "command": "switchport nonegotiate && switchport mode access"},
            {"action": "native_vlan",     "desc": "Cambiar VLAN nativa a VLAN sin uso (999)",                 "command": "switchport trunk native vlan 999"},
            {"action": "vlan_prune",      "desc": "Aplicar pruning de VLANs en todos los trunks",             "command": "switchport trunk allowed vlan <ONLY_REQUIRED_VLANS>"},
            {"action": "audit_trunks",    "desc": "Auditar configuración de trunking en todos los switches",   "command": "show interfaces trunk | grep -v inactive"},
        ],
        "auto_actions": ["disable_dtp", "native_vlan"],
        "expected_recovery_sec": 120,
        "severity_impact": "critical",
    },
    "rogue_dhcp": {
        "name": "Mitigacion Servidor DHCP Falso",
        "steps": [
            {"action": "dhcp_snooping",   "desc": "Activar DHCP Snooping en switches: bloquear OFFER no confiables", "command": "ip dhcp snooping && ip dhcp snooping vlan <VLAN_ID>"},
            {"action": "port_shutdown",   "desc": "Apagar el puerto donde se detectó el servidor DHCP falso", "command": "interface <PORT_ID> && shutdown"},
            {"action": "renew_ips",       "desc": "Forzar renovación de IPs en todos los clientes afectados", "command": "dhcp-helper broadcast --type DHCPRELEASE --vlan <VLAN_ID>"},
            {"action": "identify_device", "desc": "Identificar dispositivo no autorizado por MAC address",    "command": "show mac address-table | grep <ROGUE_PORT>"},
        ],
        "auto_actions": ["dhcp_snooping", "port_shutdown"],
        "expected_recovery_sec": 180,
        "severity_impact": "critical",
    },
    "dns_spoofing": {
        "name": "Mitigacion DNS Spoofing",
        "steps": [
            {"action": "flush_cache",     "desc": "Limpiar caché DNS en todos los servidores afectados",      "command": "rndc flush && systemctl restart bind9"},
            {"action": "dnssec_enable",   "desc": "Habilitar DNSSEC para validación criptográfica",           "command": "dnssec-keygen -a NSEC3RSASHA1 -b 2048 -n ZONE <DOMAIN>"},
            {"action": "doh_enable",      "desc": "Configurar DNS sobre HTTPS para evitar interceptación",    "command": "nginx proxy_pass https://1.1.1.1/dns-query # DoH config"},
            {"action": "verify_dns",      "desc": "Verificar resoluciones con dig para detectar anomalías",   "command": "dig @<DNS_SERVER> <DOMAIN> +dnssec"},
        ],
        "auto_actions": ["flush_cache"],
        "expected_recovery_sec": 90,
        "severity_impact": "critical",
    },
    "spanning_tree_attack": {
        "name": "Mitigacion Ataque STP",
        "steps": [
            {"action": "bpdu_guard",      "desc": "Habilitar BPDU Guard en todos los puertos de acceso",      "command": "spanning-tree bpduguard enable"},
            {"action": "root_guard",      "desc": "Configurar Root Guard en puertos de uplink legítimos",     "command": "spanning-tree guard root"},
            {"action": "fix_root_bridge", "desc": "Forzar Root Bridge correcto con prioridad 0",              "command": "spanning-tree vlan <VLAN_ID> priority 0"},
            {"action": "audit_stp",       "desc": "Verificar topología STP actual en todos los switches",     "command": "show spanning-tree detail | grep Root"},
        ],
        "auto_actions": ["bpdu_guard", "root_guard"],
        "expected_recovery_sec": 60,
        "severity_impact": "critical",
    },

    # ── Amenaza Interna ───────────────────────────────────────
    "privilege_escalation": {
        "name": "Mitigacion Escalada de Privilegios",
        "steps": [
            {"action": "revoke_privs",    "desc": "Revocar privilegios elevados del usuario/proceso",         "command": "usermod -G users <USERNAME> && pkill -u <USERNAME>"},
            {"action": "audit_sudo",      "desc": "Auditar /etc/sudoers en busca de cambios no autorizados",  "command": "ausearch -k sudoers | aureport -f"},
            {"action": "find_suid",       "desc": "Buscar binarios SUID sospechosos en el sistema",           "command": "find / -perm -4000 -type f 2>/dev/null | grep -v /usr/bin"},
            {"action": "isolate_server",  "desc": "Aislar servidor si el compromiso fue exitoso",             "command": "iptables -I INPUT -j DROP && iptables -I OUTPUT -j DROP"},
        ],
        "auto_actions": ["revoke_privs", "audit_sudo"],
        "expected_recovery_sec": 300,
        "severity_impact": "critical",
    },
    "data_exfiltration": {
        "name": "Mitigacion Exfiltracion de Datos",
        "steps": [
            {"action": "block_ip",        "desc": "Bloquear IP destino de exfiltración en firewall",          "command": "iptables -A OUTPUT -d <EXFIL_IP> -j DROP"},
            {"action": "kill_process",    "desc": "Terminar proceso generando transferencia no autorizada",   "command": "netstat -tulnp | grep <EXFIL_IP> # identificar PID, luego kill -9"},
            {"action": "capture_traffic", "desc": "Capturar tráfico para evidencia forense",                  "command": "tcpdump -i eth0 -w /tmp/evidencia_$(date +%Y%m%d_%H%M).pcap host <EXFIL_IP>"},
            {"action": "db_audit",        "desc": "Auditar qué datos fueron accedidos en las últimas 24h",    "command": "mysql -e \"SELECT * FROM general_log WHERE event_time > NOW()-INTERVAL 24 HOUR\""},
        ],
        "auto_actions": ["block_ip", "capture_traffic"],
        "expected_recovery_sec": 1800,
        "severity_impact": "critical",
    },

    "tls_downgrade": {
        "name": "Mitigacion TLS Downgrade",
        "steps": [
            {"action": "force_tls12",     "desc": "Forzar TLS 1.2+ y deshabilitar TLS 1.0/1.1",            "command": "nginx: ssl_protocols TLSv1.2 TLSv1.3; # en /etc/nginx/nginx.conf"},
            {"action": "hsts_enable",     "desc": "Habilitar HSTS con max-age de 1 ano",                    "command": "add_header Strict-Transport-Security 'max-age=31536000' always;"},
            {"action": "cipher_hardening","desc": "Actualizar cipher suite a configuracion moderna",        "command": "ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;"},
            {"action": "test_ssl",        "desc": "Verificar configuracion con SSL Labs (A+)",              "command": "sslyze --regular <DOMAIN>"},
        ],
        "auto_actions": ["force_tls12", "hsts_enable"],
        "expected_recovery_sec": 15,
        "severity_impact": "high",
    },
}


# ── ATTACK CHAINS (APT Simulation) ────────────────────────────────────────────
ATTACK_CHAINS: Dict[str, Dict] = {
    "apt_web": {
        "name": "APT - Compromiso Web (Fase multiple)",
        "description": "Ataque en fases: reconocimiento → explotacion → persistencia",
        "phases": [
            {"delay_sec": 0,   "attack_type": "port_scan",         "node": "FW-01",   "intensity": 0.4, "desc": "Fase 1: Reconocimiento de puertos"},
            {"delay_sec": 30,  "attack_type": "brute_force",       "node": "WEB-01",  "intensity": 0.6, "desc": "Fase 2: Fuerza bruta SSH"},
            {"delay_sec": 90,  "attack_type": "unauthorized_access","node": "WEB-01", "intensity": 0.8, "desc": "Fase 3: Acceso no autorizado"},
            {"delay_sec": 150, "attack_type": "dos",               "node": "WEB-02",  "intensity": 0.9, "desc": "Fase 4: DoS como distraccion"},
        ],
        "total_duration_sec": 300,
    },
    "apt_data_exfil": {
        "name": "APT - Exfiltracion de Datos",
        "description": "Lateral movement hacia base de datos",
        "phases": [
            {"delay_sec": 0,   "attack_type": "arp_spoofing",      "node": "SW-CORE", "intensity": 0.5, "desc": "Fase 1: ARP Spoofing en red interna"},
            {"delay_sec": 45,  "attack_type": "brute_force",       "node": "DB-01",   "intensity": 0.7, "desc": "Fase 2: Brute force a base de datos"},
            {"delay_sec": 120, "attack_type": "memory_leak",       "node": "DB-01",   "intensity": 0.8, "desc": "Fase 3: Explotacion de servicio DB"},
        ],
        "total_duration_sec": 240,
    },
    "ransomware_sim": {
        "name": "Simulacion Ransomware",
        "description": "Propagacion lateral y cifrado de datos",
        "phases": [
            {"delay_sec": 0,   "attack_type": "brute_force",       "node": "APP-01",  "intensity": 0.6, "desc": "Fase 1: Compromiso inicial via phishing"},
            {"delay_sec": 60,  "attack_type": "memory_leak",       "node": "APP-01",  "intensity": 0.9, "desc": "Fase 2: Escalada de privilegios"},
            {"delay_sec": 90,  "attack_type": "disk_failure",      "node": "STORAGE-01","intensity": 1.0,"desc": "Fase 3: Cifrado masivo de datos"},
            {"delay_sec": 120, "attack_type": "ddos",              "node": "WEB-01",  "intensity": 0.8, "desc": "Fase 4: DDoS como extorsion"},
        ],
        "total_duration_sec": 360,
    },
    "infrastructure_takeover": {
        "name": "Toma de Infraestructura",
        "description": "Compromiso de red y nodos criticos",
        "phases": [
            {"delay_sec": 0,   "attack_type": "arp_spoofing",      "node": "SW-ACC-01","intensity": 0.5,"desc": "Fase 1: Man-in-the-middle en switch de acceso"},
            {"delay_sec": 30,  "attack_type": "tls_downgrade",     "node": "LB-01",   "intensity": 0.6, "desc": "Fase 2: Downgrade TLS en balanceador"},
            {"delay_sec": 75,  "attack_type": "unauthorized_access","node": "FW-01",  "intensity": 0.9, "desc": "Fase 3: Acceso al firewall perimetral"},
            {"delay_sec": 120, "attack_type": "ddos",              "node": "RTR-EDGE","intensity": 1.0, "desc": "Fase 4: Saturacion de router de borde"},
        ],
        "total_duration_sec": 300,
    },
}


# ── ESCALATION RULES ──────────────────────────────────────────────────────────
ESCALATION_CONFIG = {
    "warning_after_sec":    20,    # 20 seg sin detectar → Panel guiado abre (warning)
    "critical_after_sec":   45,    # 45 seg sin detectar → Panel guiado abre (critical)
    "auto_detect_after_sec": 120,  # 2 min → sistema detecta automaticamente (penalizacion)
    "score_penalty_pct":    25,    # % de penalizacion en score si el sistema detecta
}


class MitigationEngine:
    def __init__(self):
        self._active_suggestions: Dict[int, Dict] = {}  # incident_id → suggestion

    def get_mitigation_plan(self, attack_type: str, node_id: str) -> Optional[Dict]:
        """Obtiene el plan de mitigacion para un tipo de ataque."""
        rule = MITIGATION_RULES.get(attack_type)
        if not rule:
            return None
        return {
            "attack_type":          attack_type,
            "node_id":              node_id,
            "mitigation_name":      rule["name"],
            "steps":                rule["steps"],
            "auto_actions":         rule["auto_actions"],
            "expected_recovery_sec":rule["expected_recovery_sec"],
            "severity_impact":      rule["severity_impact"],
            "generated_at":         datetime.utcnow().isoformat(),
        }

    def get_auto_actions(self, attack_type: str) -> List[Dict]:
        """Retorna solo las acciones automaticas recomendadas."""
        rule = MITIGATION_RULES.get(attack_type, {})
        auto_ids = rule.get("auto_actions", [])
        steps = rule.get("steps", [])
        return [s for s in steps if s["action"] in auto_ids]

    def register_suggestion(self, incident_id: int, attack_type: str, node_id: str):
        """Registra una sugerencia activa para un incidente."""
        plan = self.get_mitigation_plan(attack_type, node_id)
        if plan:
            self._active_suggestions[incident_id] = plan

    def get_suggestion(self, incident_id: int) -> Optional[Dict]:
        return self._active_suggestions.get(incident_id)

    def clear_suggestion(self, incident_id: int):
        self._active_suggestions.pop(incident_id, None)

    def get_all_suggestions(self) -> Dict:
        return dict(self._active_suggestions)

    def calculate_score(self, mttd_sec: float, mttr_sec: float,
                        severity: str, auto_detected: bool = False) -> float:
        """Calcula score del estudiante basado en MTTD, MTTR y severidad."""
        severity_weights = {"critical": 1.5, "high": 1.2, "medium": 1.0, "low": 0.8, "warning": 0.9}
        w = severity_weights.get(severity, 1.0)

        # Score base 100 puntos
        # MTTD: 0s=50pts, 60s=40pts, 300s=10pts
        mttd_score = max(0, 50 - (mttd_sec / 10))
        # MTTR: 0s=50pts, 60s=40pts, 600s=5pts
        mttr_score = max(0, 50 - (mttr_sec / 20))

        score = (mttd_score + mttr_score) * w
        if auto_detected:
            score *= (1 - ESCALATION_CONFIG["score_penalty_pct"] / 100)

        return min(100.0, max(0.0, round(score, 1)))

    @staticmethod
    def get_available_chains() -> Dict:
        return {k: {
            "name":        v["name"],
            "description": v["description"],
            "phases":      len(v["phases"]),
            "total_duration_sec": v["total_duration_sec"],
        } for k, v in ATTACK_CHAINS.items()}

    @staticmethod
    def get_chain(chain_id: str) -> Optional[Dict]:
        return ATTACK_CHAINS.get(chain_id)

    @staticmethod
    def get_escalation_config() -> Dict:
        return ESCALATION_CONFIG


# Instancia global
mitigation_engine = MitigationEngine()
