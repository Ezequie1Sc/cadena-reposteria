from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"), unique=True)
    numero_ticket: Mapped[str] = mapped_column(String(50), unique=True)
    fecha_emision: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
