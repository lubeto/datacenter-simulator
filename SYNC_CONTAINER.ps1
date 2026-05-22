# SYNC_CONTAINER.ps1
# Sincroniza los archivos fuente actualizados al contenedor Docker activo
# Ejecutar desde: D:\Documentos\Lubeto\datacenter-simulator\

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Sincronizando fuentes -> contenedor..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$src = "D:\Documentos\Lubeto\datacenter-simulator"
$cnt = "dc-monitoring-simulator"

# Backend
docker cp "$src\backend\database\models.py"           "${cnt}:/app/backend/database/models.py"
docker cp "$src\backend\database\crud.py"              "${cnt}:/app/backend/database/crud.py"
docker cp "$src\backend\api\routes_analytics.py"       "${cnt}:/app/backend/api/routes_analytics.py"
docker cp "$src\backend\api\routes_students.py"        "${cnt}:/app/backend/api/routes_students.py"
docker cp "$src\backend\simulation\scheduler.py"       "${cnt}:/app/backend/simulation/scheduler.py"
docker cp "$src\backend\simulation\mitigation.py"      "${cnt}:/app/backend/simulation/mitigation.py"

# Frontend
docker cp "$src\frontend\index.html"       "${cnt}:/app/frontend/index.html"
docker cp "$src\frontend\login.html"       "${cnt}:/app/frontend/login.html"
docker cp "$src\frontend\instructor.html"  "${cnt}:/app/frontend/instructor.html"

Write-Host ""
Write-Host "Archivos copiados. Creando tablas DB..." -ForegroundColor Yellow

# Crear tablas nuevas (practice_sessions)
docker exec $cnt python -c "
import asyncio, sys
sys.path.insert(0, '/app')
async def run():
    from backend.database.db import engine, Base
    from backend.database import models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('DB tables OK')
asyncio.run(run())
"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " SYNC COMPLETO. Recarga con Ctrl+Shift+R" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
