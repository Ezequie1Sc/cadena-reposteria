
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.categories.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryListResponse,
)


def test_create_category_valid():
    category = CategoryCreate(
        nombre="Pasteles",
        descripcion="Pasteles para toda ocasión",
    )

    assert category.nombre == "Pasteles"
    assert category.descripcion == "Pasteles para toda ocasión"


def test_create_category_without_description():
    category = CategoryCreate(nombre="Galletas")

    assert category.descripcion is None


@pytest.mark.parametrize("nombre", ["", "A", "X" * 101])
def test_create_category_invalid_name(nombre):
    with pytest.raises(ValidationError):
        CategoryCreate(nombre=nombre)


def test_create_category_requires_name():
    with pytest.raises(ValidationError):
        CategoryCreate()


def test_create_category_rejects_extra_fields():
    with pytest.raises(ValidationError):
        CategoryCreate(
            nombre="Bebidas",
            activo=False,
        )


def test_update_category_partial():
    category = CategoryUpdate(nombre="Postres")

    assert category.model_dump(exclude_unset=True) == {
        "nombre": "Postres"
    }


def test_update_category_empty():
    category = CategoryUpdate()

    assert category.model_dump(exclude_unset=True) == {}


def test_update_category_rejects_invalid_name():
    with pytest.raises(ValidationError):
        CategoryUpdate(nombre="A")


def test_update_category_rejects_extra_fields():
    with pytest.raises(ValidationError):
        CategoryUpdate(id=10)


def test_category_response_from_orm():
    orm_category = SimpleNamespace(
        id=1,
        nombre="Pasteles",
        descripcion="Pasteles artesanales",
        activo=True,
    )

    category = CategoryResponse.model_validate(orm_category)

    assert category.id == 1
    assert category.nombre == "Pasteles"
    assert category.activo is True


def test_category_list_response():
    category = CategoryResponse(
        id=1,
        nombre="Pasteles",
        descripcion=None,
        activo=True,
    )

    response = CategoryListResponse(
        total=1,
        categorias=[category],
    )

    assert response.total == 1
    assert len(response.categorias) == 1
    assert response.categorias[0].nombre == "Pasteles"
