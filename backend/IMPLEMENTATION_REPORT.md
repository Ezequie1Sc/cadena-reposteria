# Informe de implementación — Cadena de Repostería

Se trabajó directamente sobre `cadena-reposteria-backend-work(1).zip`, conservando su arquitectura modular, módulos, dependencias y migraciones anteriores. Se implementaron los flujos comerciales locales solicitados, sin cambios en Supabase real ni despliegue.

## Resultado verificable

- **92 operaciones HTTP**: las 56 originales conservadas y 36 nuevas; 88 privadas con JWT y 4 públicas.
- **1317 pruebas aprobadas, 0 fallidas, 0 omitidas y 1 advertencia**, 77.74 segundos, Python 3.14.10 y PostgreSQL 16.2 aislado.
- Nueva migración aditiva `b27a913c6d02`; las cuatro migraciones anteriores se preservan byte por byte.
- Pruebas reales de stock, pagos e idempotencia concurrentes; smoke test Uvicorn y Swagger.
- Propuesta de rol de aplicación extendida y verificada en PostgreSQL aislado con RLS/NOBYPASSRLS. No se cambió DATABASE_URL ni credenciales reales.

## Estado inicial y fuentes

El ZIP inicial tenía 56 operaciones, los módulos de autenticación, usuarios, clientes, empleados, categorías, productos, sucursales, inventarios y pedidos, pero no módulos HTTP para ventas, pagos, tickets, facturas ni reportes. La ejecución inicial produjo 1100 aprobadas, 4 omitidas y 1 advertencia en 126.06 s. El único cambio de código identificado respecto a la entrega auditada previa era el script de bootstrap de administrador; se conservó como venía, sin ejecutarlo.

El PDF oficial, incluyendo el diagrama de la página 2, definió venta física/en línea, sucursal cercana, transacciones, facturación, inventarios y reportes. El SQL ya incluía tablas comerciales: se mapearon y reutilizaron. El esquema no se consideró prueba de políticas RLS vigentes. El ZIP recibido no traía `.env.example`; se agregó una plantilla sin secretos reales.

## Funcionalidad implementada

| Área | Resultado |
|---|---|
| Ventas | Mostrador, empleado/sucursal, precios del servidor, stock, detalle histórico, filtros, idempotencia, cancelación y expiración |
| Pagos | Efectivo, SPEI, depósito y terminal física; registro pendiente, verificación manual, rechazo/cancelación, un pago activo completo, confirmador e historial |
| Pedidos | Rutas propias del cliente, perfil vinculado, venta única asociada, pago previo a preparación/entrega, cancelación autorizada e historial |
| Tickets | Folio único, importes históricos, consulta autorizada y HTML imprimible con estado de pago real |
| Facturación | Solicitud y datos fiscales, evidencia externa de emisión/cancelación, permisos e historial; no timbrado |
| Reportes | Agregaciones SQL de ventas, pagos, productos, inventario, movimientos y dashboard; filtros y zonas horarias |
| Integración | `/auth/me`, OpenAPI, matriz de autorización y guía Angular/Flutter; sin cambiar frontend |

## Arquitectura y consistencia

Se mantienen `app/api`, `app/core`, `app/db`, `app/modules`, `app/shared`, Alembic, scripts y tests. Los módulos nuevos separan modelos, esquemas, repositorios, servicios y rutas. El coordinador comercial de pedidos integra el servicio existente con ventas/pagos, permitiendo `commit=False` para una transacción única. El inventario reutiliza el repositorio existente y sus bloqueos ordenados.

La venta es la referencia única para pagos/ticket/factura. Un pedido reserva stock una sola vez; crear su venta no lo descuenta de nuevo. Bloqueos de filas, refresco de entidades e índices únicos protegen concurrencia. Historial y claves idempotentes se confirman con la operación; rollback revierte también los movimientos. Los detalles de reglas, estados y supuestos están en COMMERCIAL_RULES.md.

## Compatibilidad y cambios necesarios

Las rutas y métodos anteriores se conservan, al igual que sus esquemas de respuesta. Registro público ahora crea también el perfil cliente. Los pedidos administrativos mantienen su cuerpo/contrato; pueden enviar Idempotency-Key opcional. Las nuevas creaciones comerciales relevantes exigen esa cabecera.

Para proteger integridad, preparar/entregar pedidos ahora exige pago completo aprobado. Cancelar una operación pagada requiere administrador y referencia de devolución real; pedidos entregados no se cancelan por este flujo. No se aceptan nuevas compras con importe cero. Los pedidos históricos finalizados y ventas históricas sin reserva verificable requieren conciliación, no una reposición automática basada en supuestos. Esos cambios se documentan para el frontend y el operador.

Ninguna funcionalidad anterior se eliminó. Las pruebas antiguas sólo se actualizaron donde el registro ahora usa la tabla de clientes y donde creció el número de endpoints; se conservaron todas las funciones y escenarios existentes. La documentación de auditoría previa permanece en `docs/security/` como evidencia histórica, no como estado actual.

## Base de datos y seguridad

La migración agrega columnas nullable compatibles con históricos, tablas de historial/idempotencia e índices, y el método DEPOSITO. RLS se habilita en las dos tablas nuevas. No borra ni reescribe históricos, no modifica políticas existentes ni ejecuta acciones remotas. El downgrade automático se rechaza para evitar perder trazabilidad. DATABASE_MIGRATION_GUIDE.md explica revisión, respaldo, conflictos, ejecución posterior y verificación.

Se conservan JWT/Argon2id, rol y usuario activos, RBAC, controles propios/sucursal, CORS explícito y rate limiting. Los errores internos no se devuelven al cliente. Los tickets escapan HTML y no contienen scripts. Las entradas prohíben asignación arbitraria de importes/estados/roles y campos de tarjeta. No se detectaron secretos reales en el paquete; los valores de prueba son sintéticos y la plantilla requiere generar un secreto local.

## Riesgos y pendientes reales

- Supabase real: privilegios, políticas RLS, Data API, SSL/pooler y registros históricos no se verificaron; requieren staging/revisión del operador.
- Aplicar la migración y provisionar el rol/credenciales posteriormente, con respaldo y pruebas. No se publicaron cambios.
- Programar la expiración de reservas; el endpoint funciona, pero ningún scheduler se instaló. Hasta ejecutarlo, las reservas vencidas retienen stock.
- PAC/timbrado, validación fiscal y correo externos pendientes; los tickets no son CFDI.
- Sin tasa fiscal configurada: no se inventa un desglose de impuestos.
- Proximidad requiere coordenadas existentes; no se convierte una dirección en geolocalización ni se promete reparto.
- Devoluciones posteriores a entrega y conciliación histórica requieren decisiones/proceso administrativo adicional.
- Angular, Flutter, Windows real, carga prolongada y despliegue cloud pendientes de validación específica.

## Archivos de código modificados

- `app/api/routes/auth.py`
- `app/db/models.py`
- `app/main.py`
- `app/modules/auth/registration_service.py`
- `app/modules/orders/routes.py`
- `app/modules/orders/schemas.py`
- `app/modules/orders/service.py`
- `scripts/sql/propose_app_role.sql`
- `tests/api/test_customer_registration.py`
- `tests/security/test_http_security.py`

## Archivos de código creados

- `alembic/versions/b27a913c6d02_commercial_workflows.py`
- `app/modules/branches/proximity_routes.py`
- `app/modules/customers/self_routes.py`
- `app/modules/inventory/commercial.py`
- `app/modules/invoices/__init__.py`
- `app/modules/invoices/model.py`
- `app/modules/invoices/repository.py`
- `app/modules/invoices/routes.py`
- `app/modules/invoices/schemas.py`
- `app/modules/invoices/service.py`
- `app/modules/orders/commercial_service.py`
- `app/modules/orders/customer_routes.py`
- `app/modules/payments/__init__.py`
- `app/modules/payments/model.py`
- `app/modules/payments/repository.py`
- `app/modules/payments/routes.py`
- `app/modules/payments/schemas.py`
- `app/modules/payments/service.py`
- `app/modules/reports/__init__.py`
- `app/modules/reports/repository.py`
- `app/modules/reports/routes.py`
- `app/modules/reports/schemas.py`
- `app/modules/reports/service.py`
- `app/modules/sales/__init__.py`
- `app/modules/sales/model.py`
- `app/modules/sales/repository.py`
- `app/modules/sales/routes.py`
- `app/modules/sales/schemas.py`
- `app/modules/sales/service.py`
- `app/modules/tickets/__init__.py`
- `app/modules/tickets/model.py`
- `app/modules/tickets/repository.py`
- `app/modules/tickets/routes.py`
- `app/modules/tickets/schemas.py`
- `app/modules/tickets/service.py`
- `app/shared/commerce.py`
- `app/shared/commerce_models.py`
- `scripts/commercial_preflight.sql`
- `tests/commercial/__init__.py`
- `tests/commercial/conftest.py`
- `tests/commercial/test_access_and_validation.py`
- `tests/commercial/test_workflows.py`
- `tests/integration/test_commerce_concurrency.py`

## Inventario completo de cambios

`FILE_MANIFEST.csv` clasifica cada archivo como creado, modificado o conservado con SHA-256. Incluye también documentación y evidencia; no se eliminaron archivos del ZIP de origen. `.gitignore`, dependencias y scripts no afectados se conservan. `.env.example` es nuevo. Las nuevas guías de raíz y README apuntan al estado actual.

## Endpoints agregados

| Método | Ruta |
|---|---|
| GET | `/auth/me` |
| GET | `/facturas` |
| GET | `/facturas/{invoice_id}` |
| GET | `/facturas/{invoice_id}/historial` |
| GET | `/mis-pedidos` |
| GET | `/mis-pedidos/{order_id}` |
| GET | `/mis-pedidos/{order_id}/historial` |
| GET | `/pagos` |
| GET | `/pagos/metodos` |
| GET | `/pagos/{payment_id}` |
| GET | `/pagos/{payment_id}/historial` |
| GET | `/pedidos/{order_id}/historial` |
| GET | `/reportes/dashboard` |
| GET | `/reportes/inventarios` |
| GET | `/reportes/movimientos` |
| GET | `/reportes/pagos` |
| GET | `/reportes/productos` |
| GET | `/reportes/ventas` |
| GET | `/sucursales-cercanas` |
| GET | `/tickets` |
| GET | `/tickets/{ticket_id}` |
| GET | `/tickets/{ticket_id}/imprimir` |
| GET | `/ventas` |
| GET | `/ventas/{sale_id}` |
| GET | `/ventas/{sale_id}/historial` |
| PATCH | `/facturas/{invoice_id}/estado` |
| PATCH | `/pagos/{payment_id}/estado` |
| POST | `/facturas` |
| POST | `/mi-perfil` |
| POST | `/mis-pedidos` |
| POST | `/mis-pedidos/{order_id}/cancelar` |
| POST | `/pagos` |
| POST | `/tickets/venta/{sale_id}` |
| POST | `/ventas` |
| POST | `/ventas/expirar` |
| POST | `/ventas/{sale_id}/cancelar` |

La matriz completa con roles y restricciones está en ENDPOINT_AUTHORIZATION.md. TEST_RESULTS.md contiene pruebas, advertencia y limitaciones. WINDOWS_SETUP.md incluye comandos PowerShell completos y PULL_REQUEST.md la propuesta de rama/PR.
