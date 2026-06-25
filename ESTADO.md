# Estado del Proyecto — DC Monitoring Simulator

## Última sesión: 2026-06-25 (cont.) — Resaltado de nodo analizado + comunicación por sala (pendientes del cierre de curso, ya implementados)

---

## Sesión 2026-06-25 (continuación) — Los 2 pendientes para el 26-27 ya quedaron resueltos

Se descartó la idea de aislar técnicamente las salas colaborativas (más riesgo, sin tiempo) a favor de dos cambios visuales/de UX, mucho más simples y de bajo riesgo:

### 1. Resaltar el nodo que el aprendiz está analizando
Problema real: con varios nodos atacados a la vez (4 equipos el sábado, 4 nodos simultáneos), el aro dorado + etiqueta "🎯 ANALIZAR" del nodo seleccionado por el aprendiz vía "Detectar" estaban al mismo tamaño diminuto (8px) que la etiqueta roja "◉ ATAQUE" de cualquier otro nodo — no se distinguía cuál era el propio.
- `index.html`: aro dorado ahora con doble círculo, stroke-width 2-3 (antes 1), opacidad fija alta + pulso más amplio
- Etiqueta cambiada a "🎯 TU NODO — ANALIZAR" en 13px con fondo dorado tipo pastilla (antes texto plano 8px)
- Verificado: ningún nodo del mapa (`NM_POS`) queda lo bastante cerca del borde del viewBox (1100×430) para que la pastilla de 104px de ancho se recorte

### 2. Comunicación del instructor por sala colaborativa
Backend **no necesitó cambios**: el endpoint `POST /api/collab/rooms/{id}/actions` ya permite a cualquier autenticado (incluido el instructor) publicar en una sala, y `ws_manager.broadcast_to_room()` ya entrega el evento solo a los miembros conectados de esa sala — la pieza más difícil ya existía de antes.
- `instructor.html`: input + botón "📢 Enviar mensaje solo a esta sala" en el modal "Gestionar Sala", publica con `action_type:'instructor_message'`
- `index.html`: tanto la carga inicial del chat como el WS en vivo reconocen ese `action_type` y lo muestran como banner ámbar destacado (no como chat normal), además dispara un toast `notify()` para que no se pierda si el aprendiz no tiene el chat visible

### Verificado en producción
Ambos cambios confirmados con `curl` contra el HTML servido en `/dashboard` e `/instructor` después del deploy.

### Commits
- `14775dc` — resaltar nodo analizado
- `ba44c15` — comunicación por sala

### Estado para el 26-27: todo lo planeado está implementado y verificado
No queda ningún pendiente técnico conocido para el cierre de curso. Lista de lo que se construyó/corrigió en esta sesión + la anterior (24/25): auditoría de seguridad (2 pasadas), informe grupal con IA (con integración de Sala Colaborativa), fix de regresión crítica en Monitor en Vivo, auto-cierre por inactividad desactivado, resaltado del nodo analizado, comunicación del instructor por sala. El único punto abierto de fondo (no bloqueante) sigue siendo la validación completa del score del panel guiado server-side — documentado como backlog real para después del cierre de curso.

---

## Sesión 2026-06-24/25 — Preparación final clases del 26-27 (viernes/sábado, cierre de curso)

### Contexto: el 27 de junio es el último día de clases. Plan del instructor: viernes 26 = 3 clases guiadas (individual + grupal evaluativo), sábado 27 = sala colaborativa con 4 equipos (6, 5, 4, 4 integrantes) + informe grupal con IA.

### Auditoría exhaustiva por agentes (segunda pasada, más profunda que la del 21/22)
Se lanzaron 3 agentes en paralelo (backend completo, `index.html`, `instructor.html`) a leer función por función, no solo grep de patrones. Hallazgos reales corregidos:
- **CRÍTICO**: `GET /api/metrics/ssl` y `/alerts` sin auth → agregado `Depends(get_current_student)`
- **CRÍTICO**: XSS en sala colaborativa (`index.html`) — nombres de estudiante y todo el contenido de la bitácora colaborativa grupal sin escapar, incluyendo el caso de `</textarea>` rompiendo el tag vía innerHTML
- **CRÍTICO**: bloque de 219 líneas de "Clase Guiada" duplicado en `instructor.html` (código muerto desde hacía tiempo, sobrescrito silenciosamente) — eliminado
- **ALTO**: `POST /api/students/sessions/start`/`/close` sin verificar ownership — un estudiante podía manipular la sesión de otro. Agregado chequeo 403.
- **ALTO**: `routes_import.py`/`routes_export.py` devolvían `200 OK` con `{"error":...}` en vez de `403` cuando el rol no era instructor — cambiado a `HTTPException`.
- **ALTO**: XSS restante en Monitor en Vivo, Live Individual y reporte de Sala Colaborativa (`instructor.html`) — fuera del parche anterior, que solo cubrió los reportes impresos
- **MEDIO**: `_login_attempts` (rate-limit de `/login`, keyed por IP) nunca purgaba — único caché real con riesgo de crecer sin límite (los otros dos señalados, `_iptables_rules`/`_cert_days_cache`, resultaron acotados por diseño)
- **MEDIO**: score de bitácora — agregado cap de plausibilidad (score no puede superar lo que permite `correct_answers/total_questions` + margen) y el MTTD ahora se toma del incidente real en el servidor, no del cliente. **Pendiente real, no resuelto**: el backend sigue sin recalcular el score completo del panel guiado — requiere mover la lógica de preguntas/respuestas al servidor, cambio de varias sesiones, no urgente para el 26-27.
- Se descartó un hallazgo falso positivo: "3 fórmulas de ranking inconsistentes" — 2 de 3 eran idénticas, la tercera es una métrica distinta a propósito ("score de práctica" por volumen, con comentario explícito en el código)
- Se agregó `confirm()` a pausar simulación/auto-ataques (acciones de alto impacto); no se agregó a acciones restaurativas/rutinarias

### Feature nueva: Informe Grupal con IA (para el cierre de curso)
- `POST /api/ai/group-report`: junta las bitácoras de todos los integrantes de un `EvalGroup` ("Sesión Grupal"), más el contenido de cualquier `CollabBitacora` (Sala Colaborativa) donde hayan participado, y le pide a Claude Haiku un informe formal (resumen ejecutivo, incidentes atendidos, contribución por integrante, lecciones aprendidas, recomendaciones) en markdown
- `GET /api/sessions/my-groups`: para que un estudiante sepa a qué grupo pertenece (antes solo existía la versión de instructor)
- Frontend instructor (`instructor.html`): modal "🤖 Informe IA de Grupo"
- Frontend estudiante (`reports.html`): panel "Mi Informe Grupal con IA"
- El markdown de la IA se escapa con `_escapeHtml()` ANTES de aplicar el formato (##, **, -), no después — así un intento de inyección en una bitácora que llegue hasta el output de la IA queda neutralizado
- **Probado en producción con datos reales**: grupo de 6 integrantes (el tamaño más grande del sábado), 16.3 segundos de respuesta, informe completo y bien estructurado. Verificado con curl usando el token real del instructor.

### Regresión crítica encontrada y corregida en producción
El fix de timezone de la sesión anterior (`iso_utc()`, agrega sufijo `Z`) rompió `GET /api/instructor/live-status` con 500 en cada poll del Monitor en Vivo — el instructor lo descubrió por la consola del navegador (183+ errores acumulados). Causa: `datetime.fromisoformat()` en Python 3.11+ sí entiende el `Z` y devuelve un datetime **aware**, que luego no se puede comparar/insertar contra columnas `TIMESTAMP WITHOUT TIME ZONE` de Postgres (asyncpg lanza excepción no capturada). Mismo patrón encontrado preventivamente en `crud.py` (certificados SSL, probablemente no se estaban actualizando) y `routes_import.py`. Fix: `utils_time.py` gana `parse_naive_utc(s)` que siempre devuelve naive sin importar si el string trae `Z` o no. Verificado en vivo con el token del instructor: `200 OK`.

### Experimento revertido: saltar preguntas del panel guiado
Se probó (a pedido del instructor) hacer que el panel guiado abriera directo en la Misión Activa (Terminal+Logs+Firewall), saltando las 3 etapas de opción múltiple. El instructor lo probó conceptualmente y no convenció — "las respuestas en consola no dan mayor claridad para determinar los ataques que se están mitigando". **Revertido con `git revert`**, panel guiado vuelve a las 4 etapas completas, como estaba antes y ya probado.

### Fix real de UX: auto-cierre por inactividad del panel guiado y la bitácora
El instructor reportó que el panel "se desaparece rápido y no da tregua de investigar". Causa real: dos watchdogs de inactividad (`_startBitacoraInactivityWatch`, 1 min sin teclear + 30s countdown → cierre sin guardar; `_startGuidedAutoClose`, mismo mecanismo en pantalla de resultados) se activaban porque investigar un incidente implica pausar de escribir para revisar Terminal/Logs/Firewall — paneles separados — lo cual el watchdog interpretaba como abandono. **Ambas llamadas desactivadas** (funciones no borradas, por si se quiere reactivar con otro umbral).

### Pendiente para mañana (25/26 junio) — acordado con el instructor, no implementado todavía
1. **Aislamiento entre salas colaborativas**: hoy el `node_id`/`attack_type` de un `CollabRoom` es puramente informativo — no hay ninguna restricción técnica que impida que un estudiante de la Sala B detecte/mitigue el incidente "asignado" a la Sala A (la lista de incidentes es global). Diseño acordado: en los endpoints de detectar/mitigar, si el estudiante pertenece a una sala activa, verificar que el incidente sea del nodo de SU sala; filtrar también la lista de incidentes que ve en el frontend. Prioridad alta — el sábado son 4 equipos simultáneos.
2. **Comunicación del instructor por sala**: ya existe `ws_manager.broadcast_to_room(room_id, ...)` en `websocket.py` (usado para el chat/acciones de la sala) — falta solo un endpoint `POST /api/collab/rooms/{room_id}/notify` (instructor-only) que lo reutilice, un input+botón en el panel de gestión de sala, y que el mensaje se muestre destacado en el feed de actividad de los aprendices de esa sala. Bajo riesgo, aprovecha infraestructura existente.

### Comandos de verificación útiles (con token de instructor)
```bash
curl -s https://datacenter-simulator.onrender.com/api/instructor/live-status -H "Authorization: Bearer $TOKEN"
curl -s -X POST https://datacenter-simulator.onrender.com/api/ai/group-report -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"group_id":N}'
curl -s https://datacenter-simulator.onrender.com/api/sessions/report/groups/all -H "Authorization: Bearer $TOKEN"
```

### Commits de la sesión
- `b9a76fe`, `b9ba441` — auditoría manual original (3 hallazgos)
- `844ed41` — segunda pasada de auditoría (auth, XSS, código muerto, ownership)
- `0f8df99` — score NULL defensivo
- `bf05366`, `54ec1bb` — informe grupal con IA + integración Sala Colaborativa
- `d133f8e` — fix regresión crítica live-status 500
- `f5d0fca` / `d6b7652` — experimento panel guiado sin preguntas, revertido
- `f297448` — desactivar auto-cierre por inactividad

### Aprendizajes para recordar
- **Cualquier cambio a serialización de datetime (`iso_utc`) debe revisarse contra TODOS los lugares que parsean ese string de vuelta** — no solo dónde se genera. `parse_naive_utc()` ahora es el helper correcto para esto, úsalo en vez de `datetime.fromisoformat()` suelto en cualquier código nuevo.
- Al cambiar cualquier conteo de etapas/preguntas en el panel guiado, revisar TODOS los lugares con `total_questions`/`total:4` hardcodeado — hoy se encontró que un descuido ahí habría capeado todas las bitácoras a máximo 50 puntos.
- El instructor prefiere cambios reversibles y probados antes de una clase en vivo — cuando algo "no convence" en una prueba conceptual, revertir de inmediato con `git revert` en vez de iterar a contrarreloj.

---

## Sesión 2026-06-21/22 — Auditoría de seguridad

El skill `/security-review` no pudo usarse (sesión anclada a un directorio fuera del repo). Auditoría manual sobre el código real: rutas, auth, manejo de secretos, render de HTML con datos de usuario.

### 🔴 Crítico — Endpoints de IA sin autenticación (CERRADO)
`routes_ai_feedback.py`: los 4 endpoints (`bitacora-feedback`, `terminal-hint`, `collab-hint`, `bitacora-tutor`) no tenían `Depends(get_current_student)` — único archivo de rutas del proyecto con este problema (todos los demás sí exigen login). Cualquiera con la URL podía gastar la clave de Anthropic sin autenticarse, sin límite de tasa en servidor. Fix: agregado el `Depends` a los 4. De paso se encontró y corrigió un bug latente en `index.html`: la llamada a `bitacora-feedback` usaba `localStorage.getItem('dc_token')` (clave equivocada, el token real es `'token'`) — quedaba enmascarado porque el endpoint no pedía auth.

### 🔴 Crítico — Score de bitácora confiado del cliente sin validar (ABIERTO, requiere rediseño)
`routes_bitacoras.py:166`: `base_score = data.score or 0` — el score, correctas, MTTD y hints se guardan tal cual los manda el navegador, sin recalcularse contra el incidente real. Un aprendiz con DevTools puede editar el request y poner `score: 100`. También vuelve evadible la detección de Ctrl+C/Ctrl+V de anoche (`pasted_fields: []` se puede falsear). **Pendiente** — corregirlo bien requiere que el backend recalcule el score desde `incident_id`/sesión guiada en vez de aceptar el valor del cliente; no es un parche de minutos.

### 🟠 Alto — XSS almacenado en reportes del instructor (CERRADO)
`instructor.html`: `printDayReport()` y `generateConsolidatedReport()` interpolaban texto libre de bitácora (síntomas/causa/acciones/lecciones, nombre/email) directo en `win.document.write()` sin `_escapeHtml()`, a diferencia del resto del archivo. Un aprendiz podía inyectar HTML/JS ejecutable en la sesión del navegador del instructor. Fix: todos los campos de texto libre ahora pasan por `_escapeHtml()`.

### 🟡 Medio — SECRET_KEY con valor por defecto hardcodeado (CERRADO)
`jwt_handler.py`: tenía un fallback `"supersecreta_dc_simulator_2024_cambia_esto"` si la variable de entorno faltaba — visible en el código fuente público de GitHub. En Render la variable está bien configurada, pero si se borrara por error la app arrancaría silenciosamente con un secreto conocido (permite forjar tokens de instructor). Fix: la app ahora falla al iniciar (`RuntimeError`) si `SECRET_KEY` no está en el entorno. Verificado que `.env`/`.env.example` ya la definen, no rompe desarrollo local.

### Hallazgos revisados sin problema
- Terminal simulada no ejecuta shell real (sin `subprocess`/`os.system`) — sin riesgo de inyección de comandos
- Sin SQL injection — todo vía SQLAlchemy ORM; los `text(f"...")` usan nombres de tabla hardcodeados
- Contraseñas con bcrypt vía passlib
- CORS bien configurado (deshabilita credentials con wildcard)
- Rutas administrativas exigen `require_instructor`

### Commits sesión
- `b9a76fe` — fix: cerrar 3 hallazgos críticos/altos de auditoría de seguridad

---

## Sesión 2026-06-20/21 — Diagnóstico desde bitácoras reales + 7 fixes

### Origen: análisis de "Bitácoras Consolidadas" y "Reporte del Día" (2026-06-20)
El instructor reportó caos en clase (terminal sin escribir, bitácoras sin guardar, ataques sin disparar) entre 2-3 PM hora Colombia. Los PDFs reales de esa clase revelaron 4 bugs concretos que la revisión de logs de Render (sin errores, CPU pico moderado) no había explicado:

1. **Horas desfasadas ~5h**: bitácoras mostraban 19:27/21:05 en vez de la hora real de Colombia (~14:27). Causa: `datetime.utcnow().isoformat()` sin sufijo `Z` — el navegador interpreta el string como hora LOCAL en vez de UTC.
2. **100% de las sesiones "Activa"/0 min**: cada recarga de página (`initSession()`) creaba una sesión nueva sin cerrar la anterior — confirmado con 8 sesiones huérfanas en una hora para un mismo aprendiz.
3. **MTTD corrupto** (35165s ≈ 9.7h en un aprendiz): un incidente fantasma del scheduler, sin detectar por horas, corrompía el promedio permanentemente.
4. **Mensaje SST/Terminal mezclado**: una bitácora de alarma de incendio quedó etiquetada como `rogue_dhcp` (ataque de red) — confirmó en datos reales el bug de categoría ya sospechado.

### Fixes aplicados

**1. Zona horaria (UTC explícito)**
- `backend/utils_time.py` (nuevo): `iso_utc(dt)` añade `Z` a datetimes naive
- `.isoformat()` reemplazado por `iso_utc()` en ~73 sitios (routes_*, scheduler, engine, attacks, mitigation, pdf_generator)
- `main.py`: parche de `fastapi.encoders.ENCODERS_BY_TYPE[datetime]` para dicts crudos
- `routes_bitacoras.py`: `BitacoraOut.created_at` usa `@field_serializer` (Pydantic v2 ignora el encoder global de FastAPI para modelos `BaseModel` — verificado empíricamente)
- Frontend: `toLocaleTimeString/toLocaleDateString/toLocaleString` fuerzan `timeZone:'America/Bogota'` explícito (34 sitios en `instructor.html` + `index.html`)

**2. Sesiones huérfanas**
- `crud.create_session`: cierra automáticamente cualquier sesión previa activa del mismo estudiante antes de crear una nueva
- `index.html`: handler `pagehide`/`beforeunload` cierra sesión al salir (best-effort, complementa el fix de backend)
- `instructor.html`: usa `sessionInfo.elapsed_min` del backend en vez de recalcular con `Date.now() - new Date(started_at)`, eliminando "En sesión: -295 min"

**3. MTTD corrupto**
- `crud.detect_incident`: cap de `mttd_seconds` a 1800s (30 min) en la fuente

**4. Badge de conexión inconsistente**
- `instructor.html`: monitor en vivo distingue "🔵 Conectado (sin sesión formal)" de "🟢 En sesión"/"⚫ Sin sesión", usando `/api/students/online` (antes el contador de WS conectados no se reflejaba en las tarjetas)

**5. Mensaje SST/Terminal mezclado** (panel guiado)
- `index.html`: el banner de "panel de misión" en Stage 4 ahora distingue categoría SST (protocolo de respuesta) de categorías de red (Terminal→Logs→Firewall) — antes mostraba ambos textos contradictorios para incidentes SST

**6. Detección de Ctrl+C/Ctrl+V + penalización**
- `routes_bitacoras.py`: campo `pasted_fields` en `BitacoraCreate` → penalización -15 pts si se detecta paste en cualquier campo, después de la penalización por calidad textual
- `index.html`: listener global de evento `paste` sobre los 4 textareas, mensaje "🚫 Procedimiento irregular... se te restaron N puntos" al enviar

**7. Tutor IA socrático en bitácora**
- Nuevo endpoint `POST /api/ai/bitacora-tutor`: a diferencia de terminal-hint/collab-hint, NO redacta texto — responde con 1-2 preguntas guía por campo (síntomas/causa/acciones/lecciones) para que el aprendiz piense y escriba con sus propias palabras
- `index.html`: botón "🤖 Pista IA" por campo, cooldown 10s, caja de respuesta en cian

### Verificaciones
- `python -m py_compile` en todos los archivos backend modificados — sin errores
- Test empírico con FastAPI+Pydantic v2 real (`TestClient`) para confirmar que `ENCODERS_BY_TYPE` NO afecta `response_model` con Pydantic v2 (requiere `field_serializer` explícito) — solo 1 campo en todo el backend tenía este patrón (`BitacoraOut.created_at`)
- Sintaxis JS de `instructor.html` e `index.html` verificada con `node -e "new Function(...)"`

### Pendiente / mejora futura
- Detección de paste extendida solo a la bitácora individual (la pieza calificada principal); no cubre aún `sstReportInput` ni los textareas dinámicos de la bitácora colaborativa (`cbInput-*`)
- Revisar en la próxima clase en vivo que las horas se vean correctas y que no reaparezcan sesiones huérfanas

### Commits sesión
- `12859df` — fix: corregir zona horaria UTC, sesiones huérfanas y MTTD corrupto
- `5d76b95` — feat: detección de Ctrl+C/Ctrl+V con penalización + tutor IA socrático en bitácora

---

## Última sesión anterior: 2026-06-17 — netstat fix + AI terminal hint fix

---

## Sesión 2026-06-17 (continuación) — Fixes netstat + IA terminal

### Fix: netstat muestra IP del atacante para todos los tipos de ataque

**Problema:** `netstat -an` en nodos bajo ataque de tipo `vlan_hopping`, `rogue_dhcp`, `dns_spoofing`, `spanning_tree_attack`, `arp_spoofing`, `privilege_escalation`, `data_exfiltration` solo mostraba IPs internas (10.0.x.x). Los 5 tipos originales (dos/ddos/syn_flood/brute_force/port_scan) sí mostraban la IP del atacante.

**Causa raíz (2 archivos):**
1. `backend/simulation/attacks.py` — `_ATTACKER_RANGES` no tenía entradas para los 7 nuevos tipos → `attacker_ip` nunca se asignaba al crear el ataque
2. `backend/simulation/command_engine.py` — `_cmd_netstat()` solo tenía `elif` para los 5 tipos originales

**Fix aplicado:**
- `attacks.py`: agregadas entradas para `arp_spoofing`, `vlan_hopping`, `rogue_dhcp`, `dns_spoofing`, `spanning_tree_attack` (rango 10.0.9.x) y `privilege_escalation`, `data_exfiltration` (rango 10.0.8.x)
- `command_engine.py`: nuevo bloque `elif` para los 7 tipos nuevos — muestra conexiones ESTABLISHED con `attacker_ip` + mensaje de advertencia específico por categoría

**Nota importante:** el fix aplica solo a **ataques nuevos** creados después del deploy. Ataques en curso antes del fix no tienen `attacker_ip` guardado → requiere reiniciar simulador (Pausar + Iniciar desde instructor.html) para ver el efecto.

**Commits:** `a6ee6f3` — fix: netstat shows attacker IP for all new attack types

---

### Fix: IA en terminal no aparecía aunque había ataque activo

**Problema 1:** `aiTerminalEnabled` se consultaba al cargar la página (IIFE async). Si Render estaba desplegando en ese momento, la variable quedaba `false` para toda la sesión — la IA nunca aparecía sin importar el estado real de la API.

**Problema 2:** `activeAttacksMap` era una variable `const` local dentro de `loadLiveStatus()`. La función `_termRunCommand()` no podía accederla, por lo que `attackType` siempre era `''` cuando el panel guiado no estaba abierto.

**Fix:**
- `activeAttacksMap` promovida a variable global (declarada junto a `aiTerminalEnabled`)
- La asignación dentro de `loadLiveStatus()` cambiada de `const` a asignación a la global
- Eliminado el guard `if (attackType && aiTerminalEnabled)` → simplificado a `if (attackType)` (el backend maneja la ausencia de clave silenciosamente)
- Ahora el hint de IA aparece en cian `💡 IA: ...` tan pronto hay ataque en el nodo, sin importar cuándo cargó la página ni si el panel guiado está abierto

**Commits:** `5e58fe5`, `159d67e`

---

## Sesión 2026-06-17 — IA completa: bitácora + terminal + sala colaborativa

### Migración Gemini → Claude API (Anthropic)
- `backend/api/routes_ai_feedback.py` reescrito para usar `POST https://api.anthropic.com/v1/messages`
- Modelo: `claude-haiku-4-5` (más barato y rápido, suficiente para el uso educativo)
- Sin nueva dependencia — usa `httpx` que ya estaba instalado
- Variable de entorno: `ANTHROPIC_API_KEY` (agregada en Render Dashboard)
- `GEMINI_API_KEY` se conserva pero ya no se usa
- **Costo estimado total del ciclo** (19 aprendices, 5-6 sesiones, evaluaciones): ~$1.30 USD
- Precios Haiku 4.5: $1.00/1M tokens entrada, $5.00/1M tokens salida

### Fix: Ataques persisten mientras el aprendiz investiga
- **Problema:** ataques se auto-eliminaban por timeout (ej. SYN Flood en 3 min) antes de que el aprendiz terminara de investigar en terminal/logs/firewall
- **Fix en `backend/simulation/engine.py`** (`tick_attacks()`):
  - Si el ataque tiene `detected=True` → usa `investigation_deadline_sec` (1200s = 20 min) en lugar del `max_duration_sec` original
- **Fix en `backend/api/routes_attacks.py`** (`/incidents/detect`):
  - Al detectar, marca `attack["detected"] = True`, reinicia `elapsed_sec = 0`, establece `investigation_deadline_sec = 1200`
  - También devuelve `attacker_ip` en el response para que el frontend lo muestre

### IP del atacante visible en panel guiado
- `_openGuidedPanel` ahora acepta parámetro `attackerIp`
- Guardado en `guidedState.attackerIp`
- Stage 2 "Analizar" (categoría red) muestra badge naranja: **"IP sospechosa detectada: 203.0.113.X (bloquear en Firewall)"**
- Flujo correcto: Detectar → ver IP en Stage 2 → ir al terminal a confirmar → bloquear en firewall

### IA en Terminal
- Nuevo endpoint `POST /api/ai/terminal-hint`
  - Recibe: `command`, `output`, `attack_type`, `node_id`
  - Solo responde a comandos de diagnóstico: `netstat`, `ps`, `top`, `tcpdump`, `ss`, `iptables`, `cat`, `tail`, `grep`, `df`, `free`
  - Devuelve pista máx. 20 palabras — guía sin dar la respuesta directa
- Frontend: después de cada comando, si hay ataque activo y IA disponible, llama al endpoint
- Output en terminal en **cyan**: `💡 IA: Busca conexiones desde rangos 203.x.x.x — no pertenecen a la red interna.`
- Variable `aiTerminalEnabled` inicializada al cargar (consulta `/api/ai/bitacora-feedback/status`)

### IA en Sala Colaborativa
- Nuevo endpoint `POST /api/ai/collab-hint`
  - Recibe: `question`, `attack_type`, `node_id`
  - Responde máx. 3 oraciones educativas — no da la respuesta directa
- Frontend: `sendCollabChat()` detecta mensajes que empiezan con `@IA` o `?`
  - Envía el mensaje del aprendiz normalmente
  - Luego llama al endpoint y publica la respuesta como `🤖 IA: ...` en el chat de la sala
  - Visible para **todos** los miembros en tiempo real vía WebSocket
- Ejemplo de uso: `@IA ¿por qué hay tantas conexiones en SYN_RECV?`

### Commits sesión 2026-06-17
- `4d08996` — fix: switch AI feedback from Gemini to Claude Haiku, show attacker IP in guided panel
- `7f5dd78` — fix: attacks persist while student is actively investigating
- `f653542` — feat: add AI hints in terminal during active incidents
- `991ceae` — feat: add AI assistant in collaborative room
- `a6ee6f3` — fix: netstat shows attacker IP for all new attack types
- `5e58fe5` — fix: AI terminal hint fires even without guided panel open
- `159d67e` — fix: remove aiTerminalEnabled gate so AI hint always fires

### Variables de entorno en Render
- `ANTHROPIC_API_KEY` — clave API de Anthropic (console.anthropic.com, cuenta Google de Lubeto)
- `GEMINI_API_KEY` — conservada, ya no se usa activamente

---

## Última sesión anterior: 2026-06-16 (cierre) — SST flow fix + 10 nuevos tipos de ataque

---

## Sesión cierre 2026-06-16 — SST flow fix + Catálogo de ataques expandido

### Fix: Flujo SST vs Red — separación definitiva
- `_NETWORK_ATTACKS` y `_SST_ATTACKS` definen qué tipo de incidente es qué
- Ataques SST (humo, temperatura, biometría, etc.) ya NO llevan al estudiante a terminal/firewall
- `_missionActivate` pre-rellena `termDone/iocDone/fwDone=true` para SST
- Widget de misión muestra pasos adaptados: "panel guiado → protocolo → bitácora → confirmar"
- `_missionTick('verify')` no requiere `fwApplied` para SST
- `showGuidedResults()` llama automáticamente a `_missionTick('verify')` al terminar el panel guiado

### 10 nuevos tipos de ataque (backend + frontend)
**Seguridad Física (SST — panel guiado, sin terminal):**
- `biometric_bypass` — huella/retina clonada, acceso físico con biometría falsificada
- `tailgating` — persona no autorizada entra siguiendo a empleado legítimo
- `badge_cloning` — tarjeta RFID duplicada ilegalmente
- `cctv_tampering` — sabotaje de cámaras de seguridad

**Red Interna (flujo terminal + firewall):**
- `vlan_hopping` — salto entre VLANs sin autorización via 802.1Q doble encapsulación
- `rogue_dhcp` — servidor DHCP falso redirige tráfico interno
- `dns_spoofing` — envenenamiento de caché DNS
- `spanning_tree_attack` — manipulación del protocolo STP para tomar Root Bridge

**Amenaza Interna / Insider Threat (flujo terminal + firewall):**
- `privilege_escalation` — usuario/proceso obtiene permisos root sin autorización
- `data_exfiltration` — transferencia masiva de datos a destino externo no autorizado

Cada nuevo ataque incluye: catálogo completo (`attacks.py`), reglas de mitigación con comandos reales (`mitigation.py`), clasificación en `_isNetworkAttack()` y `_gCategory()` en el frontend.

### Commits sesión cierre
- `2fc0fbf` — fix: SST alerts skip terminal/firewall, go direct to guided panel
- `32b73ad` — feat: add 10 new attack types (biometric, internal network, insider threat)

---

## FASE 3 — Sala Colaborativa ✅ COMPLETADA + POST-FIXES (2026-06-16)

### Sesión nocturna 2026-06-16 — Fixes y mejoras adicionales

#### Bitácora Colaborativa (nueva)
- Modelo `CollabBitacora`: una fila por sala, secciones por rol (t1_sintomas, t2_causa, resp_acciones, com_lecciones)
- Migración automática en `main.py`: `CREATE TABLE IF NOT EXISTS collab_bitacoras`
- Rutas: `GET/PATCH /api/collab/rooms/{id}/bitacora` + `GET /api/collab/bitacoras` (instructor)
- Modal en panel del estudiante: botón **📋 Bitácora** en header → abre las 4 secciones
- Sección propia editable, secciones de compañeros en solo lectura
- WS event `collab_bitacora_updated` notifica a toda la sala en tiempo real cuando alguien guarda
- Bitácora se marca ✅ Completa cuando los 4 roles han guardado

#### Fix: SST panel parpadeando
- `_sstLastFull` cachea los 12 sensores desde `handleMetrics`
- `handleSSTAlert` hace merge (no replace) de alertas sobre la lista completa
- El panel SST ya no colapsa a 1 sensor cuando hay un Critical

#### Fix: Alertas del sistema no mostraba SST
- `_addSSTAlertToPanel()` agrega sensores críticos/warning al panel de alertas
- Botón **"✓ Atender"** (antes decía "Atendido") — cambia a verde al hacer clic y desaparece
- `_updateAlertCount()` mantiene el contador sincronizado

#### Fix: Internal Server Error en múltiples rutas
- Causa: `collab_room_id` en modelo ORM pero columna no existía en PostgreSQL
- Fix: `ALTER TABLE bitacoras ADD COLUMN IF NOT EXISTS collab_room_id` al arrancar
- Afectaba: Monitor Individual, Calidad Textual de Bitácoras, Reportes Evaluativos

#### Manual del estudiante actualizado
- Nueva sección **Sala Colaborativa** con: roles paso a paso, flujo de equipo 8 pasos,
  tabla de acciones automáticas, guía de bitácora por rol

#### Commits sesión nocturna
- `6264eb9` — Iter 6+7: vistas por rol + auto-log acciones
- `6f785c3` — Iter 8+9: collab_room_id en bitácora + reporte sala
- `e5121f2` — fix: migración collab_room_id + undefined en incidentes
- `39b4582` — docs: sección Sala Colaborativa en manual estudiante
- `3317618` — fix: SST no parpadea + alertas SST en panel alertas
- `65deb5e` — fix: botón Atender (no Atendido)
- `e106d2b` — feat: bitácora colaborativa completa

---

## FASE 3 — Sala Colaborativa ✅ COMPLETADA (2026-06-16)

### Plan acordado (8 iteraciones — 2 días)

**Día 1 — Backend + DB**
- Iter 1: modelos + migración (tablas `collab_rooms`, `collab_members`, `collab_actions`)
- Iter 2: CRUD + rutas `/api/collab/`
- Iter 3: WebSocket rooms (join/leave/broadcast por sala — extender ws_manager existente)

**Día 2 — Frontend + Roles** ✅
- Iter 4: modal crear sala (instructor asigna estudiantes y roles) ✅
- Iter 5: UI estudiante → ver sala asignada + rol propio ✅
- Iter 6+7: chat en tiempo real + vistas por rol + auto-log de acciones técnicas ✅
  - `_ROLE_CONFIG` abre drawer correspondiente (logs/fw) al entrar a la sala
  - `#cpRoleBanner` muestra guía contextual por rol
  - `fwBlockIp`/`fwBlockPort` → `postCollabAction('block_ip'/'block_port')` si hay sala activa
  - `_termRunCommand` detecta `systemctl restart` → publica en log de sala
- Iter 8: bitácora individual incluye `collab_room_id` si estudiante está en sala ✅
- Iter 9: reporte instructor — tabla sala | miembros+roles | acciones | tiempo activo ✅

### Roles definidos
| Rol | Panel principal |
|---|---|
| T1-Monitor | Métricas en tiempo real |
| T2-Analista | Logs + Terminal |
| Responder | Firewall + Terminal |
| Comunicador | Resumen del incidente + chat |

### Decisiones técnicas
- Chat: WebSocket broadcast filtrado por `room_id` (no canal global)
- Bitácora: reutilizar tabla `bitacoras` existente + campo `collab_room_id` (nullable)
- Instructor crea sala desde `instructor.html`, asigna roles manualmente
- Roles no bloquean acceso a otras pestañas — solo definen el panel que se muestra por defecto

---

### Sesión 2026-06-15 — Parte 2 (tarde)

#### Manual del Estudiante (`frontend/manual-estudiante.html`)
- Nuevo archivo standalone accesible en `/manual-estudiante` (o abriendo el HTML directo)
- Sidebar navegable con scroll-spy
- Cubre 5 sesiones de clase: DoS/DDoS/SYN Flood, Brute Force/Port Scan, Memory Leak/Disk Failure, SST (thermal/smoke/acceso físico), SSL/TLS
- Por cada ataque: síntomas, comandos de terminal con salidas reales, respuestas del panel guiado (4 fases), qué escribir en la bitácora
- Tabla de referencia rápida: proceso ps aux + mensaje syslog por tipo de ataque
- Guía del instructor: cómo detectar cuándo se lanzó un ataque, compatibilidad ataque/nodo
- Sistema de puntaje: MTTD, bitácora, panel guiado, pistas usadas

#### Scheduler — Más actividad (`backend/simulation/scheduler.py`)
- Intervalo entre ataques auto: 2-7 min → **1-3 min**
- Máximo de ataques simultáneos: 1 → **2** (configurable vía `AUTO_ATTACK_MAX_CONCURRENT`)
- `render.yaml` actualizado con las 3 nuevas variables: `AUTO_ATTACK_MIN_INTERVAL_MIN=1`, `AUTO_ATTACK_MAX_INTERVAL_MIN=3`, `AUTO_ATTACK_MAX_CONCURRENT=2`
- Para clase: cambiar `MAX_CONCURRENT` a 3 desde Render Dashboard → Environment sin redeploy

#### Commits sesión parte 2
- `f14ef66` — feat: más actividad en dashboard + manual estudiante HTML

---

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
