# Matriz de las 56 operaciones HTTP

La clasificación corresponde al código corregido. `check_permissions` representa `require_roles`; los roles concretos están en la columna Roles. Todas las dependencias de autenticación leen usuario y rol activo de la base. `403` indica identidad válida sin permiso; `401` indica credenciales ausentes/inválidas o usuario inactivo.

Los ámbitos de recurso se comprueban en las rutas mediante los helpers de `app/core/permissions.py`. El CSV incluye módulo, dependencias anteriores y posteriores, hallazgo y corrección completos.

| Método | Ruta | Acceso | Roles | Ámbito | Hallazgo / corrección |
|---|---|---|---|---|---|
| GET | / | Público | Sin JWT | Disponibilidad sin datos privados | Sin vulnerabilidad de acceso confirmada; Conservado |
| POST | /auth/login | Público | Sin JWT | Login/registro limitados por IP; registro fija Cliente | Controles existentes conservados; validación/configuración reforzadas; Handler seguro; límites y JWT existentes conservados |
| POST | /auth/register | Público | Sin JWT | Login/registro limitados por IP; registro fija Cliente | Controles existentes conservados; validación/configuración reforzadas; Handler seguro; límites y JWT existentes conservados |
| GET | /categorias | Autenticado | Administrador, Empleado, Cliente | No administradores: solo activos | Lectura sin autenticación; exposición de inactivos; CurrentUser y filtro de activos |
| POST | /categorias | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| DELETE | /categorias/{category_id} | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| GET | /categorias/{category_id} | Autenticado | Administrador, Empleado, Cliente | No administradores: solo activos | Lectura sin autenticación; exposición de inactivos; CurrentUser y filtro de activos |
| PATCH | /categorias/{category_id} | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| PATCH | /categorias/{category_id}/reactivar | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| GET | /clientes | Restringido | Administrador | Gestión global; empleado denegado | PII/gestión sin autenticación; acceso horizontal sin control; AdminUser |
| POST | /clientes | Restringido | Administrador | Gestión global; empleado denegado | PII/gestión sin autenticación; acceso horizontal sin control; AdminUser |
| DELETE | /clientes/{customer_id} | Restringido | Administrador | Gestión global; empleado denegado | PII/gestión sin autenticación; acceso horizontal sin control; AdminUser |
| GET | /clientes/{customer_id} | Restringido | Administrador, Cliente | Administrador: global; Cliente: ficha propia activa, sin modificar usuario_id | PII/gestión sin autenticación; acceso horizontal sin control; JWT, propiedad y allowlist de campos |
| PATCH | /clientes/{customer_id} | Restringido | Administrador, Cliente | Administrador: global; Cliente: ficha propia activa, sin modificar usuario_id | PII/gestión sin autenticación; acceso horizontal sin control; JWT, propiedad y allowlist de campos |
| PATCH | /clientes/{customer_id}/reactivar | Restringido | Administrador | Gestión global; empleado denegado | PII/gestión sin autenticación; acceso horizontal sin control; AdminUser |
| GET | /empleados | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| POST | /empleados | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| DELETE | /empleados/{employee_id} | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| GET | /empleados/{employee_id} | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| PATCH | /empleados/{employee_id} | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| PATCH | /empleados/{employee_id}/reactivar | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| GET | /health | Público | Sin JWT | Disponibilidad sin datos privados | Sin vulnerabilidad de acceso confirmada; Conservado |
| GET | /health/database | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| GET | /inventarios | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa | RBAC existente; faltaba ámbito por sucursal; StaffUser + asignación/sucursal + recurso |
| POST | /inventarios | Restringido | Administrador | Gestión global, ajustes y traspasos solo administración | RBAC administrativo ya existente; concurrencia reforzada; AdminUser conservado; campos extra rechazados |
| GET | /inventarios/{inventory_id} | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa | RBAC existente; faltaba ámbito por sucursal; StaffUser + asignación/sucursal + recurso |
| PATCH | /inventarios/{inventory_id} | Restringido | Administrador | Gestión global, ajustes y traspasos solo administración | RBAC administrativo ya existente; concurrencia reforzada; AdminUser conservado; campos extra rechazados |
| POST | /inventarios/{inventory_id}/ajustes | Restringido | Administrador | Gestión global, ajustes y traspasos solo administración | RBAC administrativo ya existente; concurrencia reforzada; AdminUser conservado; campos extra rechazados |
| POST | /inventarios/{inventory_id}/entradas | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa | RBAC existente; faltaba ámbito por sucursal; StaffUser + asignación/sucursal + recurso |
| GET | /inventarios/{inventory_id}/movimientos | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa | RBAC existente; faltaba ámbito por sucursal; StaffUser + asignación/sucursal + recurso |
| POST | /inventarios/{inventory_id}/salidas | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa | RBAC existente; faltaba ámbito por sucursal; StaffUser + asignación/sucursal + recurso |
| POST | /inventarios/{inventory_id}/traspasos | Restringido | Administrador | Gestión global, ajustes y traspasos solo administración | RBAC administrativo ya existente; concurrencia reforzada; AdminUser conservado; campos extra rechazados |
| GET | /pedidos | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa; clientes denegados | RBAC existente; faltaba ámbito por sucursal; StaffUser + filtro/recurso/sucursal; bloqueo con refresco ORM |
| POST | /pedidos | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa; clientes denegados | RBAC existente; faltaba ámbito por sucursal; StaffUser + filtro/recurso/sucursal; bloqueo con refresco ORM |
| GET | /pedidos/numero/{numero_pedido} | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa; clientes denegados | RBAC existente; faltaba ámbito por sucursal; StaffUser + filtro/recurso/sucursal; bloqueo con refresco ORM |
| GET | /pedidos/{order_id} | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa; clientes denegados | RBAC existente; faltaba ámbito por sucursal; StaffUser + filtro/recurso/sucursal; bloqueo con refresco ORM |
| PATCH | /pedidos/{order_id}/estado | Restringido | Administrador, Empleado | Administrador: global; Empleado: sucursal asignada activa; clientes denegados | RBAC existente; faltaba ámbito por sucursal; StaffUser + filtro/recurso/sucursal; bloqueo con refresco ORM |
| GET | /productos | Autenticado | Administrador, Empleado, Cliente | No administradores: solo activos | Lectura sin autenticación; exposición de inactivos; CurrentUser y filtro de activos |
| POST | /productos | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| DELETE | /productos/{product_id} | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| GET | /productos/{product_id} | Autenticado | Administrador, Empleado, Cliente | No administradores: solo activos | Lectura sin autenticación; exposición de inactivos; CurrentUser y filtro de activos |
| PATCH | /productos/{product_id} | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| PATCH | /productos/{product_id}/reactivar | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| GET | /roles | Restringido | Administrador | Administración global | Acceso sin JWT; /roles duplicado o diagnóstico sin protección; AdminUser; SQLAlchemy; registro único |
| GET | /sucursales | Autenticado | Administrador, Empleado, Cliente | No administradores: solo activos | Lectura sin autenticación; exposición de inactivos; CurrentUser y filtro de activos |
| POST | /sucursales | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| DELETE | /sucursales/{branch_id} | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| GET | /sucursales/{branch_id} | Autenticado | Administrador, Empleado, Cliente | No administradores: solo activos | Lectura sin autenticación; exposición de inactivos; CurrentUser y filtro de activos |
| PATCH | /sucursales/{branch_id} | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| PATCH | /sucursales/{branch_id}/reactivar | Restringido | Administrador | Gestión administrativa global | Sin autenticación heredada; escritura anónima; AdminUser |
| GET | /usuarios | Restringido | Administrador | Administración global | RBAC existente conservado; AdminUser conservado; entradas estrictas |
| POST | /usuarios | Restringido | Administrador | Administración global | RBAC existente conservado; AdminUser conservado; entradas estrictas |
| DELETE | /usuarios/{user_id} | Restringido | Administrador | Administración global | RBAC existente conservado; AdminUser conservado; entradas estrictas |
| GET | /usuarios/{user_id} | Restringido | Administrador | Administración global | RBAC existente conservado; AdminUser conservado; entradas estrictas |
| PATCH | /usuarios/{user_id} | Restringido | Administrador | Administración global | RBAC existente conservado; AdminUser conservado; entradas estrictas |
| PATCH | /usuarios/{user_id}/reactivar | Restringido | Administrador | Administración global | RBAC existente conservado; AdminUser conservado; entradas estrictas |

## Rutas técnicas de documentación

`/docs`, `/redoc`, `/openapi.json` y el redirect OAuth2 de Swagger son rutas técnicas, no operaciones de negocio OpenAPI. La documentación se publica solo en development/test cuando DOCS_ENABLED=true. En staging/production no se publican esos endpoints; el esquema puede generarse internamente.

La versión original tenía 57 registros para 56 operaciones únicas porque `GET /roles` aparecía en dos routers. La matriz contiene una sola fila para esa operación.
