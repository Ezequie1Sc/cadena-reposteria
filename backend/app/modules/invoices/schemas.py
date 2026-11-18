from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import Field, AwareDatetime, model_validator, EmailStr
from app.shared.commerce import StrictModel, ORMModel


class InvoiceCreate(StrictModel):
    venta_id: int = Field(gt=0)
    cliente_id: int = Field(gt=0)
    rfc: str = Field(pattern=r"^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$")
    razon_social: str = Field(min_length=3, max_length=255)
    uso_cfdi: str = Field(pattern=r"^[A-Z][0-9]{2}$")
    codigo_postal_fiscal: str = Field(pattern=r"^[0-9]{5}$")
    regimen_fiscal: str = Field(pattern=r"^[0-9]{3}$")
    tipo_persona: Literal["FISICA", "MORAL"]
    direccion_fiscal: str = Field(min_length=5, max_length=500)
    email_fiscal: EmailStr

    @model_validator(mode="after")
    def rfc_length(self):
        if len(self.rfc) != (13 if self.tipo_persona == "FISICA" else 12):
            raise ValueError("Longitud RFC incompatible con tipo de persona")
        return self


class InvoiceTransition(StrictModel):
    estado: Literal["EMITIDA", "CANCELADA"]
    motivo: str = Field(min_length=3, max_length=500)
    uuid: UUID | None = None
    proveedor: str | None = Field(default=None, min_length=3, max_length=100)
    referencia_proveedor: str | None = Field(default=None, min_length=3, max_length=255)
    fecha_emision: AwareDatetime | None = None

    @model_validator(mode="after")
    def evidence(self):
        if self.estado == "EMITIDA" and not all(
            (self.uuid, self.proveedor, self.referencia_proveedor, self.fecha_emision)
        ):
            raise ValueError(
                "Registrar emisión externa requiere UUID, proveedor, referencia y fecha"
            )
        if self.estado == "CANCELADA" and any(
            (self.uuid, self.proveedor, self.fecha_emision)
        ):
            raise ValueError("Cancelar no permite modificar datos de emisión")
        return self


class InvoiceResponse(ORMModel):
    id: int
    venta_id: int
    cliente_id: int
    rfc: str
    razon_social: str
    uso_cfdi: str | None
    codigo_postal_fiscal: str | None
    regimen_fiscal: str | None
    estado: str
    uuid: UUID | None
    proveedor: str | None
    referencia_proveedor: str | None
    fecha_emision: datetime | None
    created_at: datetime

    tipo_persona: str | None
    direccion_fiscal: str | None
    email_fiscal: str | None
