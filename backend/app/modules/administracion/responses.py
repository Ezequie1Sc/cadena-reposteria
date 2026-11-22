"""Contratos de lectura para el panel y para el cliente generado desde OpenAPI."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.products.schemas import ProductResponse


class StockSummary(BaseModel):
    id: int
    sucursal_id: int
    cantidad: int
    stock_minimo: int


class RegisteredProduct(BaseModel):
    producto: ProductResponse
    inventarios: list[StockSummary]


class Photo(BaseModel):
    producto_id: int
    imagen_id: int
    url: str


class ProductWithPhoto(RegisteredProduct, Photo):
    pass


class EmployeeProfile(BaseModel):
    empleado_id: int
    usuario_id: int
    estado: str
    email: str
    creado: datetime
    bienvenida_vista: datetime | None
    numero_empleado: str
    puesto: str
    sucursal_id: int
    sucursal: str
    nombre: str
    apellido: str


class ReviewEvent(BaseModel):
    accion: str
    actor_id: int | None
    fecha: datetime
    motivo: str | None


class Status(BaseModel):
    estado: str


class BatchStatus(Status):
    id: int


class ImportRow(BaseModel):
    fila: int
    estado: str
    datos: dict[str, str]
    error: str | None
    empleado_id: int | None = None


class ImportResult(BatchStatus):
    filas: list[ImportRow]


class MovementReceipt(BaseModel):
    inventario_id: int
    tipo: str
    confirmado: bool
