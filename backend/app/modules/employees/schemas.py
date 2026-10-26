"""Esquemas Pydantic para la administración de empleados."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class EmployeeBase(BaseModel):
    """Campos compartidos para registrar empleados."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    usuario_id: int = Field(gt=0)
    sucursal_id: int = Field(gt=0)

    numero_empleado: str = Field(
        min_length=1,
        max_length=30,
    )

    puesto: str = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("numero_empleado")
    @classmethod
    def normalize_employee_number(cls, value: str) -> str:
        return value.upper()


class EmployeeCreate(EmployeeBase):
    """Datos necesarios para registrar un empleado."""

    pass


class EmployeeUpdate(BaseModel):
    """Campos opcionales para actualizar un empleado."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    usuario_id: int | None = Field(
        default=None,
        gt=0,
    )

    sucursal_id: int | None = Field(
        default=None,
        gt=0,
    )

    numero_empleado: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    puesto: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    @field_validator("numero_empleado")
    @classmethod
    def normalize_employee_number(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.upper()


class EmployeeResponse(EmployeeBase):
    """Representación pública de un empleado."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    id: int
    activo: bool
    created_at: datetime


class EmployeeListResponse(BaseModel):
    """Respuesta del listado de empleados."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    empleados: list[EmployeeResponse]