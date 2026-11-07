
"""Modelos de pedidos y detalles de pedidos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Order(Base):
    """Pedido realizado por un cliente en una sucursal."""

    __tablename__ = "pedidos"

    __table_args__ = (
        UniqueConstraint(
            "numero_pedido",
            name="pedidos_numero_pedido_key",
        ),
        CheckConstraint(
            "estado IN ("
            "'PENDIENTE', "
            "'CONFIRMADO', "
            "'PREPARANDO', "
            "'LISTO', "
            "'ENTREGADO', "
            "'CANCELADO'"
            ")",
            name="pedidos_estado_check",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="pedidos_subtotal_check",
        ),
        CheckConstraint(
            "descuento >= 0",
            name="pedidos_descuento_check",
        ),
        CheckConstraint(
            "total >= 0",
            name="pedidos_total_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
    )

    numero_pedido: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    cliente_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "clientes.id",
            name="pedidos_cliente_id_fkey",
        ),
        nullable=False,
    )

    sucursal_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "sucursales.id",
            name="pedidos_sucursal_id_fkey",
        ),
        nullable=False,
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDIENTE",
        server_default="PENDIENTE",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
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

    __table_args__ = (
        CheckConstraint(
            "cantidad > 0",
            name="detalle_pedidos_cantidad_check",
        ),
        CheckConstraint(
            "precio_unitario >= 0",
            name="detalle_pedidos_precio_unitario_check",
        ),
        CheckConstraint(
            "descuento >= 0",
            name="detalle_pedidos_descuento_check",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="detalle_pedidos_subtotal_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
    )

    pedido_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "pedidos.id",
            name="detalle_pedidos_pedido_id_fkey",
        ),
        nullable=False,
    )

    producto_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "productos.id",
            name="detalle_pedidos_producto_id_fkey",
        ),
        nullable=False,
    )

    cantidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    pedido: Mapped[Order] = relationship(
        "Order",
        back_populates="detalles",
    )
