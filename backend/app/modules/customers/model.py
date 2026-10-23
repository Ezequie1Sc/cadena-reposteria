
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Customer(Base):
    """Modelo de clientes de la cadena de repostería."""

    __tablename__ = "clientes"

    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            name="clientes_usuario_id_key",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
    )

    usuario_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "usuarios.id",
            name="clientes_usuario_id_fkey",
        ),
        nullable=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    apellido: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    fecha_nacimiento: Mapped[date | None] = mapped_column(
        Date,
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
