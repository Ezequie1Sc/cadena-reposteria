# PostgreSQL y Supabase: propuesta revisable

## Qué quedó comprobado

El código original conecta SQLAlchemy con `DATABASE_URL`. El diagnóstico proporcionado por el usuario reporta `postgres` con `rolbypassrls=true`: RLS puede estar habilitado en todas las tablas y no limitar las consultas de esa conexión. Esto **no demuestra un ataque ni una filtración**. No se accedió a Supabase durante esta auditoría.

Las rutas antiguas de roles y salud de base usaban además `supabase-py`; ahora ambas utilizan la sesión SQLAlchemy existente. El cliente heredado se conserva de manera opcional y diferida. No hay cambio automático de credencial.

Se verificaron localmente SQLAlchemy 2.1.4, psycopg 3.3.6, PostgreSQL 16.2 y Alembic 1.20.0. En una base sintética basada en el TXT se ejecutó la cadena de cuatro migraciones. Se comprobó por separado un rol `NOBYPASSRLS` con RLS habilitado, inserciones con identidad, bloqueos, usuarios, inventarios, pedidos y rate limiting. Esto no certifica compatibilidad con las políticas, funciones, pooler o privilegios reales del proyecto Supabase.

## Archivos propuestos

- `scripts/sql/inspect_database_security.sql`: consultas de solo lectura sobre roles, propietarios, RLS, políticas, grants, membresías, funciones y revisión Alembic.
- `scripts/sql/propose_app_role.sql`: rol nuevo `reposteria_app`, inicialmente **NOLOGIN**, sin superusuario, creación de roles/bases, replicación ni BYPASSRLS. Termina en **ROLLBACK** y no contiene contraseña.
- `scripts/check_db_security.py`: diagnóstico de conexión, superusuario, BYPASSRLS y propiedad de tablas con RLS no forzado.

La propuesta no altera políticas existentes ni concede acceso a `anon` o `authenticated`; propone políticas adicionales exclusivamente para el rol backend. Se requiere que RLS ya esté habilitado en cada tabla afectada; de lo contrario aborta. Si el rol o las políticas con esos nombres ya existen, también aborta en vez de sobreescribirlos.

## Permisos de la propuesta

| Objetos | Permisos directos |
|---|---|
| roles | SELECT y UPDATE únicamente de `id` para el `SELECT FOR UPDATE` que protege al último administrador |
| usuarios, clientes, empleados, sucursales, categorias, productos, inventarios, pedidos, auth_rate_limits | SELECT, INSERT, UPDATE |
| detalle_pedidos, movimientos_inventario | SELECT, INSERT |
| Secuencias propiedad de tablas insertables enumeradas | USAGE |
| ventas, pagos, tickets, facturas y restantes módulos no implementados | Ninguno |
| alembic_version | Ninguno para ejecución normal |

No se otorga DELETE, TRUNCATE, propiedad, privilegios globales sobre tablas/secuencias ni permisos por defecto para futuras tablas. El borrado de contadores antiguos deberá ejecutarse mediante mantenimiento separado; no se amplió el permiso de aplicación para facilitarlo.

**Alcance de RLS propuesto:** las políticas autorizan las filas necesarias para una única cuenta backend. No ofrecen aislamiento por cliente/sucursal dentro de PostgreSQL. El JWT propio de FastAPI no se transforma automáticamente en `auth.uid()` ni en el rol `authenticated`. La autorización por usuario permanece en FastAPI. Un compromiso de la credencial de aplicación todavía permitiría acceder a todas las filas concedidas. Para RLS por usuario se requiere diseñar contexto transaccional, verificar su no falsificación y probar el pool de conexiones; no se simuló esa protección.

## Secuencia recomendada, pendiente del responsable de la base

1. Obtener un respaldo y preparar staging independiente. Revisar el script de diagnóstico antes de ejecutarlo. Confirmar IDs y nombres `1=Administrador`, `2=Empleado`, `3=Cliente`, estado activo y vinculaciones empleados/sucursal y clientes/usuario.
2. Confirmar columnas `clientes.activo`, `empleados.activo`, tabla `auth_rate_limits` y revisión `974e270dd2f1`. El TXT no incluye esos cambios. No deducir políticas ni grants del SQL de referencia.
3. Revisar grants heredados de `PUBLIC`, privilegio CREATE del esquema, funciones `SECURITY DEFINER`, EXECUTE público, membresías, políticas restrictivas y políticas TO PUBLIC. Un rol nuevo hereda privilegios de PUBLIC aun con NOINHERIT. No afirmar mínimos privilegios efectivos sin esta comprobación. Revisar vistas/RPC expuestas por la Data API y secretos `service_role` en frontend o configuraciones externas, a los que no se tuvo acceso.
4. Ejecutar la propuesta únicamente en staging inicialmente. Su ROLLBACK final evita persistencia; para aplicar un cambio aprobado, revisar y sustituirlo por COMMIT. No cambiar políticas reales automáticamente.
5. Aprovisionar por separado una credencial LOGIN segura para la cuenta aprobada, mediante el procedimiento del DBA/proveedor. No escribirla en el SQL ni en Git. Confirmar conexión directa/pooler y formato del usuario con Supabase; no asumir que basta con sustituir el nombre en una URL.
6. Probar con esa conexión todos los permisos de la matriz y las operaciones críticas. Confirmar TLS, preferentemente verificación de certificado y nombre de host, según conexión soportada. El código no reemplaza opciones de TLS ni `DATABASE_URL` existentes.
7. Guardar la credencial de DDL únicamente en el entorno de migraciones (`MIGRATION_DATABASE_URL`). No montarla en el proceso web. La opción conserva compatibilidad: si falta, Alembic sigue usando `DATABASE_URL`; en producción debe establecerse explícitamente en el trabajo de migraciones.
8. Tras revisión y pruebas en staging, planificar por separado el cambio de `DATABASE_URL` del backend y reiniciar sus pools. Esta auditoría no ejecuta ese cambio, despliegues ni rotación de secretos. Para revertir una migración de credencial, restablecer la configuración anterior autorizada; no borrar tablas ni datos.
9. Confirmar que Angular/Flutter consumen FastAPI. Sus JWT propios no son JWT Supabase Auth. Si no existe uso legítimo de Data API, evaluar deshabilitarla o retirar grants de roles públicos mediante un cambio independiente y revisado. Cero avisos del Security Advisor no demuestra RBAC correcto en FastAPI.

## Límites operativos pendientes

Configurar proxies de confianza por direcciones concretas para que Uvicorn interprete IP real; nunca confiar indiscriminadamente en `X-Forwarded-For`. El código toma `request.client.host`; se probó que variar ese header directamente no evita el límite. Revisar límites de cuerpo de solicitud, concurrencia, timeouts y tasa general en el reverse proxy. El límite de autenticación usa ventanas persistentes de 60 s (30/IP, 5/IP+correo) y registro 5/IP/hora; un proxy mal configurado puede agrupar usuarios bajo una IP.

Fuentes primarias consultadas:
- https://www.postgresql.org/docs/17/ddl-rowsecurity.html
- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/api/securing-your-api
- https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html
