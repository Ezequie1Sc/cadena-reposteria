# Resumen de modificaciones

Se trabaja sobre los archivos originales, conservando sus módulos, rutas y reglas de negocio. No se eliminó ningún archivo original. El manifiesto CSV incluye estado y SHA-256 anterior/final de cada archivo de código, pruebas y configuración. Los documentos nuevos de `docs/security/` se enumeran por separado.

## Decisiones técnicas

- Dependencias por operación, reutilizando CurrentUser/AdminUser/StaffUser. Esto protege también routers montados en otra aplicación.
- Helpers de propiedad y sucursal en permissions.py; recursos de sucursal inmutable comprobados antes de llamar a los servicios. Las asignaciones permanecen bloqueadas durante la transacción.
- Catálogos de solo activos para usuarios no administradores; administración global de clientes restringida por falta de un vínculo de sucursal en el esquema.
- `populate_existing=True` con FOR UPDATE para actualizar el estado ORM después de esperar bloqueos.
- Handler de validación que conserva localización y mensaje pero omite los valores de entrada; errores SQL e inesperados genéricos.
- Configuración defensiva, CORS explícito y migración con credencial opcional separada sin reescribir DATABASE_URL.
- Roles/salud pasan a SQLAlchemy; cliente Supabase heredado se conserva y se crea solo al solicitarlo.
- Tests funcionales anteriores conservados. Los tests unitarios de rutas incluyen actor autorizado; las nuevas pruebas de seguridad ejercitan autenticación y ORM reales.
- No se añade una migración: el cierre de acceso es de aplicación. Las cuatro revisiones anteriores permanecen idénticas.

## Cambios de comportamiento necesarios

Solicitudes sin JWT ahora reciben 401 en las operaciones privadas. Usuarios autenticados sin rol/ámbito reciben 403. Un cliente solo consulta/edita su ficha activa; no reasigna usuario_id. Empleados sin asignación activa no operan pedidos/inventario. Los campos extra de entrada se rechazan con 422. Las contraseñas nuevas de registro conservan espacios. La documentación HTTP se deshabilita en staging/production. Los errores 422 ya no devuelven input/ctx. Los contratos de éxito se conservaron.

Se conserva el registro como creación de usuario Cliente; la ficha clientes se vincula por administración. No se implementa autoservicio de pedidos. Los consumidores frontend deberán incorporar el JWT donde falte; no se editaron sus proyectos.

## Archivos

Conteo (sin documentos/evidencias): 14 creados, 38 modificados, 88 conservados.

### Modificados

- `.gitignore`
- `alembic/env.py`
- `app/api/routes/auth.py`
- `app/api/routes/health.py`
- `app/api/routes/roles.py`
- `app/core/auth.py`
- `app/core/config.py`
- `app/core/jwt.py`
- `app/core/login.py`
- `app/core/permissions.py`
- `app/core/supabase.py`
- `app/db/models.py`
- `app/db/session.py`
- `app/main.py`
- `app/modules/auth/registration_schemas.py`
- `app/modules/branches/routes.py`
- `app/modules/categories/routes.py`
- `app/modules/customers/routes.py`
- `app/modules/customers/schemas.py`
- `app/modules/employees/routes.py`
- `app/modules/inventory/repository.py`
- `app/modules/inventory/routes.py`
- `app/modules/inventory/schemas.py`
- `app/modules/orders/repository.py`
- `app/modules/orders/routes.py`
- `app/modules/orders/schemas.py`
- `app/modules/products/routes.py`
- `app/modules/users/schemas.py`
- `requirements.txt`
- `scripts/check_db_security.py`
- `tests/api/test_inventory.py`
- `tests/api/test_orders.py`
- `tests/branches/test_branch_routes.py`
- `tests/categories/test_category_routes.py`
- `tests/customers/test_customer_api.py`
- `tests/employees/test_employee_routes.py`
- `tests/integration/test_auth_rate_limit_postgresql.py`
- `tests/products/test_product_routes.py`

### Creados

- `.env.example`
- `README.md`
- `app/core/errors.py`
- `requirements-dev.txt`
- `scripts/sql/inspect_database_security.sql`
- `scripts/sql/propose_app_role.sql`
- `tests/conftest.py`
- `tests/integration/conftest.py`
- `tests/integration/test_stock_concurrency.py`
- `tests/security/__init__.py`
- `tests/security/conftest.py`
- `tests/security/legacy_seed.py`
- `tests/security/test_hardening.py`
- `tests/security/test_http_security.py`

### Conservados

- `alembic.ini`
- `alembic/README`
- `alembic/script.py.mako`
- `alembic/versions/3539360e0e34_add_activo_column_to_clientes.py`
- `alembic/versions/3e1f48ffb80f_add_employee_active_status.py`
- `alembic/versions/404a9071350b_baseline_existing_supabase_schema.py`
- `alembic/versions/974e270dd2f1_add_authentication_rate_limits.py`
- `app/__init__.py`
- `app/api/__init__.py`
- `app/api/routes/__init__.py`
- `app/core/__init__.py`
- `app/core/rate_limit.py`
- `app/core/security.py`
- `app/db/__init__.py`
- `app/modules/__init__.py`
- `app/modules/auth/rate_limit_model.py`
- `app/modules/auth/rate_limit_repository.py`
- `app/modules/auth/registration_service.py`
- `app/modules/branches/__init__.py`
- `app/modules/branches/model.py`
- `app/modules/branches/repository.py`
- `app/modules/branches/schemas.py`
- `app/modules/branches/service.py`
- `app/modules/categories/__init__.py`
- `app/modules/categories/model.py`
- `app/modules/categories/repository.py`
- `app/modules/categories/schemas.py`
- `app/modules/categories/service.py`
- `app/modules/customers/__init__.py`
- `app/modules/customers/model.py`
- `app/modules/customers/repository.py`
- `app/modules/customers/service.py`
- `app/modules/employees/__init__.py`
- `app/modules/employees/model.py`
- `app/modules/employees/repository.py`
- `app/modules/employees/schemas.py`
- `app/modules/employees/service.py`
- `app/modules/inventory/__init__.py`
- `app/modules/inventory/model.py`
- `app/modules/inventory/service.py`
- `app/modules/orders/__init__.py`
- `app/modules/orders/model.py`
- `app/modules/orders/service.py`
- `app/modules/products/__init__.py`
- `app/modules/products/model.py`
- `app/modules/products/repository.py`
- `app/modules/products/schemas.py`
- `app/modules/products/service.py`
- `app/modules/users/__init__.py`
- `app/modules/users/model.py`
- `app/modules/users/repository.py`
- `app/modules/users/routes.py`
- `app/modules/users/service.py`
- `app/shared/__init__.py`
- `app/shared/models/__init__.py`
- `app/shared/models/role_reference.py`
- `app/shared/models/user_reference.py`
- `pytest.ini`
- `tests/__init__.py`
- `tests/api/test_auth.py`
- `tests/api/test_customer_registration.py`
- `tests/api/test_users.py`
- `tests/branches/test_branch_repository.py`
- `tests/branches/test_branch_schemas.py`
- `tests/branches/test_branch_service.py`
- `tests/categories/test_category_repository.py`
- `tests/categories/test_category_schemas.py`
- `tests/categories/test_category_service.py`
- `tests/core/test_auth.py`
- `tests/core/test_connection.py`
- `tests/core/test_jwt.py`
- `tests/core/test_login.py`
- `tests/core/test_models.py`
- `tests/core/test_permissions.py`
- `tests/customers/test_customer_repository.py`
- `tests/customers/test_customer_service.py`
- `tests/employees/__init__.py`
- `tests/employees/fixtures.py`
- `tests/employees/test_employee_repository.py`
- `tests/employees/test_employee_schemas.py`
- `tests/employees/test_employee_service.py`
- `tests/inventory/__init__.py`
- `tests/inventory/test_inventory_service.py`
- `tests/orders/__init__.py`
- `tests/orders/test_order_service.py`
- `tests/products/test_product_schemas.py`
- `tests/products/test_product_service.py`
- `tests/users/test_user_service.py`

## Documentación creada

- `AUDITORIA.md`
- `MANIFIESTO_ARCHIVOS.csv`
- `MATRIZ_ENDPOINTS.csv`
- `MATRIZ_ENDPOINTS.md`
- `PULL_REQUEST.md`
- `RESULTADOS_PRUEBAS.md`
- `SUPABASE.md`
- `WINDOWS.md`
- `CAMBIOS.md`
- `evidence/`: salidas y contratos antes/después.
