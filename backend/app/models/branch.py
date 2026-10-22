
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Branch(Base):
    """Modelo de sucursales de la cadena de repostería."""

    __tablename__ = "sucursales"

    __table_args__ = (
        CheckConstraint(
            "latitud IS NULL OR "
            "(latitud >= -90 AND latitud <= 90)",
            name="sucursales_latitud_check",
        ),
        CheckConstraint(
            "longitud IS NULL OR "
            "(longitud >= -180 AND longitud <= 180)",
            name="sucursales_longitud_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    codigo: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
    )

    direccion: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ciudad: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    estado: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    codigo_postal: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    latitud: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    longitud: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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
