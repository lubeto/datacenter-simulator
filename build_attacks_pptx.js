const PptxGenJS = require('/tmp/pptx-work/node_modules/pptxgenjs');
const pptx = new PptxGenJS();

const C = {
  bgTitle:   '0D1B2A',
  bgContent: '111827',
  card:      '1E293B',
  danger:    'EF4444',
  warning:   'F59E0B',
  ok:        '22C55E',
  info:      '3B82F6',
  text:      'F8FAFC',
  muted:     '94A3B8',
  border:    '334155',
};

pptx.layout = 'LAYOUT_WIDE';

function titleSlide(title, subtitle, extra) {
  const sl = pptx.addSlide();
  sl.background = { color: C.bgTitle };
  sl.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.15, h: 7.5, fill: { color: C.danger }, line: { color: C.danger } });
  sl.addText(title, { x: 0.4, y: 2.2, w: 12.5, h: 1.2, fontSize: 44, bold: true, color: C.text, fontFace: 'Calibri', align: 'left' });
  if (subtitle) sl.addText(subtitle, { x: 0.4, y: 3.5, w: 12, h: 0.6, fontSize: 22, color: C.muted, fontFace: 'Calibri', align: 'left' });
  if (extra) sl.addText(extra, { x: 0.4, y: 6.8, w: 12, h: 0.4, fontSize: 14, color: C.muted, fontFace: 'Calibri', align: 'left' });
  return sl;
}

function contentSlide(title, bgColor) {
  const sl = pptx.addSlide();
  sl.background = { color: bgColor || C.bgContent };
  sl.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.1, h: 7.5, fill: { color: C.info }, line: { color: C.info } });
  sl.addText(title, { x: 0.3, y: 0.25, w: 12.7, h: 0.7, fontSize: 28, bold: true, color: C.text, fontFace: 'Calibri', align: 'left' });
  sl.addShape(pptx.ShapeType.rect, { x: 0.3, y: 1.0, w: 12.7, h: 0.04, fill: { color: C.border }, line: { color: C.border } });
  return sl;
}

function addCard(sl, x, y, w, h, titleText, bodyLines, accentColor) {
  sl.addShape(pptx.ShapeType.roundRect, { x, y, w, h, fill: { color: C.card }, line: { color: accentColor || C.border }, rectRadius: 0.08 });
  sl.addText(titleText, { x: x+0.15, y: y+0.1, w: w-0.3, h: 0.4, fontSize: 15, bold: true, color: accentColor || C.text, fontFace: 'Calibri' });
  if (bodyLines && bodyLines.length > 0) {
    const objs = bodyLines.map((line, i) => ({
      text: line,
      options: { fontSize: 13, color: C.text, fontFace: 'Calibri', breakLine: i < bodyLines.length - 1 }
    }));
    sl.addText(objs, { x: x+0.15, y: y+0.55, w: w-0.3, h: h-0.65, valign: 'top' });
  }
}

function addMetricTable(sl, x, y, w, colWidths, headers, rows) {
  const tableData = [
    headers.map(h => ({ text: h, options: { bold: true, color: C.text, fill: { color: C.info }, fontSize: 12, fontFace: 'Calibri', align: 'center' } })),
    ...rows.map(row => row.map(cell => {
      let color = C.text;
      if (cell.includes('↑↑↑')) color = C.danger;
      else if (cell.includes('↑↑')) color = C.warning;
      else if (cell.includes('↑')) color = 'FBBF24';
      else if (cell.includes('↓↓')) color = C.info;
      return { text: cell, options: { fontSize: 11, color, fill: { color: C.card }, fontFace: 'Calibri', align: 'center' } };
    }))
  ];
  sl.addTable(tableData, { x, y, w, colW: colWidths, border: { color: C.border }, autoPage: false });
}

// SLIDE 1 — PORTADA
titleSlide('Monitoreo de Datacenter','Guia de Ataques, Deteccion y Mitigacion','SENA - Tecnologia en Redes y Sistemas de Informacion');

// SLIDE 2 — CONTENIDO
{
  const sl = contentSlide('Contenido del Modulo', C.bgTitle);
  const groups = [
    { title: 'Ataques de Red',         items: 'DDoS/SYN Flood, Brute Force, Port Scan, ARP/MITM', color: C.danger, x: 0.4, y: 1.3 },
    { title: 'Ataques de Hardware',    items: 'Memory Leak, Disk Failure / RAID Failure',          color: C.warning, x: 6.8, y: 1.3 },
    { title: 'Seguridad Fisica (SST)', items: 'Falla Termica, Acceso No Autorizado',               color: C.ok, x: 0.4, y: 4.0 },
    { title: 'Ataques SSL/TLS',        items: 'SSL/TLS Downgrade, Certificado Expirado',           color: C.info, x: 6.8, y: 4.0 },
  ];
  for (const g of groups) addCard(sl, g.x, g.y, 5.9, 2.4, g.title, [g.items], g.color);
}

// SLIDE 3 — INTRO
{
  const sl = contentSlide('Que es un Ataque en Datacenter?');
  addCard(sl, 0.3, 1.2, 6.0, 3.4, 'Definicion', [
    'Un ataque en datacenter es cualquier accion deliberada o',
    'accidental que compromete la disponibilidad, integridad o',
    'confidencialidad de los sistemas y datos alojados.',
    '',
    'Pueden originarse de forma externa (ciberatacantes) o',
    'interna (fallas de hardware, errores de configuracion).',
  ], C.info);
  addCard(sl, 6.7, 1.2, 6.0, 3.4, 'Impactos Reales', [
    'Downtime: perdida de servicio (SLA en riesgo)',
    'Perdida o fuga de datos criticos',
    'Costos de recuperacion elevados',
    'Danos reputacionales ante clientes y reguladores',
    'Sanciones regulatorias (GDPR, ISO 27001)',
  ], C.danger);
  sl.addShape(pptx.ShapeType.roundRect, { x: 0.3, y: 4.9, w: 12.5, h: 1.2, fill: { color: '1C3A2B' }, line: { color: C.ok }, rectRadius: 0.08 });
  sl.addText('En el simulador, cada ataque afecta metricas reales: CPU %, RAM %, Net IN (MB/s), Disk I/O (MB/s), Conexiones activas',
    { x: 0.5, y: 5.05, w: 12.1, h: 0.8, fontSize: 15, bold: true, color: C.ok, fontFace: 'Calibri', align: 'center' });
}

// SLIDE 4 — DDoS / SYN Flood: Como funciona
{
  const sl = contentSlide('DDoS / SYN Flood - Como Funciona');
  addCard(sl, 0.3, 1.2, 5.8, 4.8, 'Distributed Denial of Service', [
    'Inunda el servidor con millones de paquetes SYN',
    '(inicio de handshake TCP) sin completar la conexion,',
    'agotando los recursos de red y CPU del servidor.',
    '',
    'El servidor queda esperando respuestas que nunca',
    'llegan (half-open connections), bloqueando trafico',
    'legitimo de usuarios reales.',
  ], C.danger);
  addCard(sl, 6.5, 1.2, 6.1, 4.8, 'Flujo del Ataque', [
    '1. Atacante envia SYN al servidor objetivo',
    '2. Servidor responde SYN-ACK y espera ACK final',
    '3. El ACK final nunca llega (timeout del atacante)',
    '4. Miles de conexiones half-open llenan la tabla',
    '5. Nuevas conexiones legitimas son rechazadas',
    '',
    'Variante DDoS: multiples IPs coordinadas (botnets)',
    'amplifican el volumen del ataque hasta saturacion.',
  ], C.warning);
}

// SLIDE 5 — DDoS / SYN Flood: Deteccion y Mitigacion
{
  const sl = contentSlide('DDoS / SYN Flood - Deteccion y Mitigacion');
  addCard(sl, 0.3, 1.2, 5.8, 2.8, 'Metricas en el Simulador', [
    'Net IN:       [CRITICO]   saturacion de ancho de banda',
    'Conexiones:   [CRITICO]   half-open masivas',
    'Latencia:     [ELEVADO]   respuestas lentas',
    'CPU:          [ELEVADO]   procesamiento de paquetes',
    'RAM:          [MODERADO]  buffers de red llenos',
  ], C.danger);
  addCard(sl, 0.3, 4.2, 5.8, 2.8, 'Como Detectarlo en el Simulador', [
    '1. Observar Net IN > 800 MB/s en el dashboard',
    '2. Conexiones activas > 5000 de multiples IPs',
    '3. CPU supera 90% sostenido por mas de 30 segundos',
  ], C.info);
  addCard(sl, 6.5, 1.2, 6.1, 5.8, 'Estrategias de Mitigacion', [
    '1. Rate Limiting: limitar paquetes por IP/segundo',
    '   iptables -A INPUT -p tcp --syn -m limit',
    '   --limit 1/s --limit-burst 3 -j ACCEPT',
    '',
    '2. SYN Cookies: responder sin abrir estado en tabla',
    '   sysctl -w net.ipv4.tcp_syncookies=1',
    '',
    '3. Firewall / ACL: bloquear IPs de origen masivo',
    '',
    '4. CDN / Scrubbing Center: absorber trafico',
    '   antes de llegar al servidor de produccion',
    '',
    '5. Null-route temporal a IPs atacantes detectadas',
  ], C.ok);
}

// SLIDE 6 — Brute Force
{
  const sl = contentSlide('Brute Force Attack');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Funciona', [
    'Tecnica de ataque que intenta adivinar credenciales',
    'probando combinaciones de usuario/contrasena de forma',
    'automatizada y repetitiva contra un servicio.',
    '',
    'Tipos de Brute Force:',
    'Dictionary Attack: wordlist de contrasenas comunes',
    'Credential Stuffing: credenciales de brechas previas',
    'Hybrid: combinaciones de diccionario mas patrones',
    '',
    'Herramientas comunes: Hydra, Medusa, Burp Suite',
  ], C.warning);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Metricas en el Simulador', [
    'Conexiones:  [ELEVADO]   intentos repetidos por IP',
    'CPU:         [MODERADO]  proceso de autenticacion',
    'Net IN:      [MODERADO]  trafico de login',
    'RAM:         [NORMAL]    impacto minimo',
  ], C.warning);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. fail2ban: bloqueo automatico tras N intentos',
    '2. Bloqueo por IP: ban temporal o permanente',
    '3. MFA: segundo factor de autenticacion obligatorio',
    '4. CAPTCHA en interfaces web de login',
    '5. Contrasenas largas (>16 chars) con gestores',
  ], C.ok);
}

// SLIDE 7 — Port Scan
{
  const sl = contentSlide('Port Scan / Reconocimiento de Red');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Funciona', [
    'Tecnica de reconocimiento para descubrir puertos',
    'abiertos y servicios disponibles en un host objetivo.',
    'Permite mapear la superficie de ataque antes de',
    'lanzar un exploit especifico.',
    '',
    'Tipos de scan con nmap:',
    'SYN Scan (-sS): rapido y sigiloso',
    'TCP Connect (-sT): completa el handshake',
    'UDP Scan (-sU): detecta servicios UDP',
    'Version Scan (-sV): identifica versiones exactas',
  ], C.info);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Metricas en el Simulador', [
    'Net IN:      [MODERADO]  trafico de sondeo',
    'Conexiones:  [ELEVADO]   pocas IPs, muchos puertos',
    'CPU:         [NORMAL]    impacto bajo',
    'RAM:         [NORMAL]    impacto minimo',
  ], C.info);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Stealth mode en servicios no publicos',
    '2. IDS/IPS: Snort, Suricata - alertas de scan',
    '3. Firewall: default-deny, solo puertos necesarios',
    '4. Port knocking: secuencia de puertos como llave',
    '5. Honeypots: detectar reconocimiento activo',
  ], C.ok);
}

// SLIDE 8 — ARP Spoofing / MITM
{
  const sl = contentSlide('ARP Spoofing / Man-in-the-Middle (MITM)');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Funciona', [
    'El atacante envia respuestas ARP falsas para asociar',
    'su MAC a la IP de otro host (gateway o servidor),',
    'redirigiendo el trafico a traves de su maquina.',
    '',
    'Flujo del ataque:',
    '1. Atacante envia ARP Reply: IP gateway = su MAC',
    '2. Victima actualiza su tabla ARP con datos falsos',
    '3. Todo el trafico de la victima pasa por el atacante',
    '4. Puede leer, modificar o inyectar paquetes',
    '',
    'Herramientas: arpspoof, ettercap, bettercap',
  ], C.danger);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Metricas en el Simulador', [
    'Net IN/OUT:  [ELEVADO]   trafico duplicado/reenviado',
    'Latencia:    [ELEVADO]   salto adicional por atacante',
    'Conexiones:  [MODERADO]  retransmisiones TCP',
    'CPU:         [MODERADO]  re-encapsulacion paquetes',
  ], C.danger);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Dynamic ARP Inspection (DAI) en switches L2',
    '2. 802.1X: autenticacion de dispositivos en la red',
    '3. ARP estatico en infraestructura critica',
    '4. Segmentacion con VLANs para aislar segmentos',
    '5. Deteccion activa: XArp, arpwatch',
  ], C.ok);
}

// SLIDE 9 — Memory Leak
{
  const sl = contentSlide('Memory Leak - Fuga de Memoria');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Funciona', [
    'Ocurre cuando un proceso reserva memoria RAM pero',
    'nunca la libera, acumulandola hasta agotar los',
    'recursos del sistema operativo.',
    '',
    'No es un ataque externo: es una falla de software,',
    'pero puede ser explotada deliberadamente.',
    '',
    'Causas comunes:',
    'Bucles sin liberacion de objetos (malloc sin free)',
    'Referencias circulares en lenguajes sin GC',
    'Handlers de eventos no removidos correctamente',
    'Buffers de log que crecen sin limite configurado',
  ], C.warning);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Metricas en el Simulador', [
    'RAM:    [CRITICO]  crecimiento continuo sin estabilizar',
    'CPU:    [NORMAL]   normal o ligeramente elevado',
    'Net IN: [NORMAL]   sin cambio significativo',
    'Disco:  [NORMAL]   hasta que se activa swap en disco',
  ], C.warning);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Monitorear tendencia de RAM (alerta >85%)',
    '2. Reiniciar proceso afectado (workaround temporal)',
    '3. Aplicar patch o actualizar el software afectado',
    '4. Usar Valgrind / AddressSanitizer en entorno QA',
    '5. Limitar memoria maxima del proceso con cgroups',
  ], C.ok);
}

// SLIDE 10 — Disk Failure
{
  const sl = contentSlide('Disk Failure / RAID Failure');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Funciona', [
    'Falla fisica o logica de un disco de almacenamiento.',
    'En entornos con RAID, la falla de un disco puede',
    'degradar el array y exponer datos si falla otro.',
    '',
    'Tipos de falla:',
    'Falla mecanica: cabezal o platillos danados (HDD)',
    'Falla electronica: controlador del disco daado',
    'Bad sectors: errores de lectura/escritura persistentes',
    'RAID degradado: perdida de redundancia activa',
    '',
    'Impacto: perdida de datos, downtime prolongado',
  ], C.danger);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Metricas en el Simulador', [
    'Disk I/O:    [CRITICO]  >150 MB/s con errores',
    'Disk Used:   [ELEVADO]  crecimiento anomalo',
    'CPU:         [MODERADO] retry de operaciones I/O',
    'RAM:         [MODERADO] buffers I/O pendientes',
  ], C.danger);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Monitorear SMART: smartctl -a /dev/sdX',
    '2. Reemplazar disco fallido de inmediato',
    '3. Rebuild RAID: mdadm --manage /dev/md0 --add',
    '4. Backups 3-2-1: 3 copias, 2 medios, 1 offsite',
    '5. Alertas proactivas SMART en Nagios / Zabbix',
  ], C.ok);
}

// SLIDE 11 — SST: Falla Termica
{
  const sl = contentSlide('SST - Falla Termica (Temperatura Critica)');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Ocurre', [
    'La temperatura en el rack supera los umbrales seguros',
    '(>27 C ambiente, >80 C en componentes), poniendo en',
    'riesgo hardware y disponibilidad del servicio.',
    '',
    'Causas frecuentes:',
    'Falla del sistema CRAC/CRAH de enfriamiento',
    'Bloqueo del flujo de aire en pasillos del datacenter',
    'Sobredensidad de equipos en el rack sin planificacion',
    'Falla electrica en UPS que genera calor adicional',
    '',
    'Impacto: throttling de CPU, apagado de emergencia',
    'por UEFI thermal shutdown, dano permanente en hardware',
  ], C.danger);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Sensores SST Activados', [
    'Temperatura:   ALERTA - umbral superado (>27 C)',
    'Humo:          Normal  - sin combustion detectada',
    'Energia:       ALERTA  - consumo elevado anormal',
    'Acceso Fisico: Normal  - sin intrusiones registradas',
  ], C.warning);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Verificar estado de unidades CRAC/CRAH',
    '2. Hot-aisle / Cold-aisle containment en el rack',
    '3. Blanking panels en espacios vacios del rack',
    '4. Alertas tempranas configuradas a 25 C',
    '5. Protocolo de apagado ordenado si T supera 30 C',
  ], C.ok);
}

// SLIDE 12 — SST: Acceso No Autorizado
{
  const sl = contentSlide('SST - Acceso No Autorizado');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Ocurre', [
    'Entrada fisica al datacenter por personal no autorizado,',
    'visitante sin escolta o mediante tecnicas de ingenieria',
    'social como tailgating.',
    '',
    'Vectores comunes:',
    'Tailgating: seguir a personal autorizado en la entrada',
    'Credenciales clonadas (RFID/NFC)',
    'Ingenieria social al personal de seguridad fisica',
    'Tecnico externo sin supervision ni acompanante',
    '',
    'Impacto: robo de hardware, insercion de dispositivos',
    'maliciosos como USB, implantes de red o keyloggers',
  ], C.danger);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Sensores SST Activados', [
    'Control de Acceso:  ALERTA - acceso no registrado',
    'CCTV:               Grabacion activa en tiempo real',
    'Temperatura:        Normal',
    'Humo:               Normal',
  ], C.danger);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Bloqueo inmediato de credencial comprometida',
    '2. Revisar logs de acceso en el SIEM',
    '3. Revision de grabaciones CCTV del incidente',
    '4. Doble factor fisico: PIN + badge + biometria',
    '5. Mantraps / airlocks en acceso principal al DC',
  ], C.ok);
}

// SLIDE 13 — SSL/TLS Downgrade
{
  const sl = contentSlide('SSL/TLS Downgrade Attack');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Como Funciona', [
    'El atacante manipula la negociacion TLS para forzar al',
    'servidor a usar una version antigua (TLS 1.0, TLS 1.1,',
    'SSL 3.0) con vulnerabilidades conocidas y explotables.',
    '',
    'Flujo del ataque MITM:',
    '1. Atacante intercepta el Client Hello del cliente',
    '2. Modifica la lista de cipher suites soportadas',
    '3. Servidor acepta el protocolo antiguo propuesto',
    '4. Atacante puede descifrar el trafico capturado',
    '',
    'Vulnerabilidades: POODLE (SSL3), BEAST (TLS1.0),',
    'FREAK (exportar cifrado debil), DROWN (SSLv2)',
  ], C.danger);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Indicadores en el Simulador', [
    'Alerta SSL: version negociada = TLS 1.0 o TLS 1.1',
    'Net OUT:    [MODERADO]  trafico reencaminado',
    'Latencia:   [ELEVADO]   insercion de proxy MITM',
    'Cert:       Valido pero protocolo inseguro activo',
  ], C.warning);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    '1. Forzar TLS 1.2 minimo (idealmente TLS 1.3)',
    '   nginx: ssl_protocols TLSv1.2 TLSv1.3;',
    '2. Deshabilitar SSL 3.0, TLS 1.0, TLS 1.1',
    '3. HSTS: Strict-Transport-Security en el header',
    '4. Cipher suites: solo AEAD (AES-GCM, ChaCha20)',
    '5. Validar config: ssllabs.com/ssltest',
  ], C.ok);
}

// SLIDE 14 — SSL Expirado
{
  const sl = contentSlide('Certificado SSL/TLS Expirado');
  addCard(sl, 0.3, 1.2, 5.8, 5.4, 'Que es y Que Implica', [
    'Un certificado X.509 tiene una fecha de vencimiento.',
    'Al expirar, los navegadores y clientes rechazan la',
    'conexion HTTPS mostrando error de seguridad critico.',
    '',
    'Impacto inmediato:',
    'HTTPS caido: servicio inaccesible para usuarios finales',
    'APIs y microservicios fallan con mutual TLS activo',
    'Monitoreo reporta downtime aunque el servicio corra',
    'Reputacion: usuarios ven alerta "No Seguro" en Chrome',
    '',
    'No es un ataque pero es vector explotable:',
    'atacantes usan la confusion del usuario para phishing',
  ], C.warning);
  addCard(sl, 6.5, 1.2, 6.1, 2.5, 'Indicadores en el Simulador', [
    'Alerta SSL:  certificado expirado (dias = 0)',
    'HTTPS:       DOWN - conexiones rechazadas por clientes',
    'Net IN:      [CAIDA]  trafico cae abruptamente',
    'Logs:        errores 500/503 masivos en acceso',
  ], C.danger);
  addCard(sl, 6.5, 3.9, 6.1, 2.7, 'Mitigacion', [
    "1. certbot renew (Let's Encrypt - sin costo)",
    '2. Renovacion automatica: cron o systemd timer',
    '3. Monitoreo de vencimiento con Nagios check_http',
    '4. Alertas a 30, 14, 7 y 1 dia antes del vencimiento',
    '5. Certificate Manager en AWS / GCP / Azure',
  ], C.ok);
}

// SLIDE 15 — Protocolo de Respuesta
{
  const sl = contentSlide('Protocolo General de Respuesta a Incidentes');
  const steps = [
    { n: '1', title: 'DETECTAR',   desc: 'Dashboard muestra anomalia en metricas. Alerta automatica activada en el sistema.',      color: C.danger },
    { n: '2', title: 'ANALIZAR',   desc: 'Identificar metrica principal afectada. Correlacionar con otras senales del sistema.',   color: C.warning },
    { n: '3', title: 'CLASIFICAR', desc: 'Determinar tipo de ataque. Asignar severidad: critica / alta / media / baja.',           color: C.info },
    { n: '4', title: 'MITIGAR',    desc: 'Aplicar contramedida especifica. Verificar normalizacion de metricas en el dashboard.',  color: C.ok },
  ];
  const boxW = 2.8;
  const boxH = 4.0;
  steps.forEach((s, i) => {
    const x = 0.4 + i * (boxW + 0.5);
    sl.addShape(pptx.ShapeType.roundRect, { x, y: 1.4, w: boxW, h: boxH, fill: { color: C.card }, line: { color: s.color, pt: 2 }, rectRadius: 0.1 });
    sl.addShape(pptx.ShapeType.ellipse, { x: x + boxW/2 - 0.35, y: 1.55, w: 0.7, h: 0.7, fill: { color: s.color }, line: { color: s.color } });
    sl.addText(s.n, { x: x + boxW/2 - 0.35, y: 1.58, w: 0.7, h: 0.64, fontSize: 22, bold: true, color: C.bgContent, fontFace: 'Calibri', align: 'center', valign: 'middle' });
    sl.addText(s.title, { x: x+0.1, y: 2.4, w: boxW-0.2, h: 0.5, fontSize: 16, bold: true, color: s.color, fontFace: 'Calibri', align: 'center' });
    sl.addText(s.desc, { x: x+0.15, y: 3.0, w: boxW-0.3, h: 2.2, fontSize: 13, color: C.text, fontFace: 'Calibri', align: 'center', valign: 'top', wrap: true });
    if (i < steps.length - 1) {
      sl.addShape(pptx.ShapeType.rightArrow, { x: x+boxW+0.05, y: 3.0, w: 0.4, h: 0.5, fill: { color: C.muted }, line: { color: C.muted } });
    }
  });
}

// SLIDE 16 — Tabla Resumen
{
  const sl = contentSlide('Tabla Resumen - Metricas por Ataque');
  const headers = ['Ataque', 'CPU', 'RAM', 'Net IN', 'Conexiones', 'Disk I/O', 'Accion Inmediata'];
  const rows = [
    ['DDoS / SYN Flood',    '↑↑',  '↑',   '↑↑↑', '↑↑↑', '—',   'Rate limit + SYN cookies'],
    ['Brute Force',         '↑',   '—',   '↑',   '↑↑',  '—',   'fail2ban + bloqueo IP'],
    ['Port Scan',           '—',   '—',   '↑',   '↑↑',  '—',   'IDS/IPS + revisar firewall'],
    ['ARP Spoofing/MITM',   '↑',   '—',   '↑↑',  '↑',   '—',   'DAI en switch + ARP estatico'],
    ['Memory Leak',         '↑',   '↑↑↑', '—',   '—',   '—',   'Reiniciar proceso + patch'],
    ['Disk Failure',        '↑',   '↑',   '—',   '—',   '↑↑↑', 'Reemplazar disco + RAID rebuild'],
    ['Falla Termica (SST)', '↑↑',  '—',   '—',   '—',   '—',   'CRAC + reducir carga termica'],
    ['Acceso No Autorizado','—',   '—',   '—',   '—',   '—',   'Bloquear badge + revisar CCTV'],
    ['SSL/TLS Downgrade',   '—',   '—',   '↑',   '—',   '—',   'Forzar TLS 1.3 + deshabilitar antiguo'],
    ['Cert. SSL Expirado',  '—',   '—',   '↓↓',  '—',   '—',   'certbot renew + alerta vencimiento'],
  ];
  addMetricTable(sl, 0.2, 1.15, 12.93, [2.2, 0.8, 0.8, 0.9, 1.1, 0.9, 2.53], headers, rows);
  sl.addText('Leyenda: ↑↑↑ Critico  |  ↑↑ Elevado  |  ↑ Moderado  |  — Sin cambio  |  ↓↓ Caida brusca',
    { x: 0.3, y: 6.9, w: 12.7, h: 0.35, fontSize: 12, color: C.muted, fontFace: 'Calibri', align: 'center' });
}

// SLIDE 17 — Como usar el simulador
{
  const sl = contentSlide('Como Usar el DC Monitoring Simulator');
  const steps2 = [
    { n: '1', title: 'Instructor activa ataque',  desc: 'Selecciona el tipo de ataque en el panel. El aprendiz NO sabe cual es activado.',           color: C.danger },
    { n: '2', title: 'Aprendiz observa metricas', desc: 'Analiza el dashboard: CPU, RAM, Net IN, Disk I/O, Conexiones. Identifica la anomalia.',      color: C.warning },
    { n: '3', title: 'Diagnostico Guiado',        desc: 'Usa la herramienta de diagnostico del simulador para correlacionar senales y clasificar.',   color: C.info },
    { n: '4', title: 'Bitacora y Reporte',        desc: 'Documenta: tipo de ataque, metricas observadas, acciones tomadas y tiempo de respuesta.',    color: C.ok },
  ];
  const bW = 2.9, bH = 4.3;
  steps2.forEach((s, i) => {
    const x = 0.3 + i * (bW + 0.42);
    addCard(sl, x, 1.3, bW, bH, s.n + '. ' + s.title, [s.desc], s.color);
  });
}

// SLIDE 18 — CIERRE
{
  const sl = pptx.addSlide();
  sl.background = { color: C.bgTitle };
  sl.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.15, h: 7.5, fill: { color: C.ok }, line: { color: C.ok } });
  sl.addText('"La practica hace al experto"', { x: 0.5, y: 1.8, w: 12.3, h: 1.0, fontSize: 36, bold: true, italic: true, color: C.ok, fontFace: 'Calibri', align: 'center' });
  sl.addText('El monitoreo en tiempo real no es una opcion: es la primera linea de defensa.\nCada metrica que aprendes a leer hoy puede significar horas menos de downtime manana.',
    { x: 1.0, y: 3.1, w: 11.3, h: 1.5, fontSize: 18, color: C.text, fontFace: 'Calibri', align: 'center' });
  sl.addShape(pptx.ShapeType.roundRect, { x: 3.5, y: 5.2, w: 6.3, h: 1.0, fill: { color: C.card }, line: { color: C.info }, rectRadius: 0.1 });
  sl.addText('DC Monitoring Simulator - SENA Tecnologia en Redes y Sistemas',
    { x: 3.5, y: 5.4, w: 6.3, h: 0.6, fontSize: 15, color: C.info, fontFace: 'Calibri', align: 'center' });
}

// GUARDAR
const OUT = '/sessions/peaceful-serene-bardeen/mnt/datacenter-simulator/Guia_Ataques_Datacenter.pptx';
pptx.writeFile({ fileName: OUT })
  .then(() => console.log('OK: ' + OUT))
  .catch(e => { console.error('ERROR:', e); process.exit(1); });
