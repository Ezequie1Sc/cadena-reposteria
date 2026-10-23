
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


CustomerName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=100,
    ),
]

CustomerLastName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]

CustomerEmail = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=254,
    ),
]

CustomerPhone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=7,
        max_length=20,
        pattern=r"^\+?[0-9\s()-]+$",
    ),
]


class CustomerBase(BaseModel):
    """Campos compartidos del cliente."""

    nombre: CustomerName

    apellido: CustomerLastName | None = None

    email: CustomerEmail | None = None

    telefono: CustomerPhone | None = None

    fecha_nacimiento: date | None = None

    usuario_id: int | None = Field(
        default=None,
        gt=0,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.lower()

        # Validación básica sin dependencias adicionales.
        if (
            value.count("@") != 1
            or "." not in value.split("@")[1]
            or " " in value
        ):
            raise ValueError(
                "El correo electrónico no es válido."
            )

        return value

    @field_validator("fecha_nacimiento")
    @classmethod
    def validate_birth_date(
        cls,
        value: date | None,
    ) -> date | None:
        if value is not None and value > date.today():
            raise ValueError(
                "La fecha de nacimiento no puede ser futura."
            )

        return value


class CustomerCreate(CustomerBase):
    """Datos requeridos para registrar un cliente."""

    pass


class CustomerUpdate(BaseModel):
    """Actualización parcial de un cliente."""

    model_config = ConfigDict(extra="forbid")

    nombre: CustomerName | None = None

    apellido: CustomerLastName | None = None

    email: CustomerEmail | None = None

    telefono: CustomerPhone | None = None

    fecha_nacimiento: date | None = None

    usuario_id: int | None = Field(
        default=None,
        gt=0,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return CustomerBase.validate_email(value)

    @field_validator("fecha_nacimiento")
    @classmethod
    def validate_birth_date(
        cls,
        value: date | None,
    ) -> date | None:
        return CustomerBase.validate_birth_date(value)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError(
                "Debe proporcionar al menos un campo para actualizar."
            )

        if (
            "nombre" in self.model_fields_set
            and self.nombre is None
        ):
            raise ValueError(
                "El nombre del cliente no puede ser nulo."
            )

        return self


class CustomerResponse(CustomerBase):
    """Representación pública del cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: int

    activo: bool

    created_at: datetime


class CustomerListResponse(BaseModel):
    """Listado paginado de clientes."""

    items: list[CustomerResponse]

    total: int = Field(ge=0)

    page: int = Field(ge=1)

    page_size: int = Field(ge=1)
