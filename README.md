# DC Monitoring Simulator 🖥️

> Simulador de Centro de Datos para prácticas estudiantiles de ciberseguridad y administración de redes.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ¿Qué es esto?

El **DC Monitoring Simulator** es una plataforma web educativa que simula un centro de datos con 12 nodos virtuales. Los estudiantes practican detección y mitigación de ataques en tiempo real mientras el sistema registra su desempeño para evaluación.

### Características principales

- **12 nodos virtuales** (Web, DB, App, Load Balancer, Firewall, Router, Switch, Storage)
- **15 tipos de ataque** simulados con ataques DoS/DDoS, intrusiones, ataques SSL, y más
- **4 cadenas APT** (Advanced Persistent Threat) con fases encadenadas automáticas
- **13 sensores SST** (temperatura, humedad, humo, UPS, control de acceso)
- **Monitoreo SSL** con expiración simulada de certificados
- **Sistema de escalado** de alertas: Warning (60s) → Critical (120s) → Auto-detección (300s, penalidad 25%)
- **Analytics estudiantil**: ranking, MTTD/MTTR, puntuaciones, exportación CSV
- **Motor de mitigación** con guía paso a paso y comandos Linux reales
- **WebSocket** para actualizaciones en tiempo real (cada 2 segundos)
- **Roles**: Instructor (control total) y Estudiante (detección/mitigación)

---

## Arquitectura

```
dc-monitoring-simulator/
├── backend/
│   ├── api/              # Rutas FastAPI
│   │   ├── routes_students.py    # Auth + CRUD estudiantes
│   │   ├── routes_metrics.py     # Métricas, SST, SSL, alertas
│   │   ├── routes_attacks.py     # Control de ataques
│   │   ├── routes_reports.py     # PDF + CSV reports
│   │   ├── routes_analytics.py   # Ranking, APT, mitigación
│   │   └── websocket.py          # WebSocket manager
│   ├── auth/
│   │   └── jwt_handler.py        # JWT HS256
│   ├── database/
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── crud.py               # Operaciones DB
│   │   └── db.py                 # Engine async SQLite
│   ├── middleware/
│   │   └── security.py           # Headers HTTP + request logging
│   ├── simulation/
│   │   ├── nodes.py              # Definición de nodos y sensores
│   │   ├── engine.py             # Motor de métricas y snapshots
│   │   ├── scheduler.py          # Loop de simulación + escalado
│   │   └── mitigation.py         # Reglas, APT chains, MitigationEngine
│   ├── reports/
│   │   └── generator.py          # PDF/CSV con ReportLab
│   ├── main.py                   # Punto de entrada FastAPI
│   └── requirements.txt
├── frontend/
│   ├── index.html                # Dashboard principal (tiempo real)
│   ├── instructor.html           # Panel de control del instructor
│   ├── analytics.html            # Analytics y ranking
│   └── reports.html              # Generación de reportes
├── docker/
│   ├── Dockerfile                # Multi-stage build
│   └── docker-compose.yml        # Stack completo
├── render.yaml                   # Deploy en Render.com
├── .env.example                  # Variables de entorno
└── README.md
```

---

## Inicio rápido

### Opción 1: Docker Compose (recomendado)

```bash
# 1. Clonar o descomprimir el proyecto
cd datacenter-simulator

# 2. Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env — CAMBIA al menos SECRET_KEY y ADMIN_PASSWORD

# 3. Construir e iniciar
docker compose -f docker/docker-compose.yml up --build -d

# 4. Abrir en el navegador
open http://localhost:8000
```

### Opción 2: Entorno local (desarrollo)

```bash
# Requisitos: Python 3.11+
cd datacenter-simulator

# Crear entorno virtual
python -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

# Instalar dependencias
pip install -r backend/requirements.txt

# Copiar variables de entorno
cp .env.example .env

# Iniciar servidor
python -m uvicorn backend.main:app --reload --port 8000
```

---

## Variables de Entorno

| Variable | Descripción | Defecto |
|---|---|---|
| `SECRET_KEY` | Clave para firmar JWT (mín. 32 chars) | valor inseguro |
| `ADMIN_EMAIL` | Email del instructor inicial | instructor@datacenter.edu |
| `ADMIN_PASSWORD` | Contraseña del instructor | Admin1234! |
| `DATABASE_URL` | URL de SQLite async | `sqlite+aiosqlite:///./data/simulator.db` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de sesión | 480 (8h) |
| `NUM_NODES` | Número de nodos simulados | 12 |
| `METRICS_INTERVAL_SECONDS` | Frecuencia de actualización | 2 |
| `AUTO_ATTACK_ENABLED` | Ataques automáticos | true |
| `AUTO_ATTACK_MIN_INTERVAL_MIN` | Mínimo entre ataques auto | 5 |
| `AUTO_ATTACK_MAX_INTERVAL_MIN` | Máximo entre ataques auto | 20 |
| `ALLOWED_ORIGINS` | CORS — orígenes permitidos (CSV) | * |
| `RATE_LIMIT_AUTH_PER_MINUTE` | Intentos de login por IP/min | 10 |

Genera una `SECRET_KEY` segura con:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Páginas y Endpoints

### Páginas Web

| URL | Descripción | Acceso |
|---|---|---|
| `/` | Dashboard principal en tiempo real | Todos |
| `/instructor` | Panel de control de ataques | Instructor |
| `/analytics-page` | Ranking y analytics estudiantil | Todos |
| `/reports-page` | Generación de reportes PDF/CSV | Todos |
| `/docs` | Swagger UI (API interactiva) | Desarrollo |

### API REST

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/auth/login` | Login (devuelve JWT) |
| `POST` | `/api/auth/register` | Registrar estudiante |
| `GET` | `/api/auth/me` | Perfil del usuario actual |
| `GET` | `/api/metrics/snapshot` | Estado completo del DC |
| `GET` | `/api/metrics/nodes` | Lista de nodos |
| `GET` | `/api/metrics/history/{node_id}` | Historial de métricas |
| `GET` | `/api/metrics/summary` | Resumen global |
| `GET` | `/api/metrics/sst` | Estado sensores SST |
| `GET` | `/api/metrics/ssl` | Estado certificados SSL |
| `GET` | `/api/metrics/alerts` | Alertas activas |
| `POST` | `/api/metrics/alerts/{id}/ack` | Reconocer alerta |
| `POST` | `/api/attacks/inject` | Inyectar ataque (instructor) |
| `POST` | `/api/attacks/detect` | Detectar incidente (estudiante) |
| `POST` | `/api/attacks/mitigate/{id}` | Mitigar incidente |
| `GET` | `/api/analytics/ranking` | Ranking de estudiantes |
| `GET` | `/api/analytics/mitigation-rules` | Catálogo de mitigaciones |
| `POST` | `/api/analytics/apt-chains/{id}/launch` | Lanzar cadena APT |
| `GET` | `/api/reports/csv/ranking` | Export CSV ranking |
| `GET` | `/api/reports/pdf/{type}` | Reporte PDF |
| `GET` | `/health` | Health check |

### WebSocket

Conectar a `ws://localhost:8000/ws/{student_id}?token={jwt}`

Eventos recibidos:
- `metrics_update` — snapshot completo cada 2s
- `attack_started` — nuevo ataque detectado
- `incident_escalated` — alerta escalada (warning/critical)
- `incident_auto_detected` — detección automática (penalidad 25%)
- `apt_phase` — nueva fase de cadena APT activada
- `alert_created` — nueva alerta SST/SSL

---

## Deploy en Render.com

### Pasos

1. **Subir código a GitHub** (o GitLab/Bitbucket)
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git remote add origin https://github.com/TU_USUARIO/dc-simulator.git
   git push -u origin main
   ```

2. **Crear cuenta en [render.com](https://render.com)** (gratis)

3. **New → Blueprint** → conectar tu repositorio  
   Render detectará el `render.yaml` automáticamente.

4. **Configurar secretos** en el Dashboard de Render:
   - `ADMIN_PASSWORD` → tu contraseña segura
   - `ALLOWED_ORIGINS` → `https://TU-APP.onrender.com`

5. **Deploy** — Render construye la imagen Docker y despliega.

6. **Nota sobre el Plan Free**: En el plan gratuito de Render, el servicio se suspende tras 15 minutos de inactividad. Para uso en clase continuo, considera el plan Starter ($7/mes) que incluye disco persistente.

---

## Usuarios por Defecto

| Rol | Email | Contraseña |
|---|---|---|
| Instructor | `instructor@datacenter.edu` | `Admin1234!` |

El instructor puede registrar estudiantes desde el panel `/instructor` o los estudiantes pueden registrarse directamente en `/`.

---

## Tipos de Ataque Disponibles

| ID | Tipo | Descripción |
|---|---|---|
| `dos_http_flood` | HTTP Flood | Inundación de peticiones HTTP |
| `dos_syn_flood` | SYN Flood | Flood de paquetes TCP SYN |
| `dos_udp_flood` | UDP Flood | Flood de paquetes UDP |
| `ddos_amplification` | DDoS Amplificación | Amplificación DNS/NTP |
| `ddos_botnet` | DDoS Botnet | Ataque coordinado de bots |
| `sql_injection` | SQL Injection | Inyección SQL |
| `brute_force` | Brute Force | Fuerza bruta en auth |
| `port_scan` | Port Scan | Escaneo de puertos |
| `ssl_expired` | SSL Expirado | Certificado SSL vencido |
| `ssl_mitm` | SSL MITM | Man-in-the-Middle SSL |
| `thermal` | Temperatura | Sobrecalentamiento |
| `ransomware` | Ransomware | Cifrado de archivos |
| `data_exfiltration` | Data Exfil | Exfiltración de datos |
| `lateral_movement` | Movimiento Lateral | Pivoting interno |
| `privilege_escalation` | Priv. Escalation | Escalada de privilegios |

### Cadenas APT

| ID | Nombre | Fases |
|---|---|---|
| `apt_web` | Compromiso Web | port_scan → sql_injection → privilege_escalation |
| `apt_data_exfil` | Exfiltración de Datos | brute_force → lateral_movement → data_exfiltration |
| `ransomware_sim` | Simulación Ransomware | brute_force → lateral_movement → ransomware |
| `infrastructure_takeover` | Toma de Infraestructura | ddos_botnet → ssl_mitm → privilege_escalation |

---

## Sistema de Puntuación

Los estudiantes acumulan puntos por:

| Acción | Puntos |
|---|---|
| Detectar incidente (a tiempo) | +100 |
| Detectar incidente (warning) | +75 |
| Detectar incidente (crítico) | +50 |
| Completar mitigación | +50 |
| Detección automática | −25 (penalidad) |

Niveles: **Principiante** (0-499) → **Intermedio** (500-999) → **Avanzado** (1000-2499) → **Elite** (2500+)

---

## Desarrollo y Contribución

```bash
# Tests
pip install pytest pytest-asyncio httpx
pytest tests/ -v

# Lint
pip install ruff
ruff check backend/

# Format
pip install black
black backend/
```

---

## Licencia

MIT License — Libre para uso educativo.
