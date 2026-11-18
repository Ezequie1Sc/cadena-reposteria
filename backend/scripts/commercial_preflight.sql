-- Read-only. Run before the new migration with an authorized DBA.
SELECT version_num FROM alembic_version;
SELECT current_user, rolbypassrls, rolsuper FROM pg_roles WHERE rolname=current_user;
SELECT venta_id, COUNT(*) AS pagos_activos FROM pagos
WHERE estado IN ('PENDIENTE','EN_PROCESO','APROBADO') GROUP BY venta_id HAVING COUNT(*)>1;
SELECT p.id,p.venta_id,p.monto,v.total,p.estado,v.estado AS estado_venta FROM pagos p
JOIN ventas v ON v.id=p.venta_id WHERE p.estado='APROBADO' AND (p.monto<>v.total OR v.estado<>'CONFIRMADA');
SELECT codigo,activo FROM metodos_pago ORDER BY id;
SELECT table_name,column_name,data_type FROM information_schema.columns
WHERE table_schema='public' AND table_name IN ('ventas','detalle_ventas','pagos','facturas') ORDER BY table_name,ordinal_position;
