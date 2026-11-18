# Ejecución en Windows / PowerShell

La entrega no contiene `.env`, credenciales, cachés ni entorno virtual. Trabajar inicialmente en una copia nueva. Los comandos de esta guía no despliegan ni modifican Supabase.

## Extraer y crear entorno

Desde la carpeta que contiene el ZIP:

```powershell
Expand-Archive -Path .\cadena-reposteria-backend-final.zip -DestinationPath .\backend-entrega
Set-Location .\backend-entrega\cadena-reposteria-backend-final
py -3.14 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip check
```

Se verificó Python 3.14.10 en Linux. Los comandos PowerShell están preparados para Windows, pero no se ejecutaron en un equipo Windows durante esta entrega.

## Configuración local

```powershell
Copy-Item .env.example .env
$jwtLocalSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
$envText = Get-Content .env -Raw
$envText = $envText.Replace('REEMPLAZAR_CON_UN_SECRETO_ALEATORIO_GENERADO_LOCALMENTE', $jwtLocalSecret)
[System.IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $envText, [System.Text.UTF8Encoding]::new($false))
Remove-Variable jwtLocalSecret
code .env
```

En `.env`, configurar **una base local o de staging autorizada**, no producción para pruebas. La plantilla usa localhost y credenciales ilustrativas. No publicar el archivo. No configurar SUPABASE_KEY para los módulos comerciales: usan SQLAlchemy/psycopg. `tzdata` ya está declarada para las zonas horarias en Windows.

## Pruebas portables

```powershell
python -m pytest -q
```

Pytest fuerza una DATABASE_URL no conectable y credenciales JWT sintéticas; las pruebas portables usan bases SQLite aisladas. Sin habilitar PostgreSQL, las pruebas de integración correspondientes se omiten deliberadamente. No usar datos de producción.

## Suite completa con PostgreSQL local desechable (Docker opcional)

Requiere Docker Desktop instalado y ejecutándose. Estos comandos crean un contenedor nuevo sólo para pruebas:

```powershell
$testDbPassword = python -c "import secrets; print(secrets.token_hex(24))"
docker run --name reposteria-tests --rm -d -p 127.0.0.1:55449:5432 -e "POSTGRES_PASSWORD=$testDbPassword" -e POSTGRES_DB=reposteria_audit_test postgres:16
docker exec reposteria-tests pg_isready -U postgres -d reposteria_audit_test
```

Continuar cuando `pg_isready` indique que acepta conexiones:

```powershell
$env:RUN_POSTGRES_INTEGRATION_TESTS = '1'
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:${testDbPassword}@127.0.0.1:55449/reposteria_audit_test"
python -m pytest -q --junitxml=pytest-results.xml
Remove-Item Env:RUN_POSTGRES_INTEGRATION_TESTS
Remove-Item Env:TEST_DATABASE_URL
Remove-Variable testDbPassword
docker stop reposteria-tests
```

Sólo se acepta localhost y el nombre exacto `reposteria_audit_test`. Las pruebas crean esquemas aleatorios, siembran datos sintéticos y los eliminan al terminar. No apuntar TEST_DATABASE_URL a otra base. El contenedor anterior no se reutiliza como base de desarrollo persistente.

## Migraciones y arranque

Antes de iniciar operaciones comerciales, seguir `DATABASE_MIGRATION_GUIDE.md`: se necesita el esquema original y la nueva migración. El baseline no inicializa una base vacía. No ejecutar upgrades sobre producción sin revisión independiente.

```powershell
python -m alembic heads
python -m alembic history --verbose
# Lectura de la base configurada; comprobar antes la URL de migraciones:
python -m alembic current
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

En otra consola:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Start-Process http://127.0.0.1:8000/docs
Invoke-WebRequest http://127.0.0.1:8000/openapi.json -OutFile openapi-local.json
```

Swagger sólo se habilita en desarrollo/test con DOCS_ENABLED=true. `GET /health/database` exige JWT de administrador. El script preexistente `scripts/bootstrap_admin.py` crea una cuenta real en la base configurada si se ejecuta; no fue ejecutado en esta tarea y debe usarse sólo tras revisar la conexión y necesidad administrativa.
