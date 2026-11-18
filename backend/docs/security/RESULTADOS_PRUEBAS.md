# Resultados reales de pruebas y verificaciones

## Ejecución final

```text
Python 3.14.10 / Linux
1104 passed, 1 warning in 52.71s
Fallidas: 0
Errores: 0
Omitidas: 0
```

Se ejecutó la suite completa con `RUN_POSTGRES_INTEGRATION_TESTS=1` y `TEST_DATABASE_URL` apuntando exclusivamente a una base PostgreSQL 16.2 local desechable llamada `reposteria_audit_test`. Las pruebas funcionales usan sus propias bases SQLite; la autenticación nueva se prueba con JWT firmado y ORM reales.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=pytest-results.xml
```

Para reproducir los cuatro casos PostgreSQL y obtener cero omitidas, usa la preparación local de `WINDOWS.md`. Sin activarlos se omiten explícitamente: no se usan credenciales de producción como alternativa.

## Comparación

| Ejecución | Python | Aprobadas | Fallidas/errores | Omitidas | Advertencias | Tiempo |
|---|---|---:|---:|---:|---:|---:|
| ZIP original | 3.13.5 | 770 | 0 | 1 | 1 | 42.49 s |
| Primera suite corregida, escenarios existentes | 3.14.10 | 770 | 0 | 1 | 1 | 45.44 s |
| Nuevas pruebas de seguridad iniciales | 3.14.10 | 315 | 0 | 0 | 1 | 7.38 s |
| PostgreSQL aislado | 3.14.10 | 4 | 0 | 0 | 0 | 0.55 s |
| Suite final, con ampliaciones adicionales | 3.14.10 | 1,104 | 0 | 0 | 1 | 52.71 s |

Los tiempos de suites parciales no deben sumarse para deducir el tiempo total. La comparación original/final utilizó versiones distintas de Python; no se presenta como benchmark de rendimiento.

## Advertencia conservada

```text
StarletteDeprecationWarning:
Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

La genera `fastapi/testclient.py` con Starlette 1.7.0 y HTTPX 0.28.1. Se mantiene HTTPX porque es la tecnología existente solicitada; no se silencia la advertencia ni se elimina ninguna prueba. Se puede evaluar una actualización compatible por separado.

## Cobertura añadida

- Las 52 operaciones privadas, cada una con ausencia de JWT, token inválido, expirado y usuario desactivado: 208 casos.
- Denegación vertical a empleados/clientes en operaciones administrativas.
- Lectura, filtros, escritura y movimientos de sucursales ajenas; asignaciones inexistentes o inactivas.
- Consulta/actualización del cliente propio, denegación del ajeno y campos de vinculación protegidos.
- Operaciones reales de administrador y empleado, catálogo de activos y registro/login de clientes.
- Rechazo de campos de actor, precio, total o privilegios no permitidos.
- Integridad de entradas, salidas, reserva y cancelación; repetición de cancelación y stock insuficiente.
- Rate limiting, IP falsificada en headers, fallo cerrado del almacenamiento y respuestas sin secretos.
- Configuración insegura, IDs JWT extremos, roles desconocidos, esquemas de autenticación incorrectos y errores inesperados.
- Tres casos nuevos PostgreSQL: refresco de stock precargado; dos pedidos simultáneos sin sobreventa; estado de pedido precargado sin reposición doble. Se conserva y ejecuta la prueba original de UPSERT concurrente del rate limiting.

## Verificaciones complementarias

- Inicio real de Uvicorn y solicitudes HTTP locales: `/`, `/health`, `/docs`, `/openapi.json` devuelven 200; `/clientes` sin JWT devuelve 401.
- Importación de todos los módulos de aplicación sin credenciales Supabase.
- Comparación del contrato: los 56 pares método/ruta y las declaraciones originales de respuestas 2xx permanecen.
- Todas las funciones de prueba originales existen todavía; los cuatro archivos de revisiones Alembic son idénticos byte por byte.
- Dependencias instaladas compatibles (`uv pip check`), conservando los pins de producción y añadiendo pytest para desarrollo.
- Aplicación local de la cadena Alembic sobre esquema sintético; head y current coinciden en `974e270dd2f1`.
- Rol propuesto NOBYPASSRLS validado en una transacción local revertida: usuarios, bloqueo de rol, secuencias/identidades, inventarios, pedidos y UPSERT. No se concede lectura de ventas, DELETE de usuarios ni UPDATE de alembic_version.

## Evidencia incluida

- `evidence/final-pytest.txt` y `evidence/final-pytest.xml`: salida completa y JUnit final.
- `evidence/baseline.txt` y `evidence/baseline.xml`: ejecución original.
- `evidence/compatibility.txt`: importaciones, rutas, contratos, preservación e inicio HTTP.
- `evidence/alembic-bootstrap.txt`: recorrido real de las cuatro migraciones locales.
- `evidence/least-privilege.txt`: prueba local de mínimos privilegios propuesta.
- `evidence/postgres.txt` y `evidence/postgres.xml`: integración PostgreSQL.
- `evidence/before-probes.txt`: reproducciones HTTP previas con servicios aislados.
- `evidence/endpoints-before.json`, `endpoints-after.json`, `openapi-before.json`, `openapi-after.json`: inventario y contrato antes/después.

## No ejecutado y límites

No se ejecutaron consultas ni migraciones en Supabase real; tampoco pruebas de carga, penetración externa, integración Angular/Flutter, despliegue, rotación de secretos ni los comandos sobre Windows. No se afirma que los esquemas SQLite reproduzcan concurrencia PostgreSQL: esa propiedad tiene pruebas separadas reales. El rol propuesto debe validarse adicionalmente contra las políticas, permisos heredados y funciones existentes en staging.
