# DC Monitoring Simulator — Contexto para Claude Code

## Qué es este proyecto
Simulador de monitoreo de datacenter para formación de analistas SOC.
Backend FastAPI + SQLite, frontend HTML/JS puro, deploy en Render.com.

- **Repo:** https://github.com/lubeto/datacenter-simulator
- **Producción:** https://datacenter-simulator.onrender.com
- **Estado completo:** ver `ESTADO.md` en esta raíz

## Stack
- Python 3.11, FastAPI, SQLAlchemy async, SQLite (Render disk)
- HTML/JS vanilla (sin framework), CSS custom properties
- Docker en Render, autoDeploy desde rama `main`

## Reglas críticas de edición

### NUNCA truncar archivos grandes
Los siguientes archivos superan 3000 líneas. Usar SIEMPRE ediciones quirúrgicas (str_replace), nunca reescritura completa:
- `frontend/index.html` (~3263 líneas) — dashboard aprendiz
- `frontend/instructor.html` (~3936 líneas) — panel instructor

**Antes de cualquier push:** ejecutar `python3 -m py_compile backend/main.py` para verificar sintaxis.

### Patrón de rutas FastAPI
Cada feature tiene su propio archivo en `backend/api/routes_*.py`.
Registrar en `backend/main.py`:
```python
from .api.routes_nuevo import router as nuevo_router
app.include_router(nuevo_router)
```

### Autenticación
- `Depends(get_current_student)` — cualquier estudiante autenticado
- `Depends(require_instructor)` — solo instructores
- Ambos en `backend/api/routes_students.py`

### Acceso a estado de simulación
```python
from ..simulation.engine import state as sim_state
# sim_state.active_attacks, sim_state.offline_nodes, sim_state.get_simulated_hour()
```

### Variables de entorno (Render)
- `SECRET_KEY`, `ADMIN_PASSWORD`, `ALLOWED_ORIGINS`
- NO hardcodear valores en código

## V3 en desarrollo — Fase 1

### Terminal Simulada (prioridad actual)
Archivos a crear:
- `backend/simulation/command_engine.py` — parser + respuestas dinámicas
- `backend/api/routes_terminal.py` — `POST /api/terminal/exec`
- Panel en `frontend/index.html` usando `xterm.js` (CDN)

Comandos a implementar: `netstat`, `ping`, `ps aux`, `top`, `iptables`, `tail -f`, `systemctl`, `df -h`, `free -m`, `tcpdump`

El output de cada comando debe ser dinámico según `sim_state` (si hay DDoS activo, `netstat` muestra miles de conexiones).

### Visor de Logs en Crudo
- `backend/simulation/log_generator.py`
- `GET /api/logs/live?type=access|auth|system&node_id=X`

### Editor de Reglas de Firewall
- `backend/simulation/rule_engine.py`
- `POST /api/firewall/rules`

Ver `ESTADO.md` → sección "Roadmap V3" para detalles completos de cada feature.

## Cómo correr localmente
```powershell
cd D:\Documentos\Lubeto\datacenter-simulator
C:\Users\ASUS\AppData\Local\Python\bin\python3.exe -m uvicorn backend.main:app --reload --port 8000
```

## Git — problemas conocidos
Si aparece `HEAD.lock` o `index.lock`:
```powershell
Remove-Item D:\Documentos\Lubeto\datacenter-simulator\.git\HEAD.lock -Force
Remove-Item D:\Documentos\Lubeto\datacenter-simulator\.git\index.lock -Force
```
