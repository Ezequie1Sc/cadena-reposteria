"""Mapeo de ventas existentes y detalles históricos."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Sale(Base):
    __tablename__ = "ventas"
    __table_args__ = (
        CheckConstraint("tipo IN ('FISICA','EN_LINEA')", name="ventas_tipo_check"),
        CheckConstraint(
            "estado IN ('PENDIENTE','CONFIRMADA','CANCELADA')",
            name="ventas_estado_check",
        ),
        CheckConstraint(
            "subtotal >= 0 AND descuento >= 0 AND total >= 0",
            name="ventas_importes_check",
        ),
        CheckConstraint(
            "tipo <> 'FISICA' OR empleado_id IS NOT NULL", name="ventas_empleado_check"
        ),
        CheckConstraint(
            "tipo <> 'EN_LINEA' OR cliente_id IS NOT NULL", name="ventas_cliente_check"
        ),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    numero_venta: Mapped[str] = mapped_column(String(40), unique=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"))
    empleado_id: Mapped[int | None] = mapped_column(ForeignKey("empleados.id"))
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursales.id"))
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos.id"), unique=True)
    tipo: Mapped[str] = mapped_column(String(10))
    estado: Mapped[str] = mapped_column(
        String(20), default="PENDIENTE", server_default="PENDIENTE"
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    vence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detalles: Mapped[list["SaleDetail"]] = relationship(
        back_populates="venta", lazy="selectin"
    )


class SaleDetail(Base):
    __tablename__ = "detalle_ventas"
    __table_args__ = (
        CheckConstraint(
            "cantidad > 0 AND precio_unitario >= 0 AND descuento >= 0 AND subtotal >= 0",
            name="detalle_venta_importes_check",
        ),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    descuento: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, server_default="0"
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    producto_nombre: Mapped[str | None] = mapped_column(String(150))
    producto_sku: Mapped[str | None] = mapped_column(String(50))
    venta: Mapped[Sale] = relationship(back_populates="detalles")
