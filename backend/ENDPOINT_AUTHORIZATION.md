# Matriz de autorización actual

92 operaciones: 4 públicas y 88 con JWT.

| Método | Ruta | Roles | Restricción |
|---|---|---|---|
| GET | `/` | Público | Sin JWT |
| POST | `/auth/login` | Público | Sin JWT |
| GET | `/auth/me` | Administrador, Empleado, Cliente | Cuenta autenticada propia |
| POST | `/auth/register` | Público | Sin JWT |
| GET | `/categorias` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| POST | `/categorias` | Administrador | Administrativo |
| DELETE | `/categorias/{category_id}` | Administrador | Administrativo |
| GET | `/categorias/{category_id}` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| PATCH | `/categorias/{category_id}` | Administrador | Administrativo |
| PATCH | `/categorias/{category_id}/reactivar` | Administrador | Administrativo |
| GET | `/clientes` | Administrador | Administrativo |
| POST | `/clientes` | Administrador | Administrativo |
| DELETE | `/clientes/{customer_id}` | Administrador | Administrativo |
| GET | `/clientes/{customer_id}` | Administrador, Cliente | Cliente sólo GET/PATCH propio, sin vincular usuario |
| PATCH | `/clientes/{customer_id}` | Administrador, Cliente | Cliente sólo GET/PATCH propio, sin vincular usuario |
| PATCH | `/clientes/{customer_id}/reactivar` | Administrador, Cliente | Cliente sólo GET/PATCH propio, sin vincular usuario |
| GET | `/empleados` | Administrador | Administrativo |
| POST | `/empleados` | Administrador | Administrativo |
| DELETE | `/empleados/{employee_id}` | Administrador | Administrativo |
| GET | `/empleados/{employee_id}` | Administrador | Administrativo |
| PATCH | `/empleados/{employee_id}` | Administrador | Administrativo |
| PATCH | `/empleados/{employee_id}/reactivar` | Administrador | Administrativo |
| GET | `/facturas` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| POST | `/facturas` | Administrador, Empleado, Cliente | Venta pagada y cliente correspondiente; vincular venta anónima sólo administrador |
| GET | `/facturas/{invoice_id}` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| PATCH | `/facturas/{invoice_id}/estado` | Administrador | Gestión administrativa |
| GET | `/facturas/{invoice_id}/historial` | Administrador, Empleado | Empleado sólo sucursal propia |
| GET | `/health` | Público | Sin JWT |
| GET | `/health/database` | Administrador | Administrativo |
| GET | `/inventarios` | Administrador, Empleado | Empleado sólo sucursal asignada activa |
| POST | `/inventarios` | Administrador | Operación administrativa |
| GET | `/inventarios/{inventory_id}` | Administrador, Empleado | Empleado sólo sucursal asignada activa |
| PATCH | `/inventarios/{inventory_id}` | Administrador | Operación administrativa |
| POST | `/inventarios/{inventory_id}/ajustes` | Administrador | Operación administrativa |
| POST | `/inventarios/{inventory_id}/entradas` | Administrador, Empleado | Empleado sólo sucursal asignada activa |
| GET | `/inventarios/{inventory_id}/movimientos` | Administrador, Empleado | Empleado sólo sucursal asignada activa |
| POST | `/inventarios/{inventory_id}/salidas` | Administrador, Empleado | Empleado sólo sucursal asignada activa |
| POST | `/inventarios/{inventory_id}/traspasos` | Administrador | Operación administrativa |
| POST | `/mi-perfil` | Cliente | Perfil propio activo; pedidos propios |
| GET | `/mis-pedidos` | Cliente | Perfil propio activo; pedidos propios |
| POST | `/mis-pedidos` | Cliente | Perfil propio activo; pedidos propios |
| GET | `/mis-pedidos/{order_id}` | Cliente | Perfil propio activo; pedidos propios |
| POST | `/mis-pedidos/{order_id}/cancelar` | Cliente | Perfil propio activo; pedidos propios |
| GET | `/mis-pedidos/{order_id}/historial` | Cliente | Perfil propio activo; pedidos propios |
| GET | `/pagos` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| POST | `/pagos` | Administrador, Empleado, Cliente | Cliente sólo SPEI/DEPOSITO propios; personal según sucursal; siempre PENDIENTE |
| GET | `/pagos/metodos` | Administrador, Empleado, Cliente | Catálogo de métodos activos; sin acceso a transacciones ajenas |
| GET | `/pagos/{payment_id}` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| PATCH | `/pagos/{payment_id}/estado` | Administrador, Empleado | Empleado sólo sucursal; devolución pagada sólo administrador |
| GET | `/pagos/{payment_id}/historial` | Administrador, Empleado | Empleado sólo sucursal propia |
| GET | `/pedidos` | Administrador, Empleado | Empleado sólo sucursal propia; pago verificado para avanzar |
| POST | `/pedidos` | Administrador, Empleado | Empleado sólo sucursal propia; pago verificado para avanzar |
| GET | `/pedidos/numero/{numero_pedido}` | Administrador, Empleado | Empleado sólo sucursal propia; pago verificado para avanzar |
| GET | `/pedidos/{order_id}` | Administrador, Empleado | Empleado sólo sucursal propia; pago verificado para avanzar |
| PATCH | `/pedidos/{order_id}/estado` | Administrador, Empleado | Empleado sólo sucursal propia; pago verificado para avanzar |
| GET | `/pedidos/{order_id}/historial` | Administrador, Empleado | Empleado sólo sucursal propia; pago verificado para avanzar |
| GET | `/productos` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| POST | `/productos` | Administrador | Administrativo |
| DELETE | `/productos/{product_id}` | Administrador | Administrativo |
| GET | `/productos/{product_id}` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| PATCH | `/productos/{product_id}` | Administrador | Administrativo |
| PATCH | `/productos/{product_id}/reactivar` | Administrador | Administrativo |
| GET | `/reportes/dashboard` | Administrador | Administrativo |
| GET | `/reportes/inventarios` | Administrador | Administrativo |
| GET | `/reportes/movimientos` | Administrador | Administrativo |
| GET | `/reportes/pagos` | Administrador | Administrativo |
| GET | `/reportes/productos` | Administrador | Administrativo |
| GET | `/reportes/ventas` | Administrador | Administrativo |
| GET | `/roles` | Administrador | Administrativo |
| GET | `/sucursales` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| POST | `/sucursales` | Administrador | Administrativo |
| GET | `/sucursales-cercanas` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| DELETE | `/sucursales/{branch_id}` | Administrador | Administrativo |
| GET | `/sucursales/{branch_id}` | Administrador, Empleado, Cliente | Sólo activos para no administradores |
| PATCH | `/sucursales/{branch_id}` | Administrador | Administrativo |
| PATCH | `/sucursales/{branch_id}/reactivar` | Administrador | Administrativo |
| GET | `/tickets` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| POST | `/tickets/venta/{sale_id}` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| GET | `/tickets/{ticket_id}` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| GET | `/tickets/{ticket_id}/imprimir` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| GET | `/usuarios` | Administrador | Administrativo |
| POST | `/usuarios` | Administrador | Administrativo |
| DELETE | `/usuarios/{user_id}` | Administrador | Administrativo |
| GET | `/usuarios/{user_id}` | Administrador | Administrativo |
| PATCH | `/usuarios/{user_id}` | Administrador | Administrativo |
| PATCH | `/usuarios/{user_id}/reactivar` | Administrador | Administrativo |
| GET | `/ventas` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| POST | `/ventas` | Administrador, Empleado | Empleado sólo sucursal; devolución pagada sólo administrador |
| POST | `/ventas/expirar` | Administrador | Gestión administrativa |
| GET | `/ventas/{sale_id}` | Administrador, Empleado, Cliente | Empleado sólo sucursal; cliente sólo operaciones propias; restricciones adicionales documentadas |
| POST | `/ventas/{sale_id}/cancelar` | Administrador, Empleado | Empleado sólo sucursal; devolución pagada sólo administrador |
| GET | `/ventas/{sale_id}/historial` | Administrador, Empleado | Empleado sólo sucursal propia |
