-- READ-ONLY diagnostic, reviewed separately before using against real Supabase.
BEGIN TRANSACTION READ ONLY;
SELECT current_user, session_user, current_setting('row_security') AS row_security,
       rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
FROM pg_roles WHERE rolname=current_user;
SELECT id,nombre,activo FROM public.roles ORDER BY id;
SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity,c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname;
SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check
FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname;
SELECT table_name,grantee,privilege_type FROM information_schema.table_privileges
WHERE table_schema='public' ORDER BY table_name,grantee,privilege_type;
SELECT r.rolname AS granted_role,m.rolname AS member
FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member;
SELECT n.nspname,p.proname,p.prosecdef,pg_get_userbyid(p.proowner) AS owner,p.proacl
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public';
SELECT version_num FROM public.alembic_version;
COMMIT;
