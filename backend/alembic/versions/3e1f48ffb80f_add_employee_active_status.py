"""add employee active status

Revision ID: 3e1f48ffb80f
Revises: 3539360e0e34
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3e1f48ffb80f"
down_revision: Union[str, Sequence[str], None] = "3539360e0e34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar columna activo a la tabla empleados."""

    op.add_column(
        "empleados",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    """Eliminar columna activo de la tabla empleados."""

    op.drop_column(
        "empleados",
        "activo",
    )