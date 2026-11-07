
"""Modelos de pedidos y detalles de pedidos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Order(Base):
    """Pedido realizado por un cliente en una sucursal."""

    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    numero_pedido: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    cliente_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clientes.id"),
        nullable=False,
    )

    sucursal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sucursales.id"),
        nullable=False,
    )

    estado: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="PENDIENTE",
        server_default="PENDIENTE",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    descuento: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    direccion_entrega: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    fecha_pedido: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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

    detalles: Mapped[list[OrderDetail]] = relationship(
        "OrderDetail",
        back_populates="pedido",
    )


class OrderDetail(Base):
    """Producto y cantidades asociados a un pedido."""

    __tablename__ = "detalle_pedidos"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    pedido_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pedidos.id"),
        nullable=False,
    )

    producto_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("productos.id"),
        nullable=False,
    )

    cantidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    descuento: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    pedido: Mapped[Order] = relationship(
        "Order",
        back_populates="detalles",
    )
