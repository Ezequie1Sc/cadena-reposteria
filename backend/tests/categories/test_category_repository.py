
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.modules.categories.model import Category
from app.modules.products.model import Product
from app.modules.categories.repository import CategoryRepository
from app.modules.categories.schemas import CategoryCreate, CategoryUpdate


@pytest.fixture
def db():
    """Crea una base de datos temporal para cada prueba."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine,
        tables=[
            Category.__table__,
            Product.__table__,
        ],
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def repository():
    return CategoryRepository()


def create_category(db, nombre="Pasteles", activo=True):
    category = Category(
        nombre=nombre,
        descripcion="Categoría de prueba",
        activo=activo,
    )

    db.add(category)
    db.flush()

    return category


def test_create_category(db, repository):
    data = CategoryCreate(
        nombre="Galletas",
        descripcion="Galletas artesanales",
    )

    category = repository.create(db, data)

    assert category.id is not None
    assert category.nombre == "Galletas"
    assert category.activo is True


def test_get_category_by_id(db, repository):
    category = create_category(db)

    result = repository.get_by_id(db, category.id)

    assert result is not None
    assert result.nombre == "Pasteles"


def test_get_category_by_name_case_insensitive(db, repository):
    create_category(db, nombre="Postres")

    result = repository.get_by_name(db, "postres")

    assert result is not None
    assert result.nombre == "Postres"


def test_get_all_only_active(db, repository):
    create_category(db, nombre="Pasteles")
    create_category(db, nombre="Bebidas", activo=False)

    results = repository.get_all(db)

    assert len(results) == 1
    assert results[0].nombre == "Pasteles"


def test_get_all_including_inactive(db, repository):
    create_category(db, nombre="Pasteles")
    create_category(db, nombre="Bebidas", activo=False)

    results = repository.get_all(
        db,
        solo_activos=False,
    )

    assert len(results) == 2


def test_get_all_with_search(db, repository):
    create_category(db, nombre="Pasteles")
    create_category(db, nombre="Galletas")

    results = repository.get_all(
        db,
        busqueda="paste",
    )

    assert len(results) == 1
    assert results[0].nombre == "Pasteles"


def test_update_category(db, repository):
    category = create_category(db)

    data = CategoryUpdate(
        nombre="Pasteles Premium",
    )

    updated = repository.update(db, category, data)

    assert updated.nombre == "Pasteles Premium"


def test_deactivate_category(db, repository):
    category = create_category(db)

    updated = repository.deactivate(db, category)

    assert updated.activo is False


def test_reactivate_category(db, repository):
    category = create_category(
        db,
        activo=False,
    )

    updated = repository.reactivate(db, category)

    assert updated.activo is True


def test_category_without_active_products(db, repository):
    category = create_category(db)

    assert repository.has_active_products(
        db,
        category.id,
    ) is False


def test_category_with_active_products(db, repository):
    category = create_category(db)

    product = Product(
        categoria_id=category.id,
        nombre="Pastel de chocolate",
        sku="PASTEL-001",
        precio=250,
        activo=True,
    )

    db.add(product)
    db.flush()

    assert repository.has_active_products(
        db,
        category.id,
    ) is True


def test_category_with_inactive_products(db, repository):
    category = create_category(db)

    product = Product(
        categoria_id=category.id,
        nombre="Pastel de vainilla",
        sku="PASTEL-002",
        precio=200,
        activo=False,
    )

    db.add(product)
    db.flush()

    assert repository.has_active_products(
        db,
        category.id,
    ) is False
