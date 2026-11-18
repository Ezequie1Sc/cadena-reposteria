# Integración con Angular 22 y Flutter

No se modificó frontend. La API conserva las 56 operaciones anteriores y agrega operaciones documentadas en `ENDPOINT_AUTHORIZATION.md` y `docs/implementation/openapi.json`. Base local: `http://127.0.0.1:8000`. Swagger `/docs` en desarrollo; deshabilitado en staging/production según configuración.

## Autenticación y sesión

```http
POST /auth/login
Content-Type: application/json

{"email":"usuario@example.com","password":"contraseña introducida por el usuario"}
```

Respuesta 200: `{"access_token":"<JWT>","token_type":"bearer"}`. Enviar `Authorization: Bearer <JWT>` en rutas privadas. `GET /auth/me` devuelve id, rol_id, nombre, apellido, email, activo, cliente_id y sucursal_id de la sesión. Roles: 1 Administrador, 2 Empleado, 3 Cliente. No inferir permisos sólo desde UI: el servidor valida cada operación. JWT no contiene permisos autoritativos; la cuenta y rol se consultan en la base.

`POST /auth/register` recibe nombre, apellido, email, password y telefono opcional; crea usuario rol Cliente y perfil en una transacción. No acepta rol_id. Una cuenta cliente anterior sin perfil puede usar `POST /mi-perfil`; nunca vincula perfiles ajenos por correo. `GET/PATCH /clientes/{cliente_id}` permite consultar/editar su propio perfil con las restricciones anteriores.

No registrar tokens, contraseñas ni referencias sensibles en logs del navegador. CORS requiere orígenes explícitos; permite Authorization, Content-Type e Idempotency-Key. Flutter nativo usa las mismas rutas y permisos.

## Idempotencia

Generar una clave, por ejemplo UUID, **una vez por intención de operación** y conservarla al reintentar. Usar otra clave para otra operación. La misma clave/cuerpo retorna el mismo recurso; un cuerpo diferente devuelve 409. No generar una clave diferente automáticamente en cada reintento HTTP.

Ejemplo conceptual de consumo con HttpClient (documentación, no código frontend incluido):

```typescript
const operationKey = crypto.randomUUID();
const headers = new HttpHeaders({
  Authorization: `Bearer ${token}`,
  'Idempotency-Key': operationKey
});
this.http.post(`${api}/ventas`, {
  sucursal_id: 1,
  cliente_id: 10,
  productos: [{producto_id: 1, cantidad: 2}]
}, {headers}).subscribe(venta => { /* mostrar importe del servidor */ });
```

Este ejemplo omite deliberadamente almacenamiento de credenciales y componentes; no implementar como constante un token real. Importar HttpClient/HttpHeaders de `@angular/common/http` y configurar el cliente en la aplicación cuando se integre.

## Venta física y pago

1. Consultar catálogo activo y existencias de la sucursal autorizada.
2. `POST /ventas`, cabecera idempotente, cuerpo anterior. El empleado se determina de su cuenta. Un administrador además indica `empleado_id` de esa sucursal. `cliente_id` es opcional para venta anónima.
3. Respuesta 201 incluye `id`, `numero_venta`, `estado:"PENDIENTE"`, `subtotal`, `descuento`, `total`, `vence_at`, detalles y los IDs relacionados. Importes JSON son cadenas decimales, por ejemplo `"60.00"`. No recalcular el cobro con precios enviados por el navegador.
4. Consultar `GET /pagos/metodos` para IDs/códigos vigentes. Registrar con `POST /pagos`:

```json
{"venta_id":1,"metodo":"EFECTIVO","monto":"60.00"}
```

Para SPEI, DEPOSITO o TARJETA agregar `referencia`. No enviar PAN, CVV ni comprobantes con credenciales. El registro devuelve PENDIENTE aunque la referencia exista. Cliente sólo registra SPEI/DEPOSITO propios; personal registra también efectivo/terminal.

5. Personal verifica el dinero o autorización de terminal y ejecuta `PATCH /pagos/{id}/estado`:

```json
{"estado":"APROBADO","motivo":"Transferencia conciliada por el encargado"}
```

RECHAZADO y CANCELADO se registran con el mismo formato. Una venta/pedido se paga completo, sin anticipos. Pago activo duplicado, confirmación repetida o monto distinto: 409. Cliente no confirma pagos: 403.

`GET /ventas` soporta sucursal_id, empleado_id, estado, desde/hasta, limit/offset. `GET /pagos` soporta sucursal_id, metodo, estado, desde/hasta, limit/offset. Respuestas de listas: `{total, ventas:[...]}` y `{total, pagos:[...]}`. `GET /ventas/{id}` y `/pagos/{id}` respetan propiedad/sucursal. Historial de personal: `/{id}/historial`.

## Pedido del cliente

Elegir sucursal explícitamente desde `/sucursales`; opcionalmente `/sucursales-cercanas?latitud=20&longitud=-90` devuelve sucursales activas con coordenadas, ordenadas por distancia geodésica. No consulta geolocalización automáticamente ni garantiza reparto.

```http
POST /mis-pedidos
Authorization: Bearer <JWT cliente>
Idempotency-Key: <UUID estable>
Content-Type: application/json

{"sucursal_id":1,"productos":[{"producto_id":1,"cantidad":2}],"notas":"Retiro en sucursal"}
```

El servidor obtiene cliente_id del JWT/perfil: enviarlo arbitrariamente es 422. Respuesta conserva OrderResponse. Consultas: `GET /mis-pedidos`, `GET /mis-pedidos/{id}`, `GET /mis-pedidos/{id}/historial`. Cancelación pendiente: `POST /mis-pedidos/{id}/cancelar`. Historial del cliente sólo expone estados y fechas.

El pago puede registrarse indicando el pedido, sin crear otra venta desde el frontend:

```json
{"pedido_id":25,"metodo":"SPEI","monto":"60.00","referencia":"Referencia SPEI verificada posteriormente"}
```

No mandar simultáneamente venta_id y pedido_id. La respuesta de pago contiene venta_id, utilizable para tickets/factura. Personal gestiona `/pedidos` y `PATCH /pedidos/{id}/estado`. Aprobar el pago confirma el pedido; luego PREPARANDO, LISTO y ENTREGADO. No volver a solicitar CONFIRMADO después de aprobar el pago.

## Cancelación, devolución y vencimiento

`POST /ventas/{id}/cancelar`, personal de la sucursal para pendiente:

```json
{"motivo":"Cliente desistió de la compra"}
```

Para pagada, sólo administrador y agregar `reembolso_referencia` de la devolución total ya ejecutada. No es una transferencia automática. Los pedidos entregados se excluyen de este flujo. El operador programa `POST /ventas/expirar?limit=100` con JWT de administrador; ejecutar lotes hasta obtener lista vacía.

## Tickets y facturación administrativa

`POST /tickets/venta/{venta_id}` crea/recupera el ticket único. `GET /tickets` devuelve lista paginada; `GET /tickets/{id}` devuelve venta, detalles, métodos, pagos y `pagado`. `GET /tickets/{id}/imprimir` devuelve HTML listo para impresión o descarga, sin scripts, con contenido escapado y estado visible. Obtenerlo mediante HTTP autenticado como blob; no colocar JWT en una URL. La impresión a PDF puede hacerse desde el navegador.

`POST /facturas`, cabecera idempotente:

```json
{"venta_id":1,"cliente_id":10,"rfc":"XAXX010101000","razon_social":"Cliente de prueba","uso_cfdi":"G03","codigo_postal_fiscal":"24000","regimen_fiscal":"616","tipo_persona":"FISICA","direccion_fiscal":"Dirección fiscal del receptor","email_fiscal":"cliente@example.com"}
```

Los valores fiscales de ejemplo no validan a un receptor real. Se requiere venta pagada y cliente correspondiente. Para venta anónima sólo administrador vincula el cliente al solicitar factura. Consulta `/facturas`, `/facturas/{id}`; filtros estado/limit/offset. Solicitud inicial PENDIENTE.

Sólo administrador usa `PATCH /facturas/{id}/estado`. EMITIDA requiere motivo, uuid, proveedor, referencia_proveedor y fecha_emision con zona horaria, correspondientes a un documento externo real. CANCELADA requiere motivo; si estaba EMITIDA también referencia_proveedor de cancelación externa. La API no genera ni timbra CFDI ni envía correos. Historial `/facturas/{id}/historial` para personal autorizado.

## Reportes

Exclusivos de administrador. Fechas ISO 8601 **con zona horaria**; intervalos `[desde, hasta)`. Paginación limit 1–100 y offset ≥0. Zona IANA por defecto America/Merida, configurable como parámetro `zona_horaria` en ventas/dashboard.

| Ruta GET | Parámetros principales | Resultado |
|---|---|---|
| /reportes/ventas | agrupacion=dia/semana/mes/anio/sucursal/empleado; orden=grupo/total_asc/total_desc; desde/hasta; sucursal_id | grupos, número de ventas confirmadas, total |
| /reportes/productos | desde/hasta; sucursal_id; menos_vendidos=true opcional | unidades y total; menos vendidos incluye catálogo con cero ventas |
| /reportes/pagos | desde/hasta; sucursal_id; solo_confirmados | estado, método, sucursal, cantidad, importe; ingresos usan sólo confirmados |
| /reportes/inventarios | sucursal_id; solo_bajo_stock | existencias y mínimo |
| /reportes/movimientos | desde/hasta; sucursal_id; tipo | movimientos históricos |
| /reportes/dashboard | sucursal_id; zona_horaria | catálogo activo, clientes globales, pedidos pendientes, ventas del día, ingresos del mes, top productos, alertas |

Reportes devuelven arrays de filas salvo dashboard. Tickets/facturas devuelven arrays paginados; ventas/pagos/pedidos conservan contenedor con total. Consulte OpenAPI para nombres y tipos exactos de cada respuesta. Los reportes no generan datos simulados.

## Errores

| HTTP | Manejo en interfaz |
|---|---|
| 401 | Falta JWT, expiró o cuenta inválida: solicitar sesión; WWW-Authenticate: Bearer |
| 403 | Rol, propiedad o sucursal insuficiente; ocultar acción y mostrar acceso denegado |
| 404 | Recurso inexistente |
| 409 | Estado/stock/idempotencia/importe incompatible: refrescar operación antes de reintentar |
| 422 | Datos inválidos; mostrar errores sin reproducir datos sensibles |
| 429 | Autenticación limitada; respetar Retry-After |
| 500/503 | Error interno/disponibilidad; no asumir que un pago se confirmó; consultar operación y conservar clave de idempotencia |

Los detalles internos de SQL, trazas y secretos no se devuelven. `COMMERCIAL_RULES.md` define las reglas completas y limitaciones históricas.
