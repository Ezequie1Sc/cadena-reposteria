# Propuesta de Pull Request

**Rama:** `fix/backend-security-rbac-branch-scope`

**Título:** `fix(security): proteger endpoints y restringir operaciones por usuario y sucursal`

## Descripción

Las rutas de catálogo, clientes y empleados permitían operaciones sin JWT; inventarios y pedidos comprobaban el rol de personal pero no la sucursal. Este cambio protege las operaciones privadas con la autenticación existente, limita escrituras administrativas y valida el ámbito de cada recurso. Por ejemplo, una entrada de inventario de otra sucursal ahora devuelve 403 y no modifica existencias.

Se conservan las 56 operaciones HTTP únicas y sus contratos de éxito. Se elimina el registro redundante de `GET /roles`. Los bloqueos de inventarios/pedidos refrescan el estado ORM para evitar trabajar con existencias o estados precargados antes de una modificación concurrente.

## Cambios

- JWT y roles efectivos en todas las operaciones privadas; validación de usuario/rol activo.
- Empleados con asignación activa limitados a su sucursal; clientes limitados a su ficha vinculada.
- Administración exclusiva para usuarios, empleados, roles y mutaciones del catálogo; restricciones de campos sensibles.
- Errores sin entrada sensible; configuración JWT/debug/CORS validada y contraseñas de registro preservadas exactamente.
- Roles/salud mediante SQLAlchemy; cliente Supabase heredado opcional.
- Credencial opcional de migraciones separada y registro de modelos existentes omitidos por Alembic.
- Tests aislados, plantilla de entorno, reglas de exclusión y documentación de privilegios PostgreSQL.

## Validación

- Python 3.14.10: **1,104 passed, 0 failed, 0 skipped, 1 warning in 52.71 s**.
- Cuatro pruebas con PostgreSQL 16.2 local, incluyendo concurrencia real.
- Propuesta NOBYPASSRLS probada con RLS en base sintética; transacción revertida.
- Cadena Alembic original comprobada localmente hasta `974e270dd2f1`.
- Conservación de rutas, respuestas de éxito, funciones de prueba y archivos de migraciones anteriores.

La advertencia corresponde a Starlette TestClient con HTTPX y no se ha ocultado.

## Compatibilidad y seguridad

Los consumidores deben enviar JWT en rutas ahora privadas. Las lecturas de catálogo están limitadas a activos para empleados/clientes. La administración global de clientes queda restringida al administrador, ya que no existe pertenencia de clientes a sucursales en el esquema. Pedidos continúa siendo un módulo de personal; no se habilita autoservicio comercial nuevo.

No incluye cambios de producción, despliegue, rotación de credenciales ni aplicación de políticas RLS. El SQL es revisable y termina en ROLLBACK. Revisar datos, configuración, privilegios heredados y políticas reales en staging antes de modificar `DATABASE_URL`. La credencial de migraciones debe quedar fuera del proceso web.
