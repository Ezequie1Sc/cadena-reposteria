"""Referencia a la tabla de roles existente en PostgreSQL."""

from sqlalchemy import BigInteger, Column, Table

from app.db.session import Base


roles_reference = Table(
    "roles",
    Base.metadata,
    Column(
        "id",
        BigInteger,
        primary_key=True,
    ),
    info={"reference_only": True},
)