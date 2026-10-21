
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    """Campos compartidos de los productos."""

    model_config = ConfigDict(extra="forbid")

    categoria_id: int = Field(
        gt=0,
        description="Identificador de la categoría",
    )

    nombre: str = Field(
        min_length=2,
        max_length=150,
        description="Nombre del producto",
    )

    descripcion: str | None = None

    sku: str = Field(
        min_length=1,
        max_length=50,
        description="Código único del producto",
    )

    precio: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Precio del producto",
    )

    imagen_url: str | None = None


class ProductCreate(ProductBase):
    """Datos necesarios para registrar un producto."""

    pass


class ProductUpdate(BaseModel):
    """Campos opcionales para actualizar un producto."""

    model_config = ConfigDict(extra="forbid")

    categoria_id: int | None = Field(
        default=None,
        gt=0,
    )

    nombre: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    descripcion: str | None = None

    sku: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    precio: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )

    imagen_url: str | None = None


class ProductResponse(ProductBase):
    """Representación pública de un producto."""

    id: int
    activo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


class ProductListResponse(BaseModel):
    """Respuesta paginada o agrupada del catálogo."""

    total: int
    productos: list[ProductResponse]
