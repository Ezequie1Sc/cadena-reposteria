from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Uuid,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Invoice(Base):
    __tablename__ = "facturas"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE','EMITIDA','CANCELADA')",
            name="facturas_estado_check",
        ),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"), unique=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    rfc: Mapped[str] = mapped_column(String(13))
    razon_social: Mapped[str] = mapped_column(String(255))
    uso_cfdi: Mapped[str | None] = mapped_column(String(10))
    uuid: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    proveedor: Mapped[str | None] = mapped_column(String(100))
    referencia_proveedor: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(
        String(20), default="PENDIENTE", server_default="PENDIENTE"
    )
    fecha_emision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    codigo_postal_fiscal: Mapped[str | None] = mapped_column(String(5))
    regimen_fiscal: Mapped[str | None] = mapped_column(String(3))

    tipo_persona: Mapped[str | None] = mapped_column(String(10))
    direccion_fiscal: Mapped[str | None] = mapped_column(String(500))
    email_fiscal: Mapped[str | None] = mapped_column(String(254))
