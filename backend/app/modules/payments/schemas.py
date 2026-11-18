from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import Field, model_validator
from app.shared.commerce import StrictModel, ORMModel


class PaymentCreate(StrictModel):
    venta_id: int | None = Field(default=None, gt=0)
    pedido_id: int | None = Field(default=None, gt=0)
    metodo: Literal["EFECTIVO", "SPEI", "DEPOSITO", "TARJETA"]
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    referencia: str | None = Field(default=None, min_length=3, max_length=255)

    @model_validator(mode="after")
    def consistent(self):
        if (self.venta_id is None) == (self.pedido_id is None):
            raise ValueError("Indica venta_id o pedido_id, exclusivamente")
        if self.metodo != "EFECTIVO" and not self.referencia:
            raise ValueError("Referencia requerida para pago no efectivo")
        return self


class PaymentTransition(StrictModel):
    estado: Literal["APROBADO", "RECHAZADO", "CANCELADO"]
    motivo: str = Field(min_length=3, max_length=500)


class PaymentResponse(ORMModel):
    id: int
    venta_id: int
    metodo_pago_id: int
    proveedor: str
    monto: Decimal
    moneda: str
    estado: str
    referencia: str | None
    paid_at: datetime | None
    confirmado_por: int | None
    created_at: datetime


class PaymentList(ORMModel):
    total: int
    pagos: list[PaymentResponse]


class MethodResponse(ORMModel):
    id: int
    codigo: str
    nombre: str
