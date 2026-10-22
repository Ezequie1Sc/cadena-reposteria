
from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    """Campos compartidos de las categorías."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(
        min_length=2,
        max_length=100,
        description="Nombre único de la categoría",
    )

    descripcion: str | None = Field(
        default=None,
        description="Descripción opcional de la categoría",
    )


class CategoryCreate(CategoryBase):
    """Datos necesarios para registrar una categoría."""

    pass


class CategoryUpdate(BaseModel):
    """Campos opcionales para actualizar una categoría."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    descripcion: str | None = None


class CategoryResponse(CategoryBase):
    """Representación pública de una categoría."""

    id: int
    activo: bool

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


class CategoryListResponse(BaseModel):
    """Respuesta del listado de categorías."""

    total: int
    categorias: list[CategoryResponse]
  