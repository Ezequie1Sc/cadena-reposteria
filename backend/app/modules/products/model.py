
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.modules.categories.model import Category


class Product(Base):
    """Modelo de productos de la cadena de repostería."""

    __tablename__ = "productos"

    __table_args__ = (
        Index(
            "idx_productos_categoria",
            "categoria_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=True),
        primary_key=True,
        autoincrement=True,
    )

    categoria_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("categorias.id"),
        nullable=False,
    )

    nombre: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sku: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    precio: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    imagen_url: Mapped[str | None] = mapped_column(
        Text,
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
    )

    categoria: Mapped[Category] = relationship(
        "Category",
        back_populates="productos",
    )


class ProductImage(Base):
    """Mapeo de la tabla comprobada en Supabase."""
    __tablename__ = "producto_imagenes"
    __table_args__ = (CheckConstraint("orden >= 0", name="producto_imagenes_orden_check"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer,"sqlite"), Identity(always=True), primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text,nullable=False)
    es_principal: Mapped[bool] = mapped_column(Boolean,server_default="false",nullable=False)
    orden: Mapped[int] = mapped_column(Integer,server_default="0",nullable=False)
