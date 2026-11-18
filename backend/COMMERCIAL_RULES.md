# Reglas comerciales y decisiones de implementación

## Una operación, una fuente de pago

Una venta contiene los importes históricos y los detalles. Un pedido tiene como máximo una venta asociada mediante `ventas.pedido_id UNIQUE`. Los pagos siempre referencian esa venta; `POST /pagos` permite indicar `pedido_id` para resolver la asociación transaccionalmente. Tickets y facturas apuntan a la misma venta. No se utilizan `payment_events`, webhooks ni proveedores de pagos externos en esta etapa.

El importe total se calcula en el servidor usando `Decimal` y precios del catálogo. No se admiten precios, descuentos, usuario confirmador ni estados arbitrarios desde el cliente. Los pagos nuevos son MXN, proveedor INTERNO y PENDIENTE. Los únicos métodos admitidos son EFECTIVO, SPEI, DEPOSITO y TARJETA (terminal física). OXXO y proveedores históricos permanecen en la base, sin ofrecerse en el nuevo flujo.

## Reservas e inventario

- Venta física: descuenta existencias al crear la reserva y registra movimiento VENTA. Reserva de 30 minutos.
- Pedido: conserva el descuento de existencias existente, movimiento SALIDA/PEDIDO. Reserva de 24 horas. La venta asociada copia importes y nunca vuelve a descontar inventario.
- Pago aprobado: convierte la venta a CONFIRMADA sin afectar stock; confirma el pedido pendiente.
- Pago rechazado o cancelado: conserva la reserva hasta su vencimiento/cancelación. Se permite registrar otro intento completo; no pagos parciales.
- Cancelación comercial: repone las cantidades una sola vez, cancela pagos pendientes y registra historial. No elimina registros.
- Venta pagada: sólo administrador, con referencia de una devolución completa ya realizada manualmente. El pago pasa a REEMBOLSADO. La API no envía dinero.
- Pedido entregado: no se cancela por este flujo. Una devolución posterior a entrega requiere una política y módulo específicos, no se finge una devolución logística.
- Factura EMITIDA registrada: exige registrar previamente su cancelación externa antes de cancelar la venta.
- Abandono: `/ventas/expirar` cancela reservas pendientes vencidas por lotes de hasta 100. **Debe programarse periódicamente por el operador** con una cuenta administradora. No hay un proceso de fondo instalado ni despliegue automático. Hasta que se ejecute, el stock sigue reservado; la confirmación de pagos vencidos ya está bloqueada.
- El vencimiento automático no se inventa para ventas históricas: `vence_at` es nullable. Esas ventas se bloquean para registro/aprobación de nuevos pagos y cancelación con reposición de stock hasta una conciliación administrativa fuera de esta API: el SQL no demuestra cómo se descontaron sus existencias. No se crea una vía que permita inventar reservas históricas.

## Estados

| Recurso | Transiciones |
|---|---|
| Venta | PENDIENTE → CONFIRMADA al aprobar pago; PENDIENTE → CANCELADA; CONFIRMADA → CANCELADA con devolución administrativa documentada |
| Pago manual | PENDIENTE → APROBADO / RECHAZADO / CANCELADO; APROBADO → REEMBOLSADO únicamente junto con cancelación comercial administrativa |
| Pedido | PENDIENTE → CONFIRMADO por pago; CONFIRMADO → PREPARANDO → LISTO → ENTREGADO; estados anteriores a ENTREGADO → CANCELADO con reglas de venta |
| Solicitud de factura | PENDIENTE → EMITIDA al registrar evidencia externa; PENDIENTE/EMITIDA → CANCELADA; estados finales no se reabren |

Confirmar nuevamente o repetir una transición devuelve 409. El cliente sólo cancela su pedido PENDIENTE, sin pago aprobado. Un empleado opera en su sucursal activa; el administrador gestiona globalmente. La preparación/entrega requiere pago aprobado también en las rutas administrativas anteriores. Este endurecimiento de la regla anterior es intencional.

## Transacciones y concurrencia

El coordinador comercial usa los servicios/repositorios existentes y una única transacción. El servicio de pedidos admite `commit=False` para participar sin confirmar a mitad del flujo; su valor predeterminado conserva compatibilidad de llamadas internas existentes. Las rutas HTTP usan el coordinador comercial. La reserva física reutiliza el repositorio de inventarios para bloqueos, actualización y movimientos.

Los bloqueos se toman en orden pedido → venta → pago → inventarios por ID. Se refresca el mapa de identidad de SQLAlchemy al bloquear. Las creaciones idempotentes se serializan por fila de usuario; una restricción UNIQUE sobre usuario/operación/clave complementa el bloqueo. El índice parcial `uq_pago_activo_venta` impide varios pagos PENDIENTE, EN_PROCESO o APROBADO de una venta. Un fallo hace rollback de importe, stock, pago, evento y clave.

`Idempotency-Key` es obligatoria en ventas, pagos, solicitudes de factura y pedidos del cliente. Se conserva el resultado por usuario y operación; reintento con la misma clave y cuerpo devuelve el mismo recurso, con su estado actual. Otro cuerpo con esa clave devuelve 409. No se borran claves automáticamente. La cabecera es opcional en el POST administrativo de pedidos para mantener clientes antiguos; se recomienda migrarlos a enviarla. Sin clave, esa ruta anterior conserva su semántica de crear un nuevo pedido por solicitud.

## Supuestos conservadores

- Venta con importe positivo; no promociones gratuitas, descuentos arbitrarios ni anticipos.
- Administrador identifica un empleado activo de la sucursal para la venta física; empleado no suplanta otro empleado.
- Retiro en sucursal conforme al PDF. `direccion_entrega` conserva datos opcionales; no promete reparto, tarifas ni cobertura.
- Proximidad geodésica por coordenadas existentes. Sin coordenadas se omite esa sucursal en la búsqueda cercana y permanece disponible la selección explícita. No se infiere ubicación de una dirección de texto.
- No hay configuración fiscal de impuestos por producto en el esquema. No se agrega una tasa inventada ni se recalculan precios; ticket muestra impuestos no desglosados. La configuración tributaria y timbrado real quedan fuera del comprobante comercial.
- Solicitud fiscal valida formato básico y datos requeridos, no acredita situación fiscal SAT. EMITIDA significa que un administrador registró UUID, proveedor, referencia y fecha de un documento emitido externamente. No timbra, verifica con SAT ni envía correo.
- Reportes de ventas consideran ventas CONFIRMADA. Ingresos consideran pagos APROBADO y ventas CONFIRMADA, por `paid_at`. Cancelaciones y reembolsos se excluyen de ingresos/ventas netas incluso al consultar períodos históricos; el historial conserva el momento y responsable. No sustituye contabilidad fiscal ni cierre de caja.
- `clientes_registrados` del dashboard es global, aunque se filtre una sucursal, porque clientes no tienen una sucursal asignada.
- Datos de tarjeta/CVV/credenciales no son campos aceptados. Referencias deben contener exclusivamente identificadores operativos, nunca información bancaria sensible.

Referencias técnicas: [SQLAlchemy: transacciones](https://docs.sqlalchemy.org/en/21/orm/session_basics.html), [PostgreSQL: bloqueos](https://www.postgresql.org/docs/16/explicit-locking.html). La evidencia ejecutada está en `docs/implementation/evidence/`.
