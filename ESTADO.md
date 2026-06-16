# Estado del Proyecto — DC Monitoring Simulator

## Última sesión: 2026-06-15 — COMPLETADA ✅ (Migración SQLite→PostgreSQL + reimport 211 bitácoras + Feedback IA Gemini + drawer unificado)

---

### Sesión 2026-06-15 — COMPLETADA ✅

#### Mapa de red — fixes visuales (`frontend/index.html`)
- Leyenda movida del SVG al panel derecho (rect height 252px) — ya no solapa nodos ACCESS
- Etiquetas de capas (PERIMETER/ROUTING/CORE/DISTRIBUTION/ACCESS): color `#7dd3fc` opacity 0.75 — antes invisibles con fondo oscuro
- Panel derecho reducido a `height=252` para no tapar STORAGE-01

#### Drawer unificado Logs/Terminal/Firewall (`frontend/index.html`)
- **Reemplazados 3 paneles flotantes** (se solapaban y eran difíciles de mover) por un **único `#toolsDrawer`** anclado en la parte inferior con tabs
- Altura 240px, handle de resize (drag), botón minimizar (▬) y cerrar (✕) separados
- Al abrir el drawer, `#missionWidget` sube dinámicamente para no quedar tapado
- Funciones clave: `_openToolsDrawer(tab)`, `_switchToolTab(tab)`, `_minimizeDrawer()`, `_restoreDrawer()`, `_collapseDrawer()`, `_applyDrawerOpen(h)`, `_initDrawerResize()`
- Tab colors: Logs=azul, Terminal=verde, Firewall=rojo

#### IP única por atacante (`backend/simulation/attacks.py`, `command_engine.py`)
- Cada incidente genera un `attacker_ip` único aleatorio según el tipo de ataque
- Rangos: DoS/DDoS→203.0.113.x, Brute Force→198.51.100.x, Unauth→185.220.101.x, SSL→91.108.4.x
- `netstat`, `syslog`, `tcpdump` usan la misma IP consistentemente
- `apply_firewall_mitigation()` valida la IP específica primero, luego fallback por prefijo/puerto

#### Botón "→ FW" en Logs
- Al marcar una línea IOC con IP de atacante, aparece botón `🔥 IP → FW`
- `_sendIpToFirewall(ip)`: abre tab Firewall con la IP pre-cargada en el campo de bloqueo
- `_extractIp(line)`: regex que detecta las 4 rangos de IPs atacantes

#### Feedback IA de Bitácora — Gemini (`backend/api/routes_ai_feedback.py`)
- **NUEVO archivo**: endpoint `POST /api/ai/bitacora-feedback`
- Llama a `gemini-2.0-flash` via httpx con prompt en español
- Evalúa: Claridad (1-5), Completitud (1-5), Terminología técnica (1-5) + 3 sugerencias + resumen
- Registrado en `main.py`: `from .api.routes_ai_feedback import router as ai_feedback_router`
- **Frontend**: botón "✨ Revisar con IA antes de guardar" en modal bitácora
- Panel inline con 3 barras de progreso animadas + lista de sugerencias
- Cooldown de 30s entre solicitudes (contador regresivo en el botón)
- `GEMINI_API_KEY` configurada en Render Dashboard → Environment
- **Tier gratuito**: 1,500 req/día — suficiente para 20 aprendices × 1 día de clase
- Bugs resueltos durante implementación: 401 (quitar auth dependency), 404 (modelo 1.5-flash→2.0-flash), 429 (cuota gratuita durante pruebas — resuelto con cooldown)

#### guia-simulador.html (NUEVO archivo)
- Guía standalone con tema claro (fondo `#f8fafc`, tarjetas blancas)
- Tabla de referencia de comandos + procedimientos por tipo de ataque
- `code` blocks con `word-break:break-all` y color `#1e293b` para legibilidad

#### Migración SQLite → PostgreSQL (2026-06-15)
- `backend/requirements.txt`: `aiosqlite` → `asyncpg==0.29.0`
- `backend/database/db.py`: eliminado `connect_args`, auto-fix prefijo `postgresql://` → `postgresql+asyncpg://`
- `backend/database/models.py`: todos los `Enum` convertidos a `String` (compatibilidad PG)
- `render.yaml`: `DATABASE_URL` apunta a PostgreSQL
- BD `dc-simulator-db` creada en Render (Free, Oregon, PostgreSQL 18)
- `DATABASE_URL` agregada manualmente en Render → Environment
- Backup previo: `backup_datacenter_20260615.json` (guardado en OneDrive + Google Drive)
- Reimportación exitosa: 20 students, 340 sessions, 636 incidents, **211 bitácoras**, 211 guided_sessions, 145 practice_sessions
- Endpoints temporales: `GET /api/admin/export-data`, `POST /api/admin/import-data` (mantener para futuras migraciones)
- **Variables de entorno añadidas a Render:** `DATABASE_URL` (Internal URL de dc-simulator-db)

#### Commits sesión
- `90c55b0` — feat: Gemini AI feedback for bitácora + guia-simulador.html
- `8b0ffa5` — fix: correct import path in routes_ai_feedback
- `28ced21` — fix: remove auth dependency from AI feedback endpoint (401 error)
- `fb9afb3` — fix: update Gemini model to gemini-2.0-flash
- `e7964ba` — fix: better error messages for Gemini 429/404
- `c61fb2b` — feat: add 30s cooldown between AI feedback requests

#### Variables de entorno añadidas
- `GEMINI_API_KEY` — clave Google AI Studio (tier gratuito, 1500 req/día)

---

### Sesión 2026-06-13 — COMPLETADA ✅

Serie de bugs reportados por el instructor vía capturas de pantalla, todos corregidos y mergeados a `main`.

#### `frontend/instructor.html`
- `printClassReport()` — nueva función para el botón "Reporte de Clase" (tab Clase Guiada), abre ventana de impresión con la tabla `#classReportBody`
- Renombrado el `generateClassReport()` duplicado (bitácoras) → `printDayReport()`; había colisión de nombres de función JS (la 2ª definición sobrescribía a la 1ª), por eso el botón "Reporte del Día" no hacía nada
- CSS `!important` en ambas ventanas de impresión (`th,td,span{color:#1e293b !important;background:transparent !important}`) — el texto salía gris claro sobre blanco, illegible
- Commits: `53b7809`, `0c6b1e6`

#### `frontend/index.html` — Paneles flotantes (Logs / Terminal / Firewall)
- **Bug crítico**: los 3 paneles tenían `display:none` Y `display:flex` en el mismo atributo `style` — la 2ª declaración ganaba, dejándolos visibles/vacíos desde el load y con el toggle invertido (por eso "Logs no funciona": `loadLogs()` nunca se ejecutaba). Eliminado el `display:flex` duplicado. Commit `[fix display duplicado]`
- **Coexistencia**: antes, abrir un panel cerraba los otros dos (`_closeOtherFloatingPanels`). El instructor pidió poder tener Logs+Terminal+Firewall abiertos a la vez para mitigar — se quitó el cierre mutuo, solo se minimiza el panel de Diagnóstico guiado si está abierto. Commit `[fix paneles coexisten]`

#### `frontend/index.html` — Panel de Diagnóstico guiado
- Por decisión explícita del instructor: el panel guiado **ya NO se abre automáticamente** cuando escala un incidente (`incident_escalated`). Solo se abre bajo demanda (botones "Detectar"/"Investigar"). Commit `9ffdecf`
- **Regla a preservar**: no reintroducir auto-apertura de `guidedPanel`/`startGuidedMode` por eventos pasivos

#### MTTD en "Reporte de Clase" → tabla "Detalle por Aprendiz"
- Causa: `_openGuidedPanel()` nunca seteaba `mttd_seconds` en `guidedState.incident`, así que las bitácoras se guardaban siempre con `mttd_seconds: null`
- Fix: `_openGuidedPanel(incId, attackType, nodeId, mttdSeconds)` ahora recibe y guarda `mttd_seconds`; `detectIncident` y `ackAlert` calculan el MTTD vía `/api/attacks/incidents/detect` antes de abrir el panel. Commit `7041a17`

#### Verificado por el instructor en producción
- ✅ Logs ahora carga correctamente (select de nodo, access.log, búsqueda)
- ✅ Logs + Terminal + Firewall pueden estar abiertos simultáneamente sin desaparecer

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

### Sesión 2026-06-12 — COMPLETADA ✅

#### Panel guiado movido a la izquierda (`frontend/index.html`)
- El panel de diagnóstico guiado cubría el mapa de red (estaba en la derecha)
- Movido al lado izquierdo para que el aprendiz vea el mapa sin obstáculos
- Cambios en `.guided-panel` CSS: `right:-105vw` → `left:-105vw`, `right:0` → `left:0`
- Cambiados: `border-left→border-right`, `border-bottom-left-radius→border-bottom-right-radius`, `box-shadow:-4px→4px`
- `_syncNotifSide()` actualizada: notificaciones siempre a la derecha (ya no conflicto)
- Commit: `fix: panel guiado a la izquierda, notificaciones siempre a la derecha`

#### Reset de actividad estudiantil — nuevo endpoint `/api/admin/reset-activity`
- **Contexto**: Inicio de nueva etapa pedagógica — se necesitaba borrar toda la actividad conservando cuentas
- **Archivo nuevo**: `backend/api/routes_admin.py`
  - Endpoint `POST /api/admin/reset-activity` (requiere token instructor)
  - Borra en orden de FK: bitácoras, eval_groups, sst_protocol_sessions, practice_sessions, guided_sessions, reports, mitigation_actions, alerts, incidents, sessions, metrics, sst_readings, ssl_certificates
  - Resetea contadores acumulados de Student a cero (total_sessions, total_incidents, avg_mttd, avg_mttr, avg_score)
  - Retorna JSON con conteo por tabla y total eliminado
- **Registrado en main.py**: `from .api.routes_admin import router as admin_router` + `app.include_router(admin_router)`
- **Resultado del reset ejecutado (2026-06-12)**:
  - 288 bitácoras, 1975 incidentes, 355 sesiones, 19 reportes
  - 732 métricas, 20910 lecturas SST, 4 diagnósticos guiados, 2 alertas, 5 SSL
  - **Total: 24,291 registros eliminados** — 20 cuentas conservadas intactas

#### Fix `backend/main.py` truncado — causa del deploy fallido
- **Síntoma**: Deploy `7ce103c` falló con "Exited with status 1 — SyntaxError: '{' was never closed at line 355"
- **Causa**: El archivo `main.py` estaba truncado desde una sesión anterior. La línea 360 terminaba en `"simulated_hour": ` sin valor ni cierre del dict
- **Diagnóstico**: `python3 -m py_compile` en sandbox Linux confirmó el truncamiento; el Read tool (Windows) veía el archivo aparentemente completo por diferencia de sync entre mounts
- **Fix**: Python script en sandbox reemplazó líneas 360+ con el contenido correcto:
  ```python
          "simulated_hour": sim_state.get_simulated_hour(),
          "timestamp": datetime.utcnow().isoformat(),
      }
  ```
- **Regla reforzada**: Antes de cualquier push, ejecutar `python3 -m py_compile backend/main.py` en el sandbox para verificar sintaxis
- Commits: `7ce103c` (roto) → `5918462` (fix, deploy live ✅)

#### Cómo ejecutar el reset desde PowerShell (para futuras etapas)
```powershell
# 1. Login instructor (form-urlencoded, NO json)
$resp = Invoke-RestMethod -Uri "https://datacenter-simulator.onrender.com/api/auth/login" -Method POST -Body "username=instructor@datacenter.edu&password=Admin1234!" -ContentType "application/x-www-form-urlencoded"
$token = $resp.access_token

# 2. Ejecutar reset
Invoke-RestMethod -Uri "https://datacenter-simulator.onrender.com/api/admin/reset-activity" -Method POST -Headers @{Authorization="Bearer $token"} | ConvertTo-Json
```

---

### Sesión 2026-06-08 — COMPLETADA ✅

#### Resumen
Sesión larga con 3 bugs críticos encontrados y resueltos. Plataforma funcional al cierre (screenshots confirman "En vivo", 1 conectado, JS OK, lista de aprendices OK).

#### `backend/simulation/scheduler.py` — Fix ssl_check_loop datetime ✅
- Error: `Object of type datetime is not JSON serializable` cada 30s → loop crash → WS nunca conectaba → frontend stuck "Conectando..."
- Fix: `"expires_at": expires_at.isoformat()` en línea 201
- Commit `8fe19a3` — desplegado y verificado en producción

#### `frontend/instructor.html` — Restauración completa (3818→3936 líneas) ✅
- El Edit tool truncó el archivo a 3787 líneas (3ª vez que ocurre en este proyecto)
- Síntomas: `switchTab is not defined`, `logout is not defined`, `initWebSocket is not defined` → todo el panel roto
- Fix: `git show 47f296d:frontend/instructor.html` como base → Python string replacement (nunca más Edit tool en archivos grandes)
- Re-aplicados 3 cambios:
  1. Card HTML `#qualityCard` con donut chart y tabla de aprendices
  2. Función `loadBitacoraQuality()` + `let anQualChart = null`
  3. Wire en `loadAnalytics()`
- Archivo final: 3936 líneas, termina `</script>\n</body>\n</html>`, todas las funciones presentes
- Push exitoso desde PowerShell con `Remove-Item .git/index.lock -Force`

#### `backend/api/routes_analytics.py` — Endpoint calidad bitácoras ✅
- `GET /api/analytics/bitacora-quality` (requiere instructor)
- Retorna: `{total, pct_alta, by_level, by_student}` ordenado por pct_alta desc
- Lógica `_text_quality` inlineada para evitar import circular

#### `backend/api/routes_reports.py` — Fix duplicado + null bytes ✅
- Eliminado bloque `elif full_summary` duplicado (viejo simple de 32 líneas)
- Limpiados null bytes introducidos por Edit tool
- Verificado con `ast.parse`
- `git show` confirmó que el fix ya estaba en commit `179d8f5` (no requirió nuevo push)

#### Commits clave
- `8fe19a3` — fix: expires_at.isoformat() en ssl_check_loop
- `[fix instructor.html]` — restaurar instructor.html completo (truncado) + panel calidad bitácoras
- `179d8f5` — feat: panel analítica calidad de bitácoras (incluye fix routes_reports)

#### Regla establecida (anti-truncation)
> **NUNCA usar Edit tool en archivos >500 líneas.** Siempre: `git show <commit>:archivo > /tmp/base` → Python string replacement → `cp` al destino.

---

### Sesión 2026-06-08 (panel analítica calidad de bitácoras + fix SSL informe)

#### `backend/api/routes_analytics.py` — Nuevo endpoint de calidad
- Agregado `GET /api/analytics/bitacora-quality` (requiere instructor)
- Itera todas las bitácoras, aplica la misma lógica `_text_quality` de `routes_bitacoras.py` (inline)
- Retorna: `{total, pct_alta, by_level: {alta, media, baja, muy_baja}, by_student: [...]}`
- `by_student` incluye: nombre, total, conteo por nivel, avg_quality (0-1), pct_alta
- Ordenado por `pct_alta` descendente

#### `frontend/instructor.html` — Panel "🔬 Calidad Textual de Bitácoras"
- Card nueva en `tab-analytics`, justo antes del cierre del tab, después del historial de incidentes
- **Donut Chart.js** (140×140px): Alta verde / Media amarillo / Baja naranja / Basura rojo
- **5 KPIs**: total bitácoras, % alta (coloreado según umbral), conteo Alta, Media, Baja+Basura
- **Tabla por aprendiz**: nombre, total, barra de distribución visual (spans coloreados), calidad promedio /100, % alta
- Leyenda inferior: A=Alta M=Media B=Baja X=Basura
- Función `loadBitacoraQuality()` — async, maneja estado vacío y errores
- Auto-carga al llamar `loadAnalytics()` (wired en el catch del ranking)
- Botón "↻ Actualizar" independiente en el card header

#### `backend/api/routes_reports.py` — Fix sección 8 SSL
- Ambos bloques `ssl_data` ahora incluyen `is_valid`, `is_expired`, `domain`, `alert_message`
- El primer bloque (línea ~243) usaba `getattr` como fallback; corregido
- El segundo bloque (línea ~369) en `full_summary` completo también corregido
- Resultado: sección 8 del PDF ya no muestra ❌ para todos los certificados

#### Commits
- `179d8f5` — feat: panel analítica calidad de bitácoras + fix sección 8 SSL informe
- `[pendiente push]` — fix: eliminar bloque full_summary duplicado + null bytes en routes_reports

#### Bug detectado en deploy Render
- Deploy `179d8f5` falló con "Exited with status 1"
- Causa: `routes_reports.py` tenía DOS bloques `elif report_type == "full_summary"` (el viejo simple de ~32 líneas no se eliminó al agregar el nuevo completo) + null bytes introducidos por el Edit tool
- Fix aplicado: eliminado el bloque duplicado + `python3 -c "data.replace(b'\x00',b'')"` para limpiar null bytes
- Syntax OK verificado localmente (`ast.parse` sin errores)
- **Push pendiente** — el sandbox no puede borrar `.git/HEAD.lock`; ejecutar desde PowerShell:
  ```powershell
  Remove-Item D:\Documentos\Lubeto\datacenter-simulator\.git\HEAD.lock -Force
  cd D:\Documentos\Lubeto\datacenter-simulator
  git add backend\api\routes_reports.py
  git commit -m "fix: eliminar bloque full_summary duplicado en routes_reports"
  git push origin main
  ```

---

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

- [x] Panel guiado movido a la izquierda ✅ (commit 5918462)
- [x] Endpoint reset actividad estudiantil `/api/admin/reset-activity` ✅
- [x] Fix main.py truncado ✅ (commit 5918462, deploy live)
- [x] Reset ejecutado: 24,291 registros borrados, 20 cuentas conservadas ✅
- [ ] Verificar panel "🔬 Calidad Textual de Bitácoras" en tab Analytics (pendiente revisión visual)
- [ ] Verificar penalización de calidad de bitácora en panel de resultados (estudiante)
- [x] **V3 Fase 1 — COMPLETA** ✅ (verificado en producción 2026-06-13): Terminal Simulada, Visor de Logs en Crudo, Editor de Reglas de Firewall — los 3 paneles funcionan y pueden coexistir abiertos
- [x] **V3 Fase 2 — Contexto — COMPLETA** ✅ (2026-06-15): Escenarios Narrativos + Modo Clase en Vivo (ver detalle en sesiones de abajo)
- [x] **Misión Activa (Stage 4)** (`feat-mision-activa`): Stage 4 del panel guiado reemplazado por misión procedimental real — 4 pasos secuenciales: investigar con terminal (netstat/tcpdump/top/ps), marcar 2+ IOC en logs, aplicar regla en firewall, verificar con terminal. Widget flotante `#missionWidget` (inferior derecho) muestra progreso en tiempo real con penalización de -15 pts si supera 90s. Al completar los 4 pasos se auto-cierra con `checkGuidedAnswer('mission_complete')`. Hooks añadidos en `_termRunCommand`, `toggleIoc`, `fwBlockIp`, `fwBlockPort`. La misión se cancela limpiamente si el panel guiado se cierra manualmente.

### Sesión 2026-06-14 — Auditoría panel guiado + Modo Clase en Vivo
- [x] Fix dropdown "Monitor en Vivo" instructor: usaba `/api/students/list` (no existe) → ahora `/api/students/`
- [x] Fix 500 en `/api/sessions/student/{id}/live`: accedía a `stu.level` que no existe en el modelo `Student` → ahora valor fijo "Principiante"
- [x] Auditoría preguntas panel guiado por categoría (ssl/sst/hardware/red): SST y hardware son deterministas (OK); categoría 'red' usa métricas reales (OK)
- [x] Fix `arp_spoofing`: no generaba ningún efecto en métricas (`engine.py`), pero el panel guiado pedía identificar "tráfico de red anómalo" → ahora genera aumento de net_in/net_out/latencia/pkt_loss
- [x] Modo Clase en Vivo: `/api/instructor/live-status` ahora incluye `active_attacks` con `detected_count`/`detected_names` por incidente, vía `Incident.detected_at` + `Session.student_id`
- [x] Fix: `_escalation_loop` (auto-detección/escalamiento cada 10s) no respetaba `sim_state.is_paused` → seguía reabriendo el panel guiado y notificando aunque la simulación estuviera pausada. Ahora hace `continue` si `is_paused`.
- [x] **Pausa total para el aprendiz**: al pausar, se muestra `#pauseOverlay` (overlay de pantalla completa, bloquea clicks) sobre todo el dashboard del estudiante hasta que el instructor reanude. `handleMetrics` sincroniza el overlay con `data.paused` (silencioso); `sim_paused`/`sim_resumed` notifican el cambio. Dedup con `_simPausedState` para no notificar en cada tick de métricas (2s).
  - **Verificado en producción**: overlay cubre correctamente el `guidedPanel` y bloquea toda interacción ✅
  - **Posible mejora futura**: bloquear también a nivel backend los endpoints de detección/mitigación/guiado cuando `is_paused=True` (actualmente solo es un bloqueo visual en frontend).

### Sesión 2026-06-14 (cont.) — Inicio Fase 2: Escenarios Narrativos
- [x] **Hallazgo importante**: `backend/api/routes_attacks.py` tenía la sección "Modo Clase Guiada" (`GuidedStep`, `GuidedSessionRequest`, `/guided/start`, `/guided/stop`, `/guided/status`) **duplicada 3 veces de forma idéntica** (líneas 294-471, ~170 líneas redundantes). Eliminadas las 2 copias extra, queda solo 1. Archivo pasó de 471 a 351 líneas.
- [x] **Descubrimiento clave**: la infraestructura de "Clase Guiada" (`scheduler.start_guided_session`/`_guided_session_loop`) YA ES, en esencia, el motor de Escenarios Narrativos del roadmap (state machine de pasos/fases con delay, inyección de ataques, registro de `Incident`, broadcasts `guided_step_countdown`/`guided_step_launched`/`guided_step_stats`/`guided_session_completed`). Solo le faltaba: (a) el lado del aprendiz no escuchaba estos eventos, (b) catálogo de escenarios con nombre/briefing/descripción para el instructor.
- [x] **Frontend aprendiz** (`frontend/index.html`): agregados handlers para `guided_session_started` (briefing inicial), `guided_step_countdown` (aviso "próxima fase en Xs"), `guided_step_launched` (notificación de nueva fase/incidente), `guided_session_stopped`/`guided_session_completed` (debriefing). Por ahora vía `notify()` (toast), cumpliendo el requisito mínimo de "briefing/indicador de fase/debriefing" del roadmap.
- [x] **Pendiente resuelto** (`feat-catalogo-escenarios`): catálogo de escenarios narrativos para "🎓 Clase Guiada". `backend/api/routes_attacks.py` agrega `SCENARIO_CATALOG` (`_build_scenario_catalog()`), construido a partir de `ATTACK_CHAINS` (`mitigation.py`: apt_web, apt_data_exfil, ransomware_sim, infrastructure_takeover) — convierte cada `phase` en un `GuidedStep` (delay/duración relativos) y corrige el alias `tls_downgrade`→`ssl_tls_downgrade`. Nuevo endpoint `GET /api/attacks/guided/catalog`. Frontend instructor: selector "Escenario narrativo" en la tarjeta "Nueva Sesión Guiada" (`loadGuidedCatalog`/`applyGuidedScenario`) que precarga nombre, pasos y briefing. `GuidedSessionRequest` ahora acepta `briefing`, incluido en el broadcast `guided_session_started`. Frontend aprendiz: `handleScenarioStarted` muestra el briefing en el toast. Las tarjetas "🎯 Escenarios Predefinidos" (`runScenario`) siguen siendo un mecanismo distinto (inyección instantánea sin fases) — no se modificaron.
- [x] **Pendiente resuelto** (`feat-fase-indicator-debrief`): `frontend/index.html` agrega `#scenarioBar` (barra sticky azul "🎬 Nombre — Fase X/N", visible durante toda la sesión guiada, actualizada en `guided_step_countdown`/`guided_step_launched`) y `#debriefModal` (modal de cierre con resumen "N/M fases detectadas" + detalle por fase: ataque, nodo, quién detectó y MTTD). Nuevo handler `guided_step_stats` acumula `_scenarioState.stepStats` durante la sesión; `guided_session_completed`/`guided_session_stopped` muestran el modal y limpian el estado.
- [x] **V3 Fase 2 — COMPLETA**: Escenarios Narrativos (motor + catálogo + briefing/fase/debriefing) y Modo Clase en Vivo (pausa total, live-status con detección) implementados y mergeados a main.

### Sesión 2026-06-14 (cont. 2) — Coherencia respuestas/pistas panel guiado
- [x] **Fix `fix-red-stage2-coherencia`**: en categoría 'red', Stage 2 (analizar), cuando `_gCorrectAnalyze` cae en el fallback por tipo de ataque (ninguna métrica supera su umbral realmente), ahora se fuerza a que la métrica esperada como correcta (net/conn/cpu/ram) supere claramente su umbral en el contexto mostrado — igual que ya se hacía en hardware/SSL. Antes el aprendiz veía todo "normal" pero el sistema exigía identificar "tráfico anormal".
- [x] **Fix `fix-hints-por-categoria`**: `GUIDED_HINTS` era un único array genérico orientado a ataques de red (firewall, fail2ban, etc.) usado para TODAS las categorías. En incidentes SST/SSL/hardware las pistas no tenían relación con la pregunta (ej. alerta de Sobrecalentamiento mostraba "Para ataques de red: rate limiting..."). Se creó `CATEGORY_HINTS` con pistas propias para `sst`/`ssl`/`hardware`/`red`, seleccionadas según `_gCategory(guidedState.incident)` en `showGuidedHint()`.

---

## Roadmap V3 (completo)

Fuente: conversación Cowork "ESTADO.md V2 suggestions" + `dc_simulator_v3_roadmap.html`.

### Fase 1 — Inmersión ✅ COMPLETA
> El aprendiz empieza a hacer, no solo a ver. Usa el stack actual sin cambiar infraestructura.

- **🖥️ Terminal Simulada** (medio, 2-3 ses.) ✅
  - xterm.js, `POST /api/terminal/exec`, `command_engine.py`, acceso a `sim_state`
  - Comandos: `netstat`, `ping`, `ps aux`, `top`, `iptables`, `tail -f`, `systemctl`, `df -h`, `free -m`, `tcpdump`
- **📄 Visor de Logs en Crudo** (bajo, 1 ses.) ✅
  - `log_generator.py`, `GET /api/logs/live?type=access|auth|system&node_id=X`
  - Filtro/búsqueda tipo grep, marcar líneas como IOC, "Agregar a evidencias"
- **🔒 Editor de Reglas de Firewall** (medio, 2 ses.) ✅
  - `command_engine.py` (add_block_ip/port, flush, remove), `POST /api/firewall/rules`
  - Sintaxis: BLOCK IP/PORT, RATE_LIMIT, ALLOW ONLY PORT, ISOLATE NODE

### Fase 2 — Contexto ✅ COMPLETA (2026-06-15)
> Escenarios reales, no eventos aleatorios. Requiere reestructurar `scheduler.py` para manejar fases (no reescritura total). El modo clase en vivo aprovecha el WebSocket que ya existe.

- **🎬 Escenarios Narrativos** (medio, 2-3 ses.)
  - Estructura JSON: `id, nombre, descripción, phases: [{trigger, attacks, duration, briefing}], victory_conditions (MTTD < X min), failure_conditions (N nodos caídos)`
  - Backend: `scenario_engine.py` (state machine de fases), `POST /api/scenarios/launch`, integración con `attack_manager`, tabla `scenario_sessions`
  - Frontend instructor: selector de escenario + descripción, botón Lanzar/Detener, indicador de fase actual
  - Frontend aprendiz: briefing inicial, indicador "Fase 1/3", debriefing al terminar
  - Ejemplos de escenarios: Black Friday, Insider Threat, Ransomware lateral

- **📡 Modo Clase en Vivo** (medio, 2 ses.)
  - Backend (WebSocket ya existe): comandos broadcast `pause_sim`, `reveal_solution`, `push_notification`; `GET /api/instructor/live-status`
  - Panel instructor: vista de estudiantes conectados en vivo, indicador quién detectó/quién no, botón Pausar Simulación global, botón Revelar Solución

- **📝 Feedback IA de Bitácora** ✅ COMPLETA (2026-06-15)
  - `POST /api/ai/bitacora-feedback` → Gemini 2.0 Flash, evalúa claridad/completitud/terminología
  - Panel inline con barras de progreso + sugerencias, cooldown 30s entre solicitudes
  - `GEMINI_API_KEY` en Render Environment, tier gratuito suficiente para uso en clase

### Fase 3 — Colaboración (futuro)
> Trabajo en equipo como en un SOC real. La sala colaborativa es la más compleja — necesita estado compartido entre sesiones; ahí SQLite empieza a doler y conviene evaluar PostgreSQL (Render lo ofrece nativamente).

- **👥 Sala de Crisis Colaborativa** (alto, 4-5 ses.)
  - WebSocket "rooms", `role_manager.py`, tablas `collab_sessions` + `collab_actions`, estado compartido por room
  - Roles: Analista T1 (dashboard+alertas), Analista T2 (diagnóstico guiado), Responder (terminal+firewall), Comunicador (status updates)
  - Frontend: selector de sala/código de grupo, chat interno, vista según rol, score grupal en tiempo real
  - ⚠️ Consideraciones: SQLite con contención → evaluar PostgreSQL; límite de conexiones WS en Render Starter

- **📋 Playbook del Aprendiz** (bajo, 1 ses.)
  - Tabla `playbooks` (student_id, scenario_type, content, rating), editor Markdown post-incidente
  - Panel instructor: lista + botón "Publicar como referencia", sección pública "Playbooks de la Clase"

- **🏅 Badges y Certificaciones** (bajo, 1 ses.)
  - Criterios en JSON `{id, nombre, condicion, icono}`, `badge_engine.py` evalúa al completar sesión
  - Tabla `student_badges` (student_id, badge_id, earned_at), panel de perfil con colección, exportar SVG/PNG
