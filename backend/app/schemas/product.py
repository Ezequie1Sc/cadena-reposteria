
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductResponse(BaseModel):
    id: int
    categoria_id: int
    nombre: str
    descripcion: str | None = None
    sku: str
    precio: Decimal
    imagen_url: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    total: int
    productos: list[ProductResponse]


class ProductCreate(BaseModel):
    categoria_id: int = Field(gt=0)
    nombre: str = Field(min_length=2, max_length=150)
    descripcion: str | None = None
    sku: str = Field(min_length=1, max_length=100)
    precio: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    imagen_url: str | None = None
