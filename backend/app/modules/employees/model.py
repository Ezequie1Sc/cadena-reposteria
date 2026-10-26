"""Modelo SQLAlchemy para empleados."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Employee(Base):
    """Representa a un empleado de la cadena de repostería."""

    __tablename__ = "empleados"

    __table_args__ = (
        Index(
            "idx_empleados_sucursal",
            "sucursal_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
    )

    usuario_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("usuarios.id"),
        nullable=False,
        unique=True,
    )

    sucursal_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("sucursales.id"),
        nullable=False,
    )

    numero_empleado: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
    )

    puesto: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
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