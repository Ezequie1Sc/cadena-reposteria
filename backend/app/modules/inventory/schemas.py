
"""Esquemas de validación para inventarios y movimientos."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MovementType(str, Enum):
    ENTRADA = "ENTRADA"
    SALIDA = "SALIDA"
    VENTA = "VENTA"
    AJUSTE = "AJUSTE"
    TRASPASO = "TRASPASO"


class InventoryCreate(BaseModel):
    producto_id: int = Field(gt=0)
    sucursal_id: int = Field(gt=0)
    stock_minimo: int = Field(default=0, ge=0)


class InventoryUpdate(BaseModel):
    stock_minimo: int = Field(ge=0)


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    producto_id: int
    sucursal_id: int
    cantidad: int
    stock_minimo: int
    updated_at: datetime


class InventoryListResponse(BaseModel):
    total: int
    inventarios: list[InventoryResponse]


class InventoryMovementCreate(BaseModel):
    cantidad: int = Field(gt=0)
    motivo: str | None = Field(
        default=None,
        max_length=255,
    )


class InventoryAdjustmentCreate(BaseModel):
    cantidad_final: int = Field(ge=0)
    motivo: str = Field(min_length=1, max_length=255)


class InventoryTransferCreate(BaseModel):
    sucursal_destino_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)
    motivo: str | None = Field(
        default=None,
        max_length=255,
    )


class InventoryMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventario_id: int
    tipo: MovementType
    cantidad: int
    motivo: str | None
    referencia_tipo: str | None
    referencia_id: int | None
    usuario_id: int | None
    created_at: datetime


class InventoryMovementListResponse(BaseModel):
    total: int
    movimientos: list[InventoryMovementResponse]


class InventoryTransferResponse(BaseModel):
    origen: InventoryResponse
    destino: InventoryResponse
