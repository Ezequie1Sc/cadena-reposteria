
"""Esquemas para el registro público de clientes."""

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class CustomerRegistrationRequest(BaseModel):
    """Datos permitidos para crear una cuenta de cliente."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    nombre: str = Field(
        min_length=1,
        max_length=100,
        description="Nombre del cliente",
    )

    apellido: str = Field(
        min_length=1,
        max_length=100,
        description="Apellido del cliente",
    )

    email: EmailStr = Field(
        description="Correo electrónico del cliente",
    )

    password: str = Field(
        min_length=12,
        max_length=128,
        description="Contraseña de al menos 12 caracteres",
    )

    telefono: str | None = Field(
        default=None,
        min_length=10,
        max_length=20,
        description="Teléfono opcional",
    )

    @field_validator("nombre", "apellido")
    @classmethod
    def validate_names(cls, value: str) -> str:
        """Impide nombres vacíos o compuestos solo por espacios."""

        if not value.strip():
            raise ValueError(
                "Este campo no puede estar vacío"
            )

        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normaliza el correo electrónico."""

        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Exige una contraseña con una longitud mínima segura."""

        if not any(char.isalpha() for char in value):
            raise ValueError(
                "La contraseña debe contener al menos una letra"
            )

        if not any(char.isdigit() for char in value):
            raise ValueError(
                "La contraseña debe contener al menos un número"
            )

        return value


class CustomerRegistrationResponse(BaseModel):
    """Datos públicos devueltos después del registro."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    nombre: str
    apellido: str
    email: EmailStr
    telefono: str | None
    activo: bool
