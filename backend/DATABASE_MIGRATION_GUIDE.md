# Guía de migraciones y Supabase

No se conectó ni se escribió en Supabase de producción. Las verificaciones se realizaron en PostgreSQL 16.2 local aislado.

## Estado y orden

Se preservan literalmente las cuatro migraciones anteriores:

1. `404a9071350b`: baseline del esquema preexistente, no crea las tablas comerciales.
2. `3539360e0e34`: activo en clientes.
3. `3e1f48ffb80f`: activo en empleados.
4. `974e270dd2f1`: contadores de autenticación.
5. Nueva `b27a913c6d02`: flujos comerciales manuales.

La nueva revisión presupone las tablas del SQL de referencia. **Una base vacía no puede inicializarse únicamente con `alembic upgrade head`**, porque el baseline original es un no-op. Para una base de desarrollo nueva, un operador debe restaurar sólo el esquema aprobado o aplicar el SQL de referencia a una base desechable. No usar `metadata.create_all()` para instalar producción ni generar un autogenerate indiscriminado.

## Cambios aditivos

- `ventas.vence_at` nullable; no asigna vencimientos a históricos.
- `detalle_ventas.producto_nombre` y `producto_sku` nullable, para snapshots nuevos.
- `pagos.confirmado_por`, FK a usuarios; históricos no reciben un confirmador inventado.
- Datos fiscales nullable para históricos: código postal, régimen, tipo de persona, dirección, correo.
- `historial_comercial` y `operaciones_idempotentes`, sus índices y restricciones.
- Índice único parcial de un pago activo por venta; índices de vencimiento e ingresos.
- Inserta únicamente DEPOSITO si no existe en `metodos_pago`, sin cambiar IDs ni desactivar métodos anteriores.
- Habilita RLS exclusivamente en las dos tablas nuevas. No cambia políticas de tablas existentes.

Si existen varios pagos activos de una venta, la creación del índice falla y la transacción se revierte. No se borran ni corrigen registros automáticamente. No se implementa downgrade destructivo: la revisión lo rechaza para preservar trazabilidad comercial.

## Antes de aplicar posteriormente

1. Respaldar base completa y comprobar una restauración independiente. Registrar versión de aplicación, revision Alembic y configuración. Respaldo por un DBA, sin compartir contraseñas en chats ni incluirlas en el ZIP.
2. Ejecutar `scripts/commercial_preflight.sql` como lectura autorizada. Comprobar duplicados activos, pagos aprobados inconsistentes, métodos activos y columnas reales. Comparar con el SQL y con las políticas RLS actuales, que no están incluidas íntegramente en el adjunto.
3. Probar la migración y todos los flujos en una restauración aislada, sin acceso externo de aplicaciones. Conciliar registros históricos ambiguos con el responsable de negocio.
4. Mantener credenciales separadas: `DATABASE_URL` para aplicación; `MIGRATION_DATABASE_URL` para Alembic. No sustituir la conexión actual antes de probar los permisos y SSL/pooler correspondientes al entorno.
5. Revisar `scripts/sql/propose_app_role.sql`. Su ROLLBACK final es deliberado: propuesta, no instalación. Ahora cubre ventas, pagos, tickets, facturas y tablas de historial. Conserva NOLOGIN/NOBYPASSRLS y evita DELETE, TRUNCATE y DDL. Sólo el operador autorizado puede decidir provisionar credenciales y aplicar cambios revisados.
6. Revisar privilegios heredados de PUBLIC, funciones expuestas, anon/authenticated y configuración Data API en Supabase. Las políticas backend de la propuesta no interpretan JWT propios de FastAPI; la autorización de negocio permanece en la API.

## Comandos de revisión en PowerShell

Desde la raíz del backend y con un entorno de prueba configurado:

```powershell
.\.venv\Scripts\Activate.ps1
python -m alembic heads
python -m alembic history --verbose
python -m alembic upgrade 974e270dd2f1:b27a913c6d02 --sql | Set-Content -Encoding utf8 .\commercial-migration-review.sql
```

`heads`, `history` y generación offline no modifican la base. `current` se conecta a la credencial de migración configurada:

```powershell
python -m alembic current
```

Sólo después de respaldo, revisión y ensayo satisfactorio, el operador puede configurar **la URL de la base aislada** y aplicar allí:

```powershell
$env:MIGRATION_DATABASE_URL = "postgresql+psycopg://migration_local:local_example_password@127.0.0.1:5432/reposteria_dev"
python -m alembic upgrade head
python -m alembic current
```

No se da aquí autorización automática para aplicar sobre producción. Para una aplicación posterior real, establecer ventana de mantenimiento: los índices y ALTER TABLE pueden bloquear escrituras. El backend actualizado requiere la migración antes de servir tráfico.

## Verificación posterior

Comprobar head `b27a913c6d02`, índice `uq_pago_activo_venta`, las columnas anteriores y RLS en tablas nuevas. Probar autenticación, registro/perfil, venta, pago, ticket, solicitud fiscal, pedido, devolución y reportes en el entorno aislado. Validar que el rol de aplicación no pueda modificar `alembic_version` ni borrar historial. Programar la expiración de reservas y monitorear errores/409.

Los pedidos históricos abiertos sin venta asociada se vinculan al registrar su primer pago: se copian importes existentes sin tocar de nuevo stock. Pedidos históricos ENTREGADO/CANCELADO requieren conciliación externa; no se generan cobros retrospectivos automáticamente. Facturas previas no reciben datos fiscales supuestos.

Si se revierte una publicación, volver al código previo mientras se conservan las columnas aditivas puede ser una opción técnica, pero no ejecutar el código previo con tráfico comercial nuevo sin revisar coherencia. Preferir una corrección hacia adelante. Restaurar respaldo implica pérdida potencial de operaciones posteriores y requiere un procedimiento administrativo explícito.
