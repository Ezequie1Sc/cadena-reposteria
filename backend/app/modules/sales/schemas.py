from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import Field, field_validator
from app.shared.commerce import StrictModel, ORMModel
from app.modules.orders.schemas import OrderItemCreate, OrderCreate


class SaleCreate(StrictModel):
    sucursal_id: int = Field(gt=0)
    empleado_id: int | None = Field(default=None, gt=0)
    cliente_id: int | None = Field(default=None, gt=0)
    productos: list[OrderItemCreate] = Field(min_length=1, max_length=100)
    _unique = field_validator("productos")(
        OrderCreate.validate_unique_products.__func__
    )


class SaleDetailResponse(ORMModel):
    id: int
    producto_id: int
    producto_nombre: str | None
    producto_sku: str | None
    cantidad: int
    precio_unitario: Decimal
    descuento: Decimal
    subtotal: Decimal


class SaleResponse(ORMModel):
    id: int
    numero_venta: str
    cliente_id: int | None
    empleado_id: int | None
    sucursal_id: int
    pedido_id: int | None
    tipo: Literal["FISICA", "EN_LINEA"]
    estado: Literal["PENDIENTE", "CONFIRMADA", "CANCELADA"]
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    fecha: datetime
    vence_at: datetime | None
    detalles: list[SaleDetailResponse]


class SaleList(ORMModel):
    total: int
    ventas: list[SaleResponse]


class ExpirationResponse(ORMModel):
    ventas_canceladas: list[int]
