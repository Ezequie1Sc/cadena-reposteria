"""Persistencia de idempotencia y trazabilidad; sin datos bancarios."""

from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class CommercialEvent(Base):
    __tablename__ = "historial_comercial"
    __table_args__ = (Index("ix_historial_recurso", "recurso", "recurso_id", "id"),)
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    recurso: Mapped[str] = mapped_column(String(20))
    recurso_id: Mapped[int] = mapped_column(BigInteger)
    anterior: Mapped[str | None] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(20))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    motivo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IdempotencyRecord(Base):
    __tablename__ = "operaciones_idempotentes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "operacion", "clave", name="uq_operacion_clave"),
    )
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    operacion: Mapped[str] = mapped_column(String(30))
    clave: Mapped[str] = mapped_column(String(100))
    huella: Mapped[str] = mapped_column(String(64))
    recurso_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
