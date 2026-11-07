
"""Esquemas Pydantic para la gestión de pedidos."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class OrderStatus(str, Enum):
    """Estados permitidos para un pedido."""

    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    PREPARANDO = "PREPARANDO"
    LISTO = "LISTO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class OrderItemCreate(BaseModel):
    """Producto solicitado en un pedido."""

    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class OrderCreate(BaseModel):
    """Datos necesarios para registrar un pedido."""

    cliente_id: int = Field(gt=0)
    sucursal_id: int = Field(gt=0)

    productos: list[OrderItemCreate] = Field(
        min_length=1,
        max_length=100,
    )

    direccion_entrega: str | None = Field(
        default=None,
        max_length=1000,
    )

    notas: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("productos")
    @classmethod
    def validate_unique_products(
        cls,
        products: list[OrderItemCreate],
    ) -> list[OrderItemCreate]:
        """Evitar productos duplicados en un mismo pedido."""

        product_ids = [
            product.producto_id
            for product in products
        ]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError(
                "No se permiten productos duplicados en el pedido."
            )

        return products


class OrderDetailResponse(BaseModel):
    """Detalle de un producto incluido en un pedido."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pedido_id: int
    producto_id: int
    cantidad: int
    precio_unitario: Decimal
    descuento: Decimal
    subtotal: Decimal


class OrderResponse(BaseModel):
    """Información completa de un pedido."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    numero_pedido: str
    cliente_id: int
    sucursal_id: int
    estado: OrderStatus

    subtotal: Decimal
    descuento: Decimal
    total: Decimal

    direccion_entrega: str | None = None
    notas: str | None = None

    fecha_pedido: datetime
    created_at: datetime
    updated_at: datetime

    detalles: list[OrderDetailResponse] = Field(
        default_factory=list,
    )


class OrderListResponse(BaseModel):
    """Respuesta para consultar múltiples pedidos."""

    total: int
    pedidos: list[OrderResponse]


class OrderStatusUpdate(BaseModel):
    """Solicitud para actualizar el estado de un pedido."""

    estado: OrderStatus
