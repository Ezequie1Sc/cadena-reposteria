
"""Modelos de inventarios y movimientos de la cadena de repostería."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Inventory(Base):
    """Existencias de un producto en una sucursal."""

    __tablename__ = "inventarios"

    __table_args__ = (
        UniqueConstraint(
            "producto_id",
            "sucursal_id",
            name="inventarios_producto_id_sucursal_id_key",
        ),
        CheckConstraint(
            "cantidad >= 0",
            name="inventarios_cantidad_check",
        ),
        CheckConstraint(
            "stock_minimo >= 0",
            name="inventarios_stock_minimo_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    producto_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("productos.id"),
        nullable=False,
    )

    sucursal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sucursales.id"),
        nullable=False,
    )

    cantidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    stock_minimo: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    movimientos: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="inventario",
    )


class InventoryMovement(Base):
    """Registro histórico de movimientos de inventario."""

    __tablename__ = "movimientos_inventario"

    __table_args__ = (
        CheckConstraint(
            "cantidad > 0",
            name="movimientos_inventario_cantidad_check",
        ),
        CheckConstraint(
            "tipo IN ("
            "'ENTRADA', "
            "'SALIDA', "
            "'VENTA', "
            "'AJUSTE', "
            "'TRASPASO'"
            ")",
            name="movimientos_inventario_tipo_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    inventario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inventarios.id"),
        nullable=False,
    )

    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    cantidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    motivo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    referencia_tipo: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    referencia_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    usuario_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    inventario: Mapped[Inventory] = relationship(
        "Inventory",
        back_populates="movimientos",
    )
