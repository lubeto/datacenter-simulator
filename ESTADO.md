# Estado del Proyecto — DC Monitoring Simulator

## Última sesión: 2026-06-02

---

## ¿Qué es este proyecto?
Simulador de monitoreo de datacenter con panel de instructor. Backend FastAPI + SQLite, frontend HTML/JS puro, desplegado en Render.com.

- **Repo GitHub:** https://github.com/lubeto/datacenter-simulator
- **Render:** ya configurado con `render.yaml`, `autoDeploy: true`
- **DB:** SQLite persistente en `/app/data/simulator.db` (disco Render)

---

## Cambios aplicados en esta sesión

### `frontend/instructor.html`

**1. `loadAllIncidents` — catch vacío corregido (línea ~1642)**
- **Bug:** `catch(e) {}` vacío → el div `allIncidentsList` quedaba en "Cargando..." indefinidamente si el API fallaba.
- **Fix:** El catch ahora muestra "Error cargando incidentes" en rojo.

**2. `_loadEvalStudentFilter` — catch vacío corregido (línea ~1835)**
- **Bug:** Mismo patrón. El dropdown `evalStudentSel` y los checkboxes `groupStudentChecks` quedaban en "Cargando aprendices..." para siempre.
- **Fix:** El catch ahora muestra mensaje de error en ambos elementos.

**3. `loadClassReport` — null guard agregado (línea ~2059)**
- **Bug:** `body.innerHTML = '...'` estaba FUERA del try-catch. Si `body` era null, la función colapsaba silenciosamente sin que el catch lo atrapara.
- **Fix:** Se movió el `innerHTML` inicial dentro del try y se agregó `if (!body) return;`.

---

## Cambios sesión 2026-06-02 (tercera parte — emergencia disco)

### Problema: disco SQLite lleno en Render (4.8M filas en tabla metrics)
- **Causa**: métricas se guardaban cada 2s para 12 nodos = ~500MB/día
- **Solución aplicada**:
  - `scheduler.py`: guardar en DB cada 30s (15 ciclos) en vez de cada 2s
  - `crud.py`: tabla `metrics` limitada a 60 filas por nodo (cap automático en cada INSERT)
  - `main.py`: limpieza al arrancar + cada hora (retención 6h)
  - `routes_attacks.py`: `from ..database.models import Incident` (faltaba import)
  - `main.py`: filtrar `sensor_name` y `alert_level` al guardar SST readings
  - `main.py`: restaurado `/health` y `/api/status` endpoints (estaban truncados)
- **Recuperación manual**: DB corrupta → backup a /tmp → rm DB → reinicio → restore
  - Restaurados: 20 estudiantes, 284 bitácoras, 304 sesiones

---

## Plan mejoras Dashboard Aprendiz (iniciar aquí si se cortan tokens)

### Orden de implementación:
- [x] **Paso 1**: Tema C — Graphite Cálido aplicado (`#18181b` + ámbar/naranja)
- [x] **Paso 2**: Panel diagnóstico responsive (`min(420px,96vw)`, móvil=100vw)
- [x] **Paso 3**: Nodo bajo diagnóstico → aro pulsante ámbar + etiqueta "🎯 ANALIZAR"
- [x] **Paso 4**: Score en tiempo real (⭐) + timer (⏱) en header del diagnóstico
- [x] **Paso 5**: Botón "Detectar ahora" en ámbar pulsante, más descriptivo
- [x] **Paso 6**: Timer implementado con `_startGuidedTimer()` / `_stopGuidedTimer()`

### Tema C — Graphite Cálido (variables CSS a aplicar):
```
--bg: #18181b
--bg2: #1f1f23
--card: #27272a
--card2: #2d2d30  
--border: #3f3f46
--accent: #f59e0b   (ámbar)
--accent2: #f97316  (naranja)
--green: #22c55e
--red: #ef4444
--yellow: #eab308
--muted: #a1a1aa
--text: #fafafa
```

---

## Cambios sesión 2026-06-02 (cuarta parte — mejoras dashboard aprendiz)

### `frontend/index.html`
- **Tema Graphite Cálido**: variables CSS `--bg:#18181b`, `--accent:#f59e0b`, `--accent2:#f97316`, reemplazos masivos de colores hardcodeados azulados
- **Panel guiado responsive**: `width:min(420px,96vw)`, media query móvil
- **Nodo bajo diagnóstico**: aro SVG pulsante ámbar + texto "🎯 ANALIZAR" en el mapa de red
- **HUD en panel guiado**: `guidedScoreDisplay` (score en tiempo real) + `guidedTimer` (cronómetro)
- **Botón Detectar**: estilo ámbar pulsante, texto más descriptivo
- **Modal bitácora**: `height:90vh` + `min-height:0` en bm-body → footer siempre visible; HTML del modal restaurado (estaba truncado — faltaban 4to campo y botón guardar)
- **Penalización calidad**: se muestra en panel de resultados como línea roja con score original → ajustado

### Bugs corregidos en esta sesión
- `routes_attacks.py`: faltaba `from ..database.models import Incident`
- `main.py`: `sensor_name` no filtrado al guardar SST → error DB
- `scheduler.py`: métricas guardadas cada 30s en vez de 2s (15x menos disco)
- `crud.py`: tabla metrics limitada a 60 filas/nodo (auto-limpieza en INSERT)
- `main.py`: limpieza al arrancar + /health endpoint restaurado
- DB corrupta por disco lleno: recuperación manual via Shell Render (20 estudiantes, 284 bitácoras, 304 sesiones restaurados)
- Diagnóstico guiado: SST muestra solo sensor relevante al ataque; hardware muestra métricas coherentes con ataque

## Cambios sesión 2026-06-03 (quinta parte — reportes y materiales)

### `frontend/reports.html`
- Rediseño de tarjetas: 6 tipos reemplazados por 4 más claros
- Tarjeta principal: **"Informe Completo del Aprendiz"** (tipo `full_summary`) destacada en ámbar
- `downloadReport`: descarga como `.pdf` (antes forzaba `.txt`)
- `printReport`: abre el PDF nativo del navegador (antes mostraba binario crudo como texto)
- `TYPE_LABELS` actualizado con nuevo nombre

### `backend/api/routes_reports.py`
- `_serialize_report()`: devuelve JSON correcto con `format`, `student_name`, `download_url`
- `/my-reports` y `/all`: usan `selectinload(Report.student)` para incluir nombre del aprendiz
- `full_summary`: recopila bitácoras completas (texto de 4 campos), diagnósticos guiados, protocolos SST, labs, incidentes, salud del DC, SSL/TLS

### `backend/reports/pdf_generator.py`
- `_build_full_summary_section()`: nueva función con 8 secciones completas
- `student_shift` → usa `_build_student_section()` (formato antiguo)
- `full_summary` → usa `_build_full_summary_section()` (formato nuevo con "section" keys)
- Fallback si no hay datos: mensaje explicativo en el PDF
- `ATTACK_LABELS`: diccionario de traducción de tipos de ataque

### Materiales educativos generados
- `Guia_Ataques_Datacenter.pptx` — 18 diapositivas, tema oscuro cyberseguridad
- `Guia_Ataques_Datacenter.html` — guía interactiva para estudiantes con buscador
- `build_attacks_pptx.js` — script fuente para regenerar el PPTX

---

## Estado pendiente (para próxima sesión)

- [ ] Probar "Informe Completo del Aprendiz" en producción tras el último deploy — debe mostrar las 8 secciones
- [ ] Bug BRUTE_FORCE: conexiones solo suben +200 (umbral 400) → engine.py línea `elif atype == "brute_force"` aumentar a `connections += 2000 * ramp`
- [ ] Verificar que penalización de calidad de bitácora aparece en panel de resultados
- [ ] Revisar `loadEvalReports()` en tab Reportes del instructor — nombres de aprendices
- [ ] Probar bitácora completa en producción (4to campo + botón guardar ya corregidos)

## Cambios sesión 2026-06-02 (segunda parte)

### `backend/simulation/engine.py`
- `memory_leak`: RAM ahora sube 3%/min con mínimo garantizado 82% (antes podía quedar baja)
- `disk_failure`: disk_io supera umbral 150 MB/s desde el inicio (+160 base), SMART errors elevados (5-20), disk_used sube con ramp
- Nuevos campos en métricas: `smart_errors` (int) y `access_alert` (bool) para diagnóstico guiado

### `frontend/index.html` — Diagnóstico Guiado
- **SST**: temperatura ya NO usa fallback aleatorio — cada subtipo de ataque muestra SOLO su sensor como anómalo (thermal→temp, smoke→humo, power→energía, unauth→acceso)
- **Hardware memory_leak**: si RAM live < 82%, se muestra 82-92% (siempre anómala)
- **Hardware disk_failure**: si disk_io < 160, se muestra 160-360 MB/s + SMART errors visibles

---

## Arquitectura rápida

```
backend/
  main.py                  — FastAPI app, init DB, rutas
  api/
    routes_students.py     — /api/students/  (list, create, delete)
    routes_attacks.py      — /api/attacks/incidents, /api/attacks/active
    routes_sessions.py     — /api/sessions/active, /api/sessions/report/all
    routes_bitacoras.py    — /api/bitacoras
    routes_analytics.py    — /api/analytics/
    routes_reports.py      — /api/reports/
  auth/jwt_handler.py      — JWT con SECRET_KEY
  database/models.py       — Student, Incident, EvalSession, Bitacora...
frontend/
  instructor.html          — Panel instructor (JS puro, ~3000 líneas)
  index.html               — Dashboard estudiante
render.yaml                — Config Render (Blueprint)
docker/Dockerfile          — Imagen Docker para Render
```

## Variables de entorno clave (Render Dashboard)
- `SECRET_KEY` — secreto JWT (NO cambiar entre deploys o se invalidan todos los tokens)
- `ADMIN_PASSWORD` — contraseña del instructor principal
- `ALLOWED_ORIGINS` — URL exacta de Render (ej: `https://dc-monitoring-simulator.onrender.com`)
