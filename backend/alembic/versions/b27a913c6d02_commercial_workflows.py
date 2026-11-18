"""Add manual commercial workflows to the existing Supabase schema.

Revision ID: b27a913c6d02
Revises: 974e270dd2f1
No historical records are rewritten. Incompatible duplicate active payments
cause the migration transaction to fail for manual reconciliation.
"""

from alembic import op
import sqlalchemy as sa

revision = "b27a913c6d02"
down_revision = "974e270dd2f1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ventas", sa.Column("vence_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "detalle_ventas", sa.Column("producto_nombre", sa.String(150), nullable=True)
    )
    op.add_column(
        "detalle_ventas", sa.Column("producto_sku", sa.String(50), nullable=True)
    )
    op.add_column("pagos", sa.Column("confirmado_por", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "pagos_confirmado_por_fkey", "pagos", "usuarios", ["confirmado_por"], ["id"]
    )
    for name, typ in [
        ("codigo_postal_fiscal", sa.String(5)),
        ("regimen_fiscal", sa.String(3)),
        ("tipo_persona", sa.String(10)),
        ("direccion_fiscal", sa.String(500)),
        ("email_fiscal", sa.String(254)),
    ]:
        op.add_column("facturas", sa.Column(name, typ, nullable=True))
    op.create_index(
        "uq_pago_activo_venta",
        "pagos",
        ["venta_id"],
        unique=True,
        postgresql_where=sa.text("estado IN ('PENDIENTE','EN_PROCESO','APROBADO')"),
    )
    op.create_index(
        "ix_ventas_pendientes_vencimiento", "ventas", ["estado", "vence_at"]
    )
    op.create_index("ix_pagos_confirmados_fecha", "pagos", ["estado", "paid_at"])
    op.create_table(
        "historial_comercial",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("recurso", sa.String(20), nullable=False),
        sa.Column("recurso_id", sa.BigInteger(), nullable=False),
        sa.Column("anterior", sa.String(20)),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column(
            "usuario_id", sa.BigInteger(), sa.ForeignKey("usuarios.id"), nullable=False
        ),
        sa.Column("motivo", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_historial_recurso", "historial_comercial", ["recurso", "recurso_id", "id"]
    )
    op.create_table(
        "operaciones_idempotentes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "usuario_id", sa.BigInteger(), sa.ForeignKey("usuarios.id"), nullable=False
        ),
        sa.Column("operacion", sa.String(30), nullable=False),
        sa.Column("clave", sa.String(100), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("recurso_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "usuario_id", "operacion", "clave", name="uq_operacion_clave"
        ),
    )
    # Newly introduced tables are denied through Supabase Data API by default.
    op.execute("ALTER TABLE historial_comercial ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operaciones_idempotentes ENABLE ROW LEVEL SECURITY")
    # Only add the missing manual method. Do not alter existing methods or IDs.
    op.execute(
        "INSERT INTO metodos_pago(codigo,nombre,activo) VALUES ('DEPOSITO','Depósito bancario',true) ON CONFLICT(codigo) DO NOTHING"
    )


def downgrade():
    raise RuntimeError(
        "Migration retains commercial audit data. Use a reviewed backup/forward-fix plan; automatic downgrade is intentionally unavailable."
    )
