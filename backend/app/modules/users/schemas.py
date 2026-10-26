"""Esquemas Pydantic para el módulo de usuarios."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


def validate_email(value: str) -> str:
    """Normaliza y valida un correo electrónico."""

    email = value.strip().lower()

    if (
        not email
        or len(email) > 254
        or email.count("@") != 1
    ):
        raise ValueError("El correo electrónico no es válido.")

    local, domain = email.rsplit("@", 1)

    if (
        not local
        or not domain
        or "." not in domain
        or any(char.isspace() for char in email)
    ):
        raise ValueError("El correo electrónico no es válido.")

    return email


class UserBase(BaseModel):
    """Campos comunes de un usuario."""

    rol_id: int = Field(gt=0)

    nombre: str = Field(
        min_length=1,
        max_length=100,
    )

    apellido: str = Field(
        min_length=1,
        max_length=100,
    )

    email: str = Field(
        min_length=3,
        max_length=254,
    )

    telefono: str | None = Field(
        default=None,
        max_length=20,
    )

    @field_validator("nombre", "apellido")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Elimina espacios innecesarios."""

        value = value.strip()

        if not value:
            raise ValueError("Este campo no puede estar vacío.")

        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Valida y normaliza el correo."""

        return validate_email(value)

    @field_validator("telefono")
    @classmethod
    def normalize_phone(
        cls,
        value: str | None,
    ) -> str | None:
        """Normaliza el teléfono opcional."""

        if value is None:
            return None

        value = value.strip()

        return value or None


class UserCreate(UserBase):
    """Datos necesarios para crear un usuario."""

    password: str = Field(
        min_length=12,
        max_length=128,
    )


class UserUpdate(BaseModel):
    """Campos opcionales para actualizar un usuario."""

    rol_id: int | None = Field(
        default=None,
        gt=0,
    )

    nombre: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    apellido: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    email: str | None = Field(
        default=None,
        min_length=3,
        max_length=254,
    )

    telefono: str | None = Field(
        default=None,
        max_length=20,
    )

    password: str | None = Field(
        default=None,
        min_length=12,
        max_length=128,
    )

    @field_validator("nombre", "apellido")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Este campo no puede estar vacío.")

        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_email(value)

    @field_validator("telefono")
    @classmethod
    def normalize_phone(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class UserResponse(BaseModel):
    """Representación pública de un usuario."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rol_id: int
    nombre: str
    apellido: str
    email: str
    telefono: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime