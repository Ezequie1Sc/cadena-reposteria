"""Pagos manuales sobre las tablas del esquema de referencia."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Boolean,
    CheckConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class PaymentMethod(Base):
    __tablename__ = "metodos_pago"
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(60))
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )


class Payment(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="pagos_monto_check"),
        CheckConstraint(
            "proveedor IN ('INTERNO','STRIPE','OTRO')", name="pagos_proveedor_check"
        ),
        CheckConstraint(
            "estado IN ('PENDIENTE','EN_PROCESO','APROBADO','RECHAZADO','VENCIDO','REEMBOLSADO','CANCELADO')",
            name="pagos_estado_check",
        ),
        Index(
            "uq_pago_activo_venta",
            "venta_id",
            unique=True,
            postgresql_where=text("estado IN ('PENDIENTE','EN_PROCESO','APROBADO')"),
            sqlite_where=text("estado IN ('PENDIENTE','EN_PROCESO','APROBADO')"),
        ),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"))
    metodo_pago_id: Mapped[int] = mapped_column(ForeignKey("metodos_pago.id"))
    proveedor: Mapped[str] = mapped_column(
        String(30), default="INTERNO", server_default="INTERNO"
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="MXN", server_default="MXN")
    estado: Mapped[str] = mapped_column(
        String(20), default="PENDIENTE", server_default="PENDIENTE"
    )
    referencia: Mapped[str | None] = mapped_column(String(255))
    proveedor_payment_id: Mapped[str | None] = mapped_column(String(255))
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
