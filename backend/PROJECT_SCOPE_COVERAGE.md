# Matriz de cobertura del proyecto

Fuente funcional: `ProyectoDual_ITESCAM_CadenaDeReposteria-1(8).pdf`, páginas 1–2; se leyó el texto y se inspeccionó el diagrama visual de la página 2. Fuente técnica: ZIP `cadena-reposteria-backend-work(1).zip` y esquema SQL adjunto. La instrucción actual sustituye pagos de pasarela por registro y verificación manual; no se introduce una integración externa ficticia.

“Implementado y probado” se limita al backend y entornos aislados descritos en TEST_RESULTS.md. No significa aceptación de usuarios, integración de frontend ni validación de producción.

| Requisito del PDF | Estado | Implementación / endpoints | Evidencia y límite |
|---|---|---|---|
| Administración centralizada de información | Implementado y probado | Arquitectura FastAPI/SQLAlchemy conservada; 92 operaciones | Regresión completa, imports, OpenAPI y Uvicorn; producción pendiente |
| Venta en tienda física | Implementado y probado | `modules/sales`, `/ventas`, empleado/sucursal/detalles/precio servidor | `tests/commercial/test_workflows.py`; carreras PostgreSQL |
| Venta en línea desde aplicación móvil | Implementado parcialmente | `/mis-pedidos`, `/pagos`, `/ventas` propias; contratos para Flutter | Flujo backend hasta entrega probado; aplicación móvil no desarrollada en esta tarea |
| Seleccionar/sugerir sucursal más cercana | Implementado y probado | `/sucursales-cercanas`; selección explícita en pedido | Coordenadas sintéticas y ausencia de coordenadas probadas; distancia geodésica, sin geocodificador ni cobertura de reparto |
| Recoger en sucursal | Implementado y probado | Pedido con sucursal, estados PREPARANDO/LISTO/ENTREGADO | Flujo HTTP de cliente y empleado; sin módulo logístico adicional |
| Registro de cliente: nombre, teléfono, correo | Implementado y probado | `/auth/register`, `/mi-perfil`, clientes | Cuenta+perfil atómicos, roles y propiedad probados |
| Dirección del cliente para sugerir sucursal | Implementado parcialmente | `direccion_entrega` opcional del pedido; proximidad con latitud/longitud proporcionadas por consumidor | No existe domicilio persistente en clientes ni conversión automática dirección→coordenadas; selección explícita disponible |
| Transacción comercial ligada a venta | Implementado y probado | Pedido→venta única→pago→ticket/factura | Idempotencia, monto exacto, estados y stock probados |
| Tickets | Implementado y probado | `modules/tickets`, generación/consulta/HTML imprimible | Unicidad, propiedad, importes históricos, estado de pago y escape HTML |
| Medios de pago: efectivo | Implementado y probado | Pagos manuales EFECTIVO | Registro y confirmación por personal; sin cobro automatizado |
| Medios de pago: tarjeta bancaria | Implementado y probado | Código TARJETA, referencia de terminal física | Registra operación autorizada externamente; no procesa tarjetas ni almacena PAN/CVV |
| SPEI y depósito (ampliación solicitada) | Implementado y probado | SPEI/DEPOSITO pendientes hasta verificación | Métodos, reintento, rechazo, cancelación, permisos e idempotencia |
| Datos para factura: RFC, tipo de persona, razón social, domicilio, CP, CFDI, correo | Implementado y probado | `modules/invoices`, POST `/facturas` | Validación básica, propiedad, pago previo, historial, estados; no valida identidad fiscal ante SAT |
| Generación fiscal oficial de factura | Pendiente de integración externa | Se registran solicitudes y evidencia de documentos emitidos fuera del sistema | No PAC, timbrado, verificación SAT ni envío de documentos por correo |
| Productos y actualización de inventario por sucursal | Implementado y probado | CRUD existentes e inventarios, entradas/salidas/ajustes/traspasos | Pruebas originales conservadas; reservas/cancelación y concurrencia ampliadas |
| Administración de sucursales | Implementado y probado | CRUD protegido existente y proximidad | Pruebas funcionales y restricciones de sucursal |
| Visibilidad de transacciones y rotación de inventario | Implementado y probado | Historial comercial y `/reportes/movimientos`, stock, ventas, pagos | Datos SQL reales, sin estadísticas simuladas; no contabilidad fiscal |
| Reportes de ingresos semanales/mensuales | Implementado y probado | `/reportes/pagos?solo_confirmados=true` con intervalo; ventas agrupables y dashboard | Totales y exclusión de pendientes/reembolsados; zona horaria PostgreSQL probada |
| Reporte de sucursales con mayor/menor venta mensual | Implementado y probado | `/reportes/ventas?agrupacion=sucursal` con desde/hasta | Orden SQL `orden=total_desc/total_asc` antes de paginar; prueba de ranking entre sucursales |
| Productos más/menos solicitados por sucursal/mes | Implementado y probado | `/reportes/productos`, `menos_vendidos=true`, fecha y sucursal | Agregaciones y ceros de catálogo; mide ventas confirmadas, excluye pedidos no pagados |
| Reportes por día, semana, mes, año, empleado y dashboard (ampliación) | Implementado y probado | `modules/reports` | Agregaciones SQL y filtros; exclusión de clientes/empleados de reportes |
| Integración de APIs externas | Pendiente de integración externa | Backend no introduce llamadas sin proveedor configurado | Supabase vía PostgreSQL se conserva; pasarelas excluidas por instrucción; PAC/correo/geocodificación futuros |
| Sistema web y móvil alojado en la nube | Implementado parcialmente | Backend compatible con Angular/Flutter, guía de configuración | No frontend ni despliegue automático; operación cloud y seguridad real pendientes de validación |

## Estado inicial y cobertura por módulo

| Módulo | Estado inicial comprobado | Operaciones iniciales | Trabajo realizado |
|---|---|---|---|
| Autenticación | JWT, Argon2id, RBAC y rate limiting | Registro/login | Perfil cliente atómico y sesión `/auth/me`; se conserva autenticación |
| Usuarios | CRUD administrativo y protecciones de administrador | Listar/consultar/crear/editar/desactivar/reactivar | Conservado; regresión ejecutada |
| Clientes | CRUD y acceso propio limitado | Listar/consultar/crear/editar/desactivar/reactivar | Perfil de cuentas antiguas y vínculo seguro de registro |
| Empleados | CRUD administrativo y sucursal | Listar/consultar/crear/editar/desactivar/reactivar | Conservado; usado para responsable de venta |
| Productos | Catálogo y CRUD administrativo | Seis operaciones | Conservado; precios se obtienen del servidor |
| Categorías | CRUD administrativo | Seis operaciones | Conservado |
| Sucursales | CRUD administrativo con coordenadas opcionales | Seis operaciones | Proximidad real agregada |
| Inventarios | Nueve operaciones, movimientos y bloqueos | Listar/detalle/movimientos/crear/mínimo/entrada/salida/ajuste/traspaso | Reserva física y cancelación reutilizan repositorio |
| Pedidos | Cinco operaciones sólo personal, reserva y estados | Listar/id/número/crear/estado | Coordinador transaccional; pedidos propios, historial, pago obligatorio |
| Ventas | Tabla SQL, sin módulo HTTP | Ninguna | Módulo físico, consulta, cancelación, expiración e idempotencia |
| Pagos | Tablas SQL, sin módulo HTTP | Ninguna | Pagos manuales completos, consulta, verificación, trazabilidad |
| Tickets | Tabla SQL, sin módulo HTTP | Ninguna | Ticket único, consulta e impresión HTML |
| Facturación | Tabla SQL, sin módulo HTTP | Ninguna | Solicitud administrativa, datos fiscales y referencias externas |
| Reportes | Sin módulo de reportes | Ninguna | Ventas/pagos/stock/movimientos/dashboard y filtros |

No se agregan CRUD innecesarios para `payment_events`, horarios o galería de imágenes: existen como estructuras de referencia, pero no son necesarios para los casos de uso especificados. No se eliminaron esas tablas ni módulos anteriores. En la auditoría inicial se detectó que el ZIP no contenía `.env.example`; se agregó una plantilla pública sin secretos.

## Verificaciones pendientes que impiden afirmar “todo el sistema terminado”

Validación de Supabase real y sus políticas, migración y ensayo en staging real, configuración del rol y credenciales, conciliación de registros históricos, ejecución programada de expiraciones, validación de reglas de devoluciones posteriores a entrega, política fiscal/impuestos, PAC/correo, y pruebas de interfaz con Angular/Flutter. La entrega completa la implementación local solicitada, con estas dependencias claramente separadas.
