
"""Baseline del esquema existente de Supabase.

Revision ID: 404a9071350b
Revises:
Create Date: 2026-10-21 21:41:12.727033

Esta migración establece el punto de partida de Alembic.

Las tablas ya existen en Supabase, por lo que no se realizan
operaciones de creación, modificación ni eliminación.
"""

from typing import Sequence, Union


# Identificadores de revisión de Alembic.
revision: str = "404a9071350b"

down_revision: Union[str, Sequence[str], None] = None

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Conservar el esquema existente sin modificaciones."""
    pass


def downgrade() -> None:
    """No modificar las tablas existentes de Supabase."""
    pass
