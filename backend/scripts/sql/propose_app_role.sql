-- REVIEW ONLY. No production execution was performed during the audit.
-- Existing schema, migrations and enabled RLS are prerequisites.
-- The final ROLLBACK intentionally makes this a dry-run transaction.
-- A DBA must review inherited PUBLIC grants/functions and all existing policies.
BEGIN;
CREATE ROLE reposteria_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO reposteria_app;
DO $$ BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO reposteria_app', current_database());
END $$;
GRANT SELECT ON public.roles TO reposteria_app;
-- SELECT FOR UPDATE in UserService._lock_admin_role requires UPDATE privilege.
-- No API changes role IDs; only this column is granted, not role names/flags.
GRANT UPDATE(id) ON public.roles TO reposteria_app;
GRANT SELECT, INSERT, UPDATE ON public.usuarios, public.clientes, public.empleados,
    public.sucursales, public.categorias, public.productos, public.inventarios,
    public.pedidos, public.auth_rate_limits, public.ventas, public.pagos, public.facturas TO reposteria_app;
GRANT SELECT ON public.metodos_pago TO reposteria_app;
GRANT UPDATE(id) ON public.metodos_pago TO reposteria_app;
GRANT SELECT, INSERT ON public.detalle_ventas, public.tickets, public.historial_comercial, public.operaciones_idempotentes TO reposteria_app;
GRANT SELECT, INSERT ON public.detalle_pedidos, public.movimientos_inventario TO reposteria_app;
-- No DELETE, TRUNCATE, DDL, ownership, memberships or future-object grants.
-- Only sequences actually owned by the listed INSERT tables.
DO $$
DECLARE item record;
BEGIN
    FOR item IN
        SELECT DISTINCT seq.oid::regclass AS sequence_name
        FROM pg_class seq
        JOIN pg_depend dep ON dep.objid=seq.oid AND dep.classid='pg_class'::regclass
        JOIN pg_class tab ON dep.refobjid=tab.oid
        JOIN pg_namespace ns ON ns.oid=tab.relnamespace
        WHERE seq.relkind='S' AND dep.deptype IN ('a','i') AND ns.nspname='public'
          AND tab.relname = ANY(ARRAY['usuarios','clientes','empleados','sucursales',
              'categorias','productos','inventarios','pedidos','detalle_pedidos','movimientos_inventario',
              'ventas','detalle_ventas','pagos','facturas','tickets','historial_comercial','operaciones_idempotentes'])
    LOOP
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO reposteria_app',item.sequence_name);
    END LOOP;
END $$;
-- A backend-only service role. These policies permit the backend's required rows;
-- JWT, ownership and branch restrictions remain enforced by FastAPI, not auth.uid().
-- No policies or privileges are added to anon/authenticated/service_role.
DO $$
DECLARE target text;
BEGIN
    FOREACH target IN ARRAY ARRAY['roles','usuarios','clientes','empleados','sucursales',
        'categorias','productos','inventarios','pedidos','detalle_pedidos',
        'movimientos_inventario','auth_rate_limits','ventas','detalle_ventas','pagos','metodos_pago',
        'tickets','facturas','historial_comercial','operaciones_idempotentes']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=target AND c.relrowsecurity) THEN
            RAISE EXCEPTION 'RLS must already be enabled on public.%', target;
        END IF;
        EXECUTE format('CREATE POLICY reposteria_backend_select ON public.%I FOR SELECT TO reposteria_app USING (true)',target);
        IF target NOT IN ('roles','metodos_pago') THEN
            EXECUTE format('CREATE POLICY reposteria_backend_insert ON public.%I FOR INSERT TO reposteria_app WITH CHECK (true)',target);
        END IF;
        IF target NOT IN ('detalle_pedidos','movimientos_inventario','detalle_ventas','tickets','historial_comercial','operaciones_idempotentes') THEN
            EXECUTE format('CREATE POLICY reposteria_backend_update ON public.%I FOR UPDATE TO reposteria_app USING (true) WITH CHECK (true)',target);
        END IF;
    END LOOP;
END $$;
-- Do not grant this role to anon/authenticated/authenticator or application users.
-- Keep NOLOGIN until an approved staging credential is provisioned separately.
-- Replace ROLLBACK with COMMIT only after review in an independently approved change.
ROLLBACK;
