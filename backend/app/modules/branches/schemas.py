
from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class BranchBase(BaseModel):
    """Campos compartidos para registrar sucursales."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    nombre: str = Field(
        min_length=1,
        max_length=100,
    )

    codigo: str = Field(
        min_length=1,
        max_length=30,
    )

    direccion: str = Field(
        min_length=1,
        max_length=255,
    )

    ciudad: str = Field(
        min_length=1,
        max_length=100,
    )

    estado: str = Field(
        min_length=1,
        max_length=100,
    )

    codigo_postal: str | None = Field(
        default=None,
        max_length=10,
    )

    telefono: str | None = Field(
        default=None,
        max_length=20,
    )

    latitud: Decimal | None = Field(
        default=None,
        ge=Decimal("-90"),
        le=Decimal("90"),
        allow_inf_nan=False,
    )

    longitud: Decimal | None = Field(
        default=None,
        ge=Decimal("-180"),
        le=Decimal("180"),
        allow_inf_nan=False,
    )

    @field_validator("codigo")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()


class BranchCreate(BranchBase):
    """Datos necesarios para crear una sucursal."""

    pass


class BranchUpdate(BaseModel):
    """Campos opcionales para actualizar una sucursal."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    nombre: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    codigo: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    direccion: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    ciudad: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    estado: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    codigo_postal: str | None = Field(
        default=None,
        max_length=10,
    )

    telefono: str | None = Field(
        default=None,
        max_length=20,
    )

    latitud: Decimal | None = Field(
        default=None,
        ge=Decimal("-90"),
        le=Decimal("90"),
        allow_inf_nan=False,
    )

    longitud: Decimal | None = Field(
        default=None,
        ge=Decimal("-180"),
        le=Decimal("180"),
        allow_inf_nan=False,
    )

    @field_validator("codigo")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.upper()


class BranchResponse(BranchBase):
    """Representación pública de una sucursal."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    id: int
    activo: bool

    created_at: datetime
    updated_at: datetime


class BranchListResponse(BaseModel):
    """Respuesta para el listado de sucursales."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    sucursales: list[BranchResponse]
