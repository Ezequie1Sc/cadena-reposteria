# Auditoría y corrección de seguridad — Cadena de Repostería

**Fecha:** 12 de noviembre de 2026. **Alcance:** ZIP suministrado y esquema SQL de referencia. **Resultado:** backend existente corregido; revisión de producción pendiente. No se accedió a Supabase real, no se desplegó y no se cambiaron credenciales reales.

## Resultado ejecutivo

Se conservaron la arquitectura modular, los nueve módulos existentes, las **56 operaciones HTTP únicas**, sus métodos y sus respuestas de éxito. El original registraba 57 rutas porque `GET /roles` estaba duplicado. Se retiró únicamente ese registro redundante.

La suite final ejecutada en **Python 3.14.10** terminó con **1,104 aprobadas, 0 fallidas, 0 omitidas y 1 advertencia, en 52.71 segundos**, incluyendo cuatro pruebas con PostgreSQL local. Los 770 escenarios previamente aprobados se conservaron, se habilitó la prueba PostgreSQL originalmente omitida y se añadieron 333 casos. La advertencia corresponde a la deprecación del uso de HTTPX por Starlette TestClient; no se suprimió ni se sustituyó HTTPX.

El problema principal confirmado estaba en la autorización de FastAPI: no había dependencias de autenticación heredadas para 32 operaciones que ahora son privadas. Entre ellas había 20 escrituras administrativas de catálogo, empleados y clientes. Además, los endpoints de inventarios y pedidos validaban el rol de personal, pero no su sucursal.

El diagnóstico histórico `postgres / puede omitir RLS = True` es coherente con una conexión privilegiada que no queda restringida por RLS. No prueba acceso malicioso ni filtración. Las políticas reales, el propietario efectivo y los grants de producción no estaban incluidos en los archivos.

## Método y evidencias

1. Extracción segura del ZIP, normalizando sus separadores Windows y conservando una copia original para comparación. Revisión del TXT completo sin ejecutarlo contra Supabase.
2. Inspección de la aplicación, routers, dependencias, servicios, repositorios, modelos, esquemas, configuración, sesiones y cuatro migraciones.
3. Inspección recursiva de dependencias de los routers incluidos. La versión de FastAPI utiliza routers incluidos de forma diferida: contar solamente `APIRoute` en `app.routes` sería incorrecto.
4. Reproducciones HTTP sobre la aplicación original con bases/servicios aislados, sin hacer escrituras reales: `GET /clientes` y `GET /empleados` respondieron 200 sin JWT; `DELETE /productos/1` respondió 204 e invocó el servicio sin JWT. Un valor malformado del campo contraseña apareció en la respuesta 422. `debug` era true por defecto.
5. Ejecución de referencia: **770 aprobadas, 1 omitida, 1 advertencia, 42.49 s** en Python 3.13.5. Se resolvió previamente un problema del proxy del entorno de auditoría; no era un defecto funcional del backend.
6. Correcciones y nuevas pruebas HTTP con JWT y ORM reales, sin reemplazar autenticación por mocks. Las pruebas antiguas centradas en rutas/servicios recibieron un actor administrador simulado explícito, manteniendo sus escenarios y aserciones funcionales.
7. Pruebas de concurrencia con PostgreSQL 16.2 local y datos sintéticos, más validación de Alembic y de la propuesta de rol. El esquema del TXT se usó únicamente en esta base desechable local.
8. Comparación de rutas, contratos de éxito, funciones de prueba originales y bytes de las migraciones anteriores. Evidencias incluidas en `docs/security/evidence/`.

## Hallazgos confirmados y correcciones

| ID | Severidad | Hallazgo y efecto | Archivos principales | Corrección y verificación |
|---|---|---|---|---|
| SEC-01 | Crítica | Escrituras administrativas anónimas en productos, categorías, sucursales, clientes y empleados. No existían dependencias heredadas que las protegieran. | `app/main.py`, `app/modules/{products,categories,branches,customers,employees}/routes.py` | Dependencias por operación usando `CurrentUser` y `AdminUser` existentes. 52 operaciones privadas probadas con JWT ausente, inválido, expirado y usuario inactivo; matriz de denegación de privilegios. |
| SEC-02 | Alta | Lectura anónima de fichas de empleados/clientes y posibilidad de modificar la vinculación de un cliente. | Rutas de clientes y empleados; `app/core/permissions.py` | Administración de empleados y listados globales de clientes exclusiva de Administrador. Cliente limitado a su ficha activa vinculada para GET/PATCH; no puede modificar `usuario_id`, estado ni roles. Pruebas reales de acceso propio/ajeno y ausencia de cambios no autorizados. |
| SEC-03 | Alta | Personal podía consultar y operar inventarios/pedidos de cualquier sucursal. | Rutas de inventarios/pedidos; `app/core/permissions.py` | Se exige asignación activa de empleado y sucursal activa. Listados filtrados automáticamente; filtros ajenos y recursos de otra sucursal se rechazan con 403. Se conserva acceso global del administrador. |
| SEC-04 | Alta | Lectura ORM previa a un bloqueo podía conservar estado antiguo al adquirir `FOR UPDATE`, afectando stock y cancelaciones. | Repositorios de inventarios y pedidos | `populate_existing=True` al adquirir bloqueos. PostgreSQL real: actualización después de precarga, dos pedidos compitiendo por stock y cancelación con estado antiguo. Los tres casos pasan. |
| SEC-05 | Media | Errores de validación reflejaban datos de entrada, incluyendo contraseñas malformadas o anidadas. | `app/core/errors.py`, `app/main.py` | Handler 422 conserva `detail/type/loc/msg` y omite `input/ctx`. Respuestas SQL 503 y errores inesperados 500 genéricos. Pruebas comprueban ausencia del secreto y del traceback. |
| SEC-06 | Alta condicionada al despliegue | `DEBUG=true` por defecto y secretos/algoritmos/duración JWT sin validación suficiente. No se conoce la configuración efectiva de producción. | `app/core/config.py`, `app/main.py`, `app/core/jwt.py` | Debug desactivado; rechazado en producción/staging. Clave mínima validada, algoritmos HMAC explícitos, TTL 1–1440 min, `sub` limitado al rango BIGINT. Documentación HTTP deshabilitada en producción/staging. Pruebas de configuración y tokens extremos. |
| SEC-07 | Media | `/roles` duplicado y salud/roles dependían del cliente Supabase creado al importar, aun usando SQLAlchemy para el resto. | `app/api/routes/{roles,health}.py`, `app/core/supabase.py` | Un solo `/roles`; ambos diagnósticos restringidos a Administrador y ejecutados por SQLAlchemy. Cliente heredado opcional diferido; se conservó el archivo y las dependencias originales. |
| SEC-08 | Media | Registro recortaba espacios de contraseña mientras login los conservaba; login de correo inexistente omitía el trabajo Argon2, creando una diferencia temporal observable. | Registro y `app/core/login.py` | Contraseñas de nuevos registros conservadas exactamente; trabajo Argon2 equivalente para cuentas desconocidas. Prueba de registro/login con espacios. No se afirma tiempo constante absoluto. |
| SEC-09 | Baja / defensa adicional | Varios esquemas ignoraban campos extra; los campos no llegaban a persistirse, por lo que no se demostró asignación masiva explotable en esos esquemas. | Esquemas de usuarios, clientes, inventarios y pedidos | `extra="forbid"` para entradas. Pruebas rechazan actor, precios, totales, roles y campos no permitidos; cálculos de pedidos siguen siendo del servidor. |
| SEC-10 | Media operativa | Alembic compartía obligatoriamente la conexión de aplicación y no importaba los modelos existentes de inventario/pedidos. El test PostgreSQL opcional usaba el engine de aplicación. | `alembic/env.py`, `app/db/models.py`, pruebas de integración | Credencial opcional separada de migración, registro de modelos faltantes, configuración de tests aislada y guardas de host/nombre de base. Cuatro migraciones originales preservadas; cadena ejecutada solo localmente. |
| SEC-11 | Baja / configuración | No había CORS explícito, plantilla de entorno ni exclusión suficiente de variantes privadas; pytest no estaba declarado. La ausencia de CORS no otorgaba autenticación ni constituía por sí sola un bypass. | Configuración, `.env.example`, `.gitignore`, `requirements-dev.txt` | Orígenes exactos, sin wildcard, sin cookies; plantilla pública segura y rechazada hasta configurar clave; exclusiones ampliadas; pytest declarado. Se conservaron los pins de producción y se convirtió requirements de UTF-16 a UTF-8. |

La severidad refleja impacto potencial sobre el código auditado; no equivale a una evaluación de explotabilidad externa del despliegue real. No hay evidencia de que estas rutas estuvieran accesibles desde Internet ni de uso malicioso.

## Política de permisos y supuestos de negocio

| Módulo / operación | Administrador | Empleado | Cliente | Público |
|---|---|---|---|---|
| Inicio y `/health` | Sí | Sí | Sí | Sí |
| Login y registro | Sí | Sí | Sí | Sí; registro fija rol Cliente |
| Catálogos: productos, categorías y sucursales | Lectura completa y escritura | Lectura de activos | Lectura de activos | No |
| Usuarios, roles y diagnóstico DB | Sí | No | No | No |
| Empleados | Administración completa | No | No | No |
| Clientes: listado, creación, desactivación, reactivación | Sí | No | No | No |
| Clientes: consulta/actualización de ficha | Cualquier ficha | No | Solo ficha propia activa; datos personales permitidos | No |
| Inventario: lectura, entradas, salidas y movimientos | Global | Solo sucursal asignada activa | No | No |
| Inventario: creación, mínimo, ajustes y traspasos | Sí | No | No | No |
| Pedidos: lectura, creación y cambio de estado | Global | Solo sucursal asignada activa | No | No |

Decisiones conservadoras documentadas:

- Los tests originales establecían que clientes no administran pedidos; no se habilitó compra/autoservicio ni cancelación del cliente en esta tarea.
- Las fichas de clientes no tienen `sucursal_id`. No se inventó pertenencia por sucursal ni se abrió el listado global a empleados. Si el negocio necesita capturar clientes en mostrador, deberá definir y probar un permiso explícito antes de ampliarlo. El empleado conserva las operaciones de pedidos con identificadores de clientes ya registrados.
- El registro público existente crea `usuarios` con rol Cliente y no crea automáticamente una fila en `clientes`. Se preservó ese comportamiento. El administrador debe crear/vincular la ficha antes de usar su autoservicio. No se enlazan cuentas por email por conveniencia.
- Las lecturas de catálogo requieren JWT por política conservadora; no se diseñó una tienda anónima. Para clientes/empleados, `solo_activos=false` devuelve 403 y una ficha inactiva devuelve 404. El administrador conserva filtros y consultas anteriores.
- Autenticación usa IDs de rol 1/2/3 existentes. Los desconocidos se rechazan. La correspondencia real de esos IDs con nombres debe comprobarse antes del despliegue.
- Los bloqueos compartidos de empleado/sucursal mantienen la asignación durante una operación; una revocación concurrente puede esperar a que termine la transacción ya autorizada.

La matriz completa `MATRIZ_ENDPOINTS.csv` y su versión Markdown contienen las 56 operaciones, dependencias antes/después, clasificación, roles, ámbito, hallazgo y corrección.

## Arquitectura y consistencia conservadas

Se mantiene `app/api`, `core`, `db`, `modules`, `shared`, `alembic`, `scripts` y `tests`. No se creó un segundo sistema de autenticación. Se reutilizan HTTPBearer, `get_current_user`, `require_roles`, JWT PyJWT, roles activos y Argon2id.

Los repositorios usan expresiones SQLAlchemy y parámetros; no se identificaron consultas SQL de aplicación construidas con entrada del usuario. Los filtros `ilike` usan parámetros: comodines pueden ampliar búsquedas autorizadas, pero no se consideran inyección SQL confirmada. Los servicios conservan validaciones de productos/categorías activas, transacciones, rollback, precios del servidor, detección de productos repetidos, orden ascendente de bloqueos y transiciones de pedidos. Los movimientos registran el actor autenticado.

El motor mantiene tamaño del pool y reciclado, agrega `hide_parameters=True` y la dependencia de sesión hace rollback explícito en excepciones. Los servicios siguen siendo código interno de confianza: la autorización HTTP se aplica en dependencias/rutas y no debe omitirse en futuros workers o tareas internas. No se añadieron endpoints comerciales.

## Contraste con el SQL de referencia

El TXT describe estructura inicial y contiene DDL y datos semilla; no es prueba del estado actual. La migración baseline `404a9071350b` es intencionalmente vacía: **Alembic no reconstruye una base desde cero**. Las posteriores añaden `clientes.activo`, `empleados.activo` y `auth_rate_limits`, ausentes del TXT.

Los modelos son parciales frente a la base completa: roles utiliza una tabla de referencia, y módulos como pagos, ventas y facturas no se implementaron. Se conservaron discrepancias no necesarias para esta corrección, como precisiones/metadatos ORM e índices que no reproducen cada restricción del TXT. No ejecutar `autogenerate` y aplicar su resultado sin revisión: registrar modelos omitidos puede revelar diferencias históricas. No se generó una migración destructiva ni se alteraron las anteriores.

## Resultados y límites de verificación

| Comprobación | Resultado |
|---|---|
| Suite original | 770 aprobadas, 1 omitida, 1 advertencia; 42.49 s; Python 3.13.5 |
| Suite final completa | 1,104 aprobadas, 0 fallidas, 0 omitidas, 1 advertencia; 52.71 s; Python 3.14.10 |
| PostgreSQL real aislado | 4 aprobadas; contadores concurrentes, actualización de stock precargado, pedidos simultáneos y cancelación repetida |
| Rol propuesto sin BYPASSRLS | Operaciones de usuarios, inventarios, pedidos y rate limiting comprobadas con RLS local; permisos fuera de alcance denegados |
| Alembic local | Cuatro revisiones ejecutadas sobre esquema sintético; head/current `974e270dd2f1` |
| Contratos | 56 pares método/ruta conservados; se elimina solamente el registro duplicado de `/roles` |
| Tests/migraciones originales | Se conservan todas las funciones de prueba y los cuatro archivos de revisión originales |
| Supabase real | No conectado ni modificado; políticas, grants y estado actual pendientes |
| Windows | Comandos completos entregados; ejecución observada fue Linux, no Windows |

La verificación local del rol se realizó dentro de una transacción revertida; no se cambió `DATABASE_URL` del proyecto para usarlo. En pruebas portables sin PostgreSQL se omiten cuatro casos de integración por diseño y se informa la razón. Los límites del runtime que afectaron los primeros intentos de iniciar PostgreSQL local se resolvieron antes de la ejecución final; no se ocultaron fallos finales mediante skips.

Los errores intermedios de fixtures nuevas se corrigieron, sin eliminar escenarios originales. La advertencia final de Starlette/HTTPX está conservada en la salida y en el informe de resultados. Los resultados no representan una prueba de penetración sobre infraestructura externa ni certifican ausencia de vulnerabilidades en dependencias.

## Riesgos y verificaciones pendientes

| Pendiente | Riesgo / motivo | Cómo resolver |
|---|---|---|
| Credencial real sigue siendo la actual | Si continúa siendo `postgres` con BYPASSRLS, una credencial comprometida conserva privilegios amplios | Revisar y validar `SUPABASE.md` en staging, luego cambio de credencial separado |
| RLS/Data API real | No se incluyeron políticas, vistas, funciones, grants heredados ni membresías actuales | Ejecutar revisión autorizada de solo lectura; revisar TO PUBLIC y SECURITY DEFINER; confirmar exposición de tablas por Data API |
| Roles y vinculaciones existentes | Un empleado sin ficha activa o un cliente sin vinculación no tendrá acceso al ámbito restringido | Verificar y corregir datos por procedimiento administrativo, sin conceder permisos generales |
| Tokens anteriores y sesiones | No existe logout con revocación individual; cambiar contraseña no invalida automáticamente todos los JWT ya emitidos | Mantener TTL corto y clave exclusiva; diseñar revocación/versionado de sesión en una tarea con migración aprobada |
| Disponibilidad y abuso distribuido | Rate limiting cubre login/registro, no volumen general, múltiples IP ni todos los cuerpos inválidos; tablas de contadores pueden crecer | Configurar límites en ingress, limpieza separada de contadores y monitoreo sin registrar credenciales |
| Listados extensos | Algunos catálogos/inventarios/empleados no tienen paginación contractual | Medir volumen y agregar paginación compatible mediante cambio posterior; no truncar datos silenciosamente |
| Enumeración por registro | El contrato existente devuelve 409 si un email ya está registrado | Evaluar respuesta neutral y verificación de correo con un flujo de negocio aprobado; se conserva contrato y rate limit |
| Configuración efectiva | TLS, CORS de dominios reales, proxy confiable, secretos, logs y red dependen del despliegue | Verificar en staging antes de publicar; nunca usar claves de ejemplo |
| Esquema real y migraciones | No se conoce la revisión efectiva ni restricciones extra de Supabase | Contrastar `alembic current` y diagnóstico con autorización; no ejecutar migraciones automáticamente |

No se identificaron secretos de producción en los archivos revisados mediante inspección y búsqueda de patrones. Esto no descarta secretos en historial Git, variables de plataforma o archivos no entregados. Los valores de contraseña/clave en tests son sintéticos y nunca deben usarse en despliegue.

## Criterios de aceptación

Los controles privados, roles, propiedad/sucursal, pruebas no autorizadas y suite completa se verificaron localmente. La funcionalidad legítima cubierta por los escenarios existentes se conserva. Se entregan ZIP, informe, matriz, resultados, resumen de archivos, SQL revisable, comandos Windows y propuesta de PR. La base real no fue alterada.

**Pendiente de aceptación operativa:** contrastar datos, roles, revisión Alembic, políticas y grants reales, ejecutar pruebas de staging con la nueva credencial propuesta y validar la infraestructura. No se declara el backend completamente seguro ni listo para desplegar sin esas comprobaciones.

## Fuentes técnicas primarias

- PostgreSQL, RLS y excepciones de propietario/BYPASSRLS: https://www.postgresql.org/docs/17/ddl-rowsecurity.html
- Supabase, RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase, seguridad de Data API: https://supabase.com/docs/guides/api/securing-your-api
- SQLAlchemy, actualización de objetos del identity map: https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html
- FastAPI, manejo de errores de validación: https://fastapi.tiangolo.com/tutorial/handling-errors/
