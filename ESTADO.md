# Estado del Proyecto — DC Monitoring Simulator

## Última sesión: 2026-06-07 (cierre — Sección 5 completada)

---

## ¿Qué es este proyecto?
Simulador de monitoreo de datacenter con panel de instructor. Backend FastAPI + SQLite, frontend HTML/JS puro, desplegado en Render.com.

- **Repo GitHub:** https://github.com/lubeto/datacenter-simulator
- **Render:** https://datacenter-simulator.onrender.com (autoDeploy: true desde main)
- **DB:** SQLite persistente en `/app/data/simulator.db` (disco Render)

---

## Arquitectura rápida

```
backend/
  main.py                  — FastAPI app, init DB, rutas
  api/
    routes_students.py     — /api/students/
    routes_attacks.py      — /api/attacks/incidents, /api/attacks/active
    routes_sessions.py     — /api/sessions/active, /api/sessions/report/all
    routes_bitacoras.py    — /api/bitacoras
    routes_analytics.py    — /api/analytics/
    routes_reports.py      — /api/reports/
  auth/jwt_handler.py      — JWT con SECRET_KEY
  database/models.py       — Student, Incident, EvalSession, Bitacora...
  simulation/engine.py     — Motor de métricas + ataques
  simulation/scheduler.py  — Ciclo cada 30s
frontend/
  instructor.html          — Panel instructor (~3000 líneas)
  index.html               — Dashboard estudiante (V2 activo)
  reports.html             — Página de reportes del estudiante
render.yaml                — Config Render (Blueprint)
docker/Dockerfile          — Imagen Docker para Render
```

## Variables de entorno clave (Render Dashboard)
- `SECRET_KEY` — secreto JWT (NO cambiar entre deploys)
- `ADMIN_PASSWORD` — contraseña del instructor principal
- `ALLOWED_ORIGINS` — URL exacta de Render

---

## Historial de sesiones

### Sesión 2026-06-07 (cierre — stats clase guiada + guía aprendiz + funciones JS)

#### `frontend/guia_aprendiz.html` (NUEVO)
- Guía educativa completa standalone para aprendices (misma dark theme del simulador)
- 5 secciones: El Proceso Completo (7 pasos), Cómo leer métricas (9 métricas × tabla), Tipos de ataque (red/hw/sst/ssl), Ayudas del simulador, Cómo llenar la bitácora
- Sidebar con scroll spy (IntersectionObserver), responsive
- Sección bitácora: 4 guías de campo, 4 pares malo/bueno, grid de calidad (Alta/Media/Baja/Basura), lista de penalizaciones, ejemplo DDoS completo, checklist

#### `backend/simulation/scheduler.py` — Clase Guiada mejorada
- Nuevo método `_get_step_stats(incident_id, step_info)`: consulta DB para detección, MTTD y conteo de sesiones activas al finalizar cada paso
- `_guided_session_loop` reescrito: guarda incidente con `AsyncSessionLocal` directo (obtiene `incident_id` real), emite `guided_step_stats` antes de cada nuevo paso y al completar la sesión
- Fallback a `_db_save_cb` si falla el guardado directo
- `guided_step_launched` ahora incluye `incident_id` y `attack_name`
- `guided_step_countdown` ahora incluye `step_num` y `delay_before_sec`

#### `frontend/instructor.html` — Funciones JS clase guiada (IMPLEMENTADAS)
- Todas las funciones que estaban en onclick pero sin definir, ahora implementadas:
  - `addGuidedStep()` / `removeGuidedStep(idx)` / `renderGuidedSteps()` — UI dinámica para construir la secuencia de ataques con selects de tipo+nodo+tiempo
  - `startGuidedSession()` / `stopGuidedSession()` — llaman a `/api/attacks/guided/start|stop`
  - `refreshGuidedStatus()` — consulta estado y actualiza `#guidedStatusPanel`
  - `addGuidedLog(icon, text, level)` — appends entradas al `#guidedLog` monospace con timestamp
  - `handleGuidedWsEvent(evt, data)` — router de eventos WS guiados:
    - `guided_session_started` → muestra banner verde
    - `guided_step_countdown` → actualiza status text
    - `guided_step_launched` → log con ⚡ en rojo
    - `guided_step_stats` → tarjeta resultado (verde=detectado, amarillo=sin detección) + MTTD + activos + notify toast
    - `guided_session_completed` / `guided_session_stopped` → oculta banner
- `guided_step_stats` agregado al switch WS en `handleWS()`

#### Commits
- `35dfa4f` — push anterior (reporte de clase + bitácoras auto-refresh + monitor individual)
- `[nuevo]` — feat: stats de paso completado en clase guiada + funciones JS guiada + guia_aprendiz.html

---

### Sesión 2026-06-07 (skills Cowork + fix brute_force + verificación producción)

#### Skills instaladas en Cowork
- `impeccable.skill` — skill de diseño UI/UX (adaptada de GitHub, sin Node.js)
- `caveman.skill` — modo comunicación ultra-comprimida (intensidades: lite/full/ultra/wenyan)
- `dc-monitor.skill` — skill propia del proyecto: briefing, monitoreo en vivo, actualizar ESTADO.md

#### `backend/simulation/engine.py`
- **Fix BRUTE_FORCE**: `connections + 200 * ramp` → `connections + 2000 * ramp` (commit 252a720)
- Umbral de detección era 400 conexiones; con +200 nunca se alcanzaba; ahora sube correctamente

#### Git
- Commit 252a720: fix brute_force connections +2000*ramp
- Commit 721c723: archivos sin rastrear (`Guia_Ataques_Datacenter.html`, `.pptx`, `build_attacks_pptx.js`)
- Eliminado archivo basura `h` (output de git guardado accidentalmente)
- Push a main → Render auto-deploy

#### Verificaciones en producción (https://datacenter-simulator.onrender.com)
- `loadEvalReports()` tab Reportes: ✅ nombres correctos (ABIMELEC, LAURA, DEIRIS, ANNEY, ELIANA)
- Catches en `instructor.html`: ✅ `loadAllIncidents`, `loadEvalReports`, `_loadEvalStudentFilter` — todos con mensaje de error, ninguno vacío
- "Informe Completo del Aprendiz": ✅ abre en ventana nueva, 2 páginas, 7 secciones visibles en página 1 + sección 8 en página 2

---

### Sesión 2026-06-03 (sexta parte — V2 implementada)

#### Sección 4 — UX del aprendiz ✅
**Fix 1: Zoom y pan en el mapa SVG**
- Zoom con botones +/− en esquina del mapa
- Pan con clic y arrastre
- `Ctrl+scroll` para zoom con rueda del mouse (sin Ctrl → scroll normal de página)
- Hint en subtítulo del mapa: "Ctrl+scroll para zoom · Arrastrar para mover"

**Fix 2: Selector de tema persistente (4 temas)**
- Botón 🎨 en navbar del estudiante
- Temas: 🌑 Graphite Cálido, 🌊 Oceanic, 🟣 Slate Púrpura, ☀️ Claro/Light
- Persiste en `localStorage` (clave `dc_theme`)
- Se aplica al cargar la página automáticamente

**Fix 3: Tabla de liderazgo anónima**
- Card "🏆 Top Detección — Esta Sesión" en dashboard
- `leaderboardAdd(mttd)` — guarda en `localStorage` (clave `dc_leaderboard`), top 10
- `renderLeaderboard()` — muestra top 5 con medallas 🥇🥈🥉 y barra de progreso
- Conectado en `detectIncident()` y `quickDetect()`
- 100% anónimo, sin nombres

#### Sección 2 — Pedagogía y evaluación ✅
**Banco de preguntas variadas por ataque**
- `GUIDED_Q_VARIANTS` — 2-3 variantes por etapa (detectar, analizar, clasificar, mitigar) y por categoría (red, hardware, ssl, sst)
- `_pickVariants()` elige aleatoriamente al abrir cada sesión
- `_getQVariant(stageKey, cat)` retorna la variante activa
- Los aprendices no pueden memorizar el patrón entre sesiones

**3 niveles de dificultad**
- Selector `<select id="guidedDiffSel">` en el header del panel de diagnóstico
- 🟢 **Guiado**: pista automática tras respuesta incorrecta (−10 pts después de 600ms)
- 🟡 **Asistido**: pista a demanda (botón "💡 Pista −10 pts") — default
- 🔴 **Experto**: sin botón de pista, countdown 5 min en rojo, −20 pts si se agota el tiempo
- Persiste en `localStorage` (clave `dc_difficulty`)

#### Sección 3 — Monitoreo en tiempo real más realista ✅
**Propagación de ataques en topología**
- `TOPOLOGY_DOWNSTREAM` — mapa de nodos aguas abajo por nodo infraestructura
- Un ataque en RTR-EDGE → todos los nodos downstream se vuelven **naranja** en el mapa
- Un ataque en FW-01 → toda la red se ve afectada
- `nmPropagated` (Set) — nodos con latencia elevada por propagación upstream
- `updatePropagation()` — corre en cada `loadIncidents()`

**Correlación de alertas (APT)**
- `checkAlertCorrelation(incidents)` — detecta ≥2 nodos distintos bajo ataque simultáneo
- Genera banner rojo "POSIBLE APT COORDINADO" en el panel de alertas
- Notificación push al estudiante
- Evento registrado en la línea de tiempo

**Línea de tiempo de sesión**
- Card nueva "📅 Línea de Tiempo — Sesión" debajo de Alertas del Sistema
- `addTimelineEvent(label, desc, type)` — registra eventos con timestamp relativo (mm:ss)
- Registra: inicio de sesión, detecciones (MTTD), diagnósticos completados (score), labs, SSTs, alertas APT
- Máximo 50 eventos, más reciente primero
- Botón "Limpiar" para resetear

---

### Sesión 2026-06-03 (quinta parte — reportes y materiales)

#### `frontend/reports.html`
- Rediseño de tarjetas: 6 tipos → 4 más claros
- Tarjeta principal: **"Informe Completo del Aprendiz"** (tipo `full_summary`) en ámbar
- `downloadReport`: descarga como `.pdf`
- `printReport`: abre PDF nativo del navegador

#### `backend/api/routes_reports.py`
- `_serialize_report()`: JSON correcto con `format`, `student_name`, `download_url`
- `full_summary`: bitácoras completas, diagnósticos guiados, protocolos SST, labs, incidentes

#### `backend/reports/pdf_generator.py`
- `_build_full_summary_section()`: 8 secciones completas
- `ATTACK_LABELS`: diccionario de traducción de tipos de ataque

#### Materiales educativos
- `Guia_Ataques_Datacenter.pptx` — 18 diapositivas, tema oscuro cyberseguridad
- `Guia_Ataques_Datacenter.html` — guía interactiva con buscador
- `build_attacks_pptx.js` — script fuente para regenerar el PPTX

---

### Sesión 2026-06-02 (cuarta parte — dashboard aprendiz)

#### `frontend/index.html`
- **Tema Graphite Cálido**: `--bg:#18181b`, `--accent:#f59e0b`, `--accent2:#f97316`
- **Panel guiado responsive**: `width:min(420px,96vw)`, media query móvil
- **Nodo bajo diagnóstico**: aro SVG pulsante ámbar + texto "🎯 ANALIZAR"
- **HUD**: `guidedScoreDisplay` (score en tiempo real) + `guidedTimer` (cronómetro)
- **Modal bitácora**: `height:90vh`, footer siempre visible, 4to campo + botón guardar restaurados

---

### Sesión 2026-06-02 (tercera parte — emergencia disco)

#### Problema: disco SQLite lleno (4.8M filas en tabla metrics)
- `scheduler.py`: guardar en DB cada 30s (antes cada 2s)
- `crud.py`: tabla `metrics` limitada a 60 filas por nodo
- `main.py`: limpieza al arrancar + cada hora (retención 6h)
- **Recuperación manual**: 20 estudiantes, 284 bitácoras, 304 sesiones restaurados

---

### Sesión 2026-06-02 (segunda parte — engine.py)

#### `backend/simulation/engine.py`
- `memory_leak`: RAM sube 3%/min, mínimo garantizado 82%
- `disk_failure`: disk_io > 150 MB/s desde inicio, SMART errors 5-20
- Nuevos campos: `smart_errors` (int) y `access_alert` (bool)

---

## Estado pendiente (para próxima sesión)

- [x] **Push pendiente**: cambios V2 pusheados a main ✅
- [x] **Bug BRUTE_FORCE**: fix en engine.py (commit 252a720) ✅
- [x] Probar "Informe Completo del Aprendiz" en producción ✅ (funciona, 2 páginas)
- [x] Revisar `loadEvalReports()` — nombres correctos en producción ✅
- [x] `instructor.html`: catches verificados en prod ✅
- [x] Reporte de clase con análisis automático ✅
- [x] Guía aprendiz `guia_aprendiz.html` ✅
- [x] Stats de paso completado en clase guiada ✅
- [x] Funciones JS clase guiada (addGuidedStep, startGuidedSession, handleGuidedWsEvent, etc.) ✅
- [ ] Verificar penalización de calidad de bitácora en panel de resultados (estudiante)
- [ ] Verificar sección 8 del reporte (página 2 del Informe Completo)
- [ ] Panel analítica de calidad de texto para instructor
- [ ] Migrar SQLite → PostgreSQL (Sección 1, baja prioridad)

---

## V2 — Mejoras propuestas (estado de implementación)

### ✅ Sección 4 — UX del aprendiz (completada)
- [x] Mapa interactivo con zoom/pan (Ctrl+scroll)
- [x] Selector de tema persistente (4 temas)
- [x] Tabla de liderazgo anónima por sesión

### ✅ Sección 2 — Pedagogía y evaluación (completada)
- [x] Banco de preguntas por ataque (2-3 variantes por etapa/categoría)
- [x] Tres niveles de dificultad (Guiado/Asistido/Experto)
- [ ] Panel analítica de calidad de texto para instructor (pendiente)

### ✅ Sección 3 — Monitoreo más realista (completada)
- [x] Propagación de ataques en topología (nodos downstream en naranja)
- [x] Correlación de alertas → alerta APT coordinado
- [x] Línea de tiempo de sesión completa

### 🔲 Sección 1 — Arquitectura y datos (pendiente)
- [ ] Migrar SQLite → PostgreSQL en Render
- [ ] Motor de simulación con escenarios predefinidos y progresión temporal realista

### ✅ Sección 5 — Gestión del instructor (completada)
- [x] Modo "clase guiada": secuencia de ataques programada por el instructor (commit f8200aa)
  - Tab 🎓 Clase Guiada en instructor.html
  - POST /api/attacks/guided/start|stop, GET /api/attacks/guided/status
  - Loop async en scheduler, broadcast WS por paso
  - Funciones JS: addGuidedStep, renderGuidedSteps, startGuidedSession, stopGuidedSession, refreshGuidedStatus, handleGuidedWsEvent
- [x] Vista de monitoreo individual del aprendiz en tiempo real (commit b52cf97)
  - Panel en tab Monitor con selector de aprendiz
  - GET /api/sessions/student/{id}/live — score, bitácoras, diagnósticos, MTTD, auto-refresh 20s
- [x] Reporte de clase con análisis automático
  - GET /api/sessions/class-report?date_str=YYYY-MM-DD
  - Abre ventana con resumen del día, tabla por aprendiz, análisis automático en lenguaje natural
- [x] Stats por paso de clase guiada (guided_step_stats WS event)
  - Al finalizar cada paso: muestra quién detectó, MTTD, cantidad de aprendices activos
  - Tarjeta verde/amarilla en log del instructor según si hubo detección o no
- [x] Guía aprendiz `frontend/guia_aprendiz.html` — doc educativo del proceso completo

---

## Cómo correr localmente

```powershell
cd D:\Documentos\Lubeto\datacenter-simulator
C:\Users\ASUS\AppData\Local\Python\bin\python3.exe -m uvicorn backend.main:app --reload --port 8000
```

Abrir: http://localhost:8000 (estudiante) | http://localhost:8000/instructor (instructor)

**Nota**: Las dependencias deben estar instaladas en ese Python. Si falla con `ModuleNotFoundError`, instalar primero:
```powershell
C:\Users\ASUS\AppData\Local\Python\bin\python3.exe -m pip install -r backend/requirements.txt
```
