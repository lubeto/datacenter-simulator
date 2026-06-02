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

## Estado pendiente (para próxima sesión)

- [ ] Verificar en producción que los bugs de instructor.html quedan resueltos
- [ ] Investigar por qué `/api/attacks/incidents` retorna error (ver logs de Render)
- [ ] Revisar si `loadEvalReports()` (Reportes Evaluativos) carga correctamente los nombres
- [ ] Confirmar que el disco persistente de Render conserva la DB entre deploys

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
