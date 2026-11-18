# Propuesta de Pull Request

Rama: `feat/manual-commerce-workflows`

Título: `feat: integrar ventas, pagos manuales y pedidos de clientes con trazabilidad`

## Descripción

El backend tenía catálogo, inventarios y pedidos de personal, pero no podía completar el flujo comercial contemplado por el proyecto. Esta entrega conecta ventas físicas y pedidos propios con pagos manuales completos, tickets imprimibles, solicitudes administrativas de factura y reportes SQL.

Conserva las 56 operaciones originales y añade 36 protegidas. Las reservas y cancelaciones usan bloqueos y transacciones; las creaciones nuevas son idempotentes. Confirmar un pago actualiza venta/pedido sin descontar inventario otra vez. Se preservan JWT, Argon2id, roles y restricciones por sucursal/cliente.

## Cambios relevantes para revisión

- Nuevos módulos sales, payments, tickets, invoices y reports; separación de modelos, esquemas, repositorios, servicios y rutas.
- Coordinador de pedidos existente, perfil de cliente atómico, `/auth/me` y consulta de sucursales cercanas.
- Migración aditiva `b27a913c6d02`, historial e idempotencia; conserva las cuatro migraciones previas.
- Reglas conservadoras: pago antes de preparación/entrega; una sola exhibición; cancelación pagada con devolución administrativa documentada; ventas históricas sin reserva verificable requieren conciliación.
- Documentación y evidencia en `TEST_RESULTS.md`, `DATABASE_MIGRATION_GUIDE.md`, `FRONTEND_INTEGRATION.md` y `PROJECT_SCOPE_COVERAGE.md`.

## Validación

Consultar el resultado final exacto y duración en TEST_RESULTS.md y los logs/XML incluidos. Se ejecutaron la suite original y ampliada, pruebas reales de concurrencia PostgreSQL, migraciones sobre el SQL aislado, rol NOBYPASSRLS, imports, OpenAPI y arranque Uvicorn. No se eliminaron funciones de prueba originales.

## Seguridad y despliegue

No se modificó Supabase ni se desplegó. Aplicar la nueva revisión sólo después de respaldo, conciliación y staging. Configurar expiración periódica de reservas. Los tickets no son CFDI; emisión fiscal y envío de correo quedan externos. No hay pasarelas ni datos de tarjetas. Los documentos de `docs/security` son evidencia histórica de la auditoría anterior; prevalece la documentación nueva para esta entrega.
