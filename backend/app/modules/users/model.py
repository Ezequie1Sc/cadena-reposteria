"""Modelo SQLAlchemy de usuarios."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    func,
    true,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    """Usuario del sistema de gestión de repostería."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
    )

    rol_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey(
            "roles.id",
            name="usuarios_rol_id_fkey",
        ),
        nullable=False,
    )

    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    apellido: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )