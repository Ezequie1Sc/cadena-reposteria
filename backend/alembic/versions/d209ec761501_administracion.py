"""Alta administrativa, imágenes gestionadas e incorporación. Sin backfill."""

from alembic import op

revision = "d209ec761501"
down_revision = "b27a913c6d02"
branch_labels = None
depends_on = None


def upgrade():
    # Un esquema no expuesto evita los grants automáticos del esquema public.
    op.execute("CREATE SCHEMA gestion_interna")
    op.execute("REVOKE ALL ON SCHEMA gestion_interna FROM PUBLIC")
    op.execute("""
        ALTER TABLE public.movimientos_inventario
        ADD COLUMN cantidad_anterior integer CHECK (cantidad_anterior >= 0),
        ADD COLUMN cantidad_nueva integer CHECK (cantidad_nueva >= 0)
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_usuario_email_normalizado ON public.usuarios(lower(btrim(email)))"
    )
    op.execute("""CREATE TABLE gestion_interna.recibo_foto(actor_id bigint REFERENCES public.usuarios,
                  clave text, respuesta jsonb NOT NULL, PRIMARY KEY(actor_id,clave))""")
    op.execute("""CREATE UNIQUE INDEX uq_imagen_principal
                  ON public.producto_imagenes(producto_id) WHERE es_principal""")
    op.execute("""
        CREATE TABLE gestion_interna.expediente (
            empleado_id bigint PRIMARY KEY REFERENCES public.empleados(id),
            email text NOT NULL,
            estado text NOT NULL CHECK (estado IN
              ('INVITADO','PENDIENTE','CORRECCION','APROBADO','RECHAZADO','REVOCADO')),
            token_hash text UNIQUE, vence timestamptz, codigo_hash text,
            codigo_vence timestamptz, siguiente_codigo timestamptz,
            intentos integer NOT NULL DEFAULT 0, envios integer NOT NULL DEFAULT 0,
            creado timestamptz NOT NULL DEFAULT now(), bienvenida_vista timestamptz
        )
    """)
    op.execute("""
        CREATE TABLE gestion_interna.evento (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            empleado_id bigint NOT NULL REFERENCES gestion_interna.expediente,
            actor_id bigint REFERENCES public.usuarios,
            accion text NOT NULL, motivo text, fecha timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""CREATE INDEX ix_evento_revocacion ON gestion_interna.evento(empleado_id,fecha DESC)
                  WHERE accion='REVOCADO'""")
    op.execute("""
        CREATE TABLE gestion_interna.correo (
            clave uuid PRIMARY KEY, empleado_id bigint NOT NULL REFERENCES gestion_interna.expediente,
            tipo text NOT NULL, contenido bytea, creado timestamptz NOT NULL DEFAULT now(),
            estado text NOT NULL DEFAULT 'LISTO', intentos integer NOT NULL DEFAULT 0,
            proximo timestamptz NOT NULL DEFAULT now(), proveedor_id text, error text
        )
    """)
    op.execute("""CREATE UNIQUE INDEX uq_bienvenida ON gestion_interna.correo(empleado_id)
                  WHERE tipo='bienvenida'""")
    op.execute(
        """CREATE INDEX ix_cola ON gestion_interna.correo(proximo) WHERE estado='LISTO'"""
    )
    op.execute("""
        CREATE TABLE gestion_interna.identidad (
            id integer PRIMARY KEY CHECK (id=1), datos jsonb NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE gestion_interna.beneficio (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, nombre text NOT NULL,
            condiciones text NOT NULL, activo boolean NOT NULL, inicio date, fin date,
            sucursal_id bigint REFERENCES public.sucursales, puesto text,
            empleado_id bigint REFERENCES public.empleados, CHECK (fin >= inicio)
        )
    """)
    op.execute("""
        CREATE TABLE gestion_interna.lote (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, actor_id bigint NOT NULL REFERENCES public.usuarios,
            huella text NOT NULL, filas jsonb NOT NULL, estado text NOT NULL DEFAULT 'PREVIO',
            UNIQUE(actor_id, huella)
        )
    """)
    op.execute("""
        CREATE TABLE gestion_interna.objeto (
            clave text PRIMARY KEY, producto_id bigint REFERENCES public.productos,
            imagen_id bigint UNIQUE REFERENCES public.producto_imagenes ON DELETE SET NULL,
            estado text NOT NULL CHECK (estado IN ('PREPARADO','VIGENTE','RETIRADO')),
            revisar timestamptz NOT NULL DEFAULT now() + interval '1 day'
        )
    """)

    # Protege las cuentas nuevas incluso ante un rollback del binario a un CRUD anterior.
    op.execute("""
        CREATE FUNCTION gestion_interna.validar_usuario() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
        DECLARE etapa text;
        BEGIN
          SELECT x.estado INTO etapa FROM gestion_interna.expediente x
          JOIN public.empleados e ON e.id=x.empleado_id WHERE e.usuario_id=NEW.id;
          IF FOUND AND ((NEW.activo AND (etapa <> 'APROBADO' OR NOT EXISTS (
                          SELECT 1 FROM public.roles r WHERE r.id=NEW.rol_id AND r.nombre='Empleado' AND r.activo
                        ))) OR NEW.rol_id IS DISTINCT FROM OLD.rol_id
                        OR NEW.email IS DISTINCT FROM OLD.email) THEN
            RAISE EXCEPTION 'Cambio incompatible con la incorporación' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER dg_proteger_usuario BEFORE UPDATE OF activo,rol_id,email
        ON public.usuarios FOR EACH ROW EXECUTE FUNCTION gestion_interna.validar_usuario()""")
    op.execute("""
        CREATE FUNCTION gestion_interna.validar_empleado() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
        DECLARE etapa text;
        BEGIN
          SELECT estado INTO etapa FROM gestion_interna.expediente WHERE empleado_id=OLD.id;
          IF FOUND AND ((NEW.activo AND etapa <> 'APROBADO') OR NEW.usuario_id <> OLD.usuario_id
                        OR NEW.numero_empleado <> OLD.numero_empleado) THEN
            RAISE EXCEPTION 'Cambio incompatible con la incorporación' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER dg_proteger_empleado BEFORE UPDATE OF activo,usuario_id,numero_empleado
        ON public.empleados FOR EACH ROW EXECUTE FUNCTION gestion_interna.validar_empleado()""")


def downgrade():
    # Evita un rollback que perdería decisiones, correos o referencias vigentes.
    raise RuntimeError(
        "Requiere respaldo y reversión supervisada de datos de incorporación"
    )
