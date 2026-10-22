
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category_service import CategoryService


@pytest.fixture
def service():
    return CategoryService()


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def category():
    return Category(
        id=1,
        nombre="Pasteles",
        descripcion="Pasteles artesanales",
        activo=True,
    )


def test_get_categories(service, db, category):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_all.return_value = [category]

        result = service.get_categories(db)

        assert len(result) == 1
        assert result[0].nombre == "Pasteles"
        repository.get_all.assert_called_once_with(
            db=db,
            busqueda=None,
            solo_activos=True,
        )


def test_get_category_by_id(service, db, category):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = category

        result = service.get_category_by_id(db, 1)

        assert result is not None
        assert result.id == 1


def test_get_nonexistent_category(service, db):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = None

        result = service.get_category_by_id(db, 999)

        assert result is None


def test_reject_duplicate_category_name(service, db, category):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_name.return_value = category

        with pytest.raises(HTTPException) as exc:
            service.validate_name(db, "Pasteles")

        assert exc.value.status_code == 409


def test_allow_available_category_name(service, db):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_name.return_value = None

        service.validate_name(db, "Galletas")

        repository.get_by_name.assert_called_once_with(
            db,
            "Galletas",
        )


def test_create_category(service, db, category):
    data = CategoryCreate(
        nombre="Pasteles",
        descripcion="Pasteles artesanales",
    )

    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_name.return_value = None
        repository.create.return_value = category

        result = service.create_category(db, data)

        assert result.nombre == "Pasteles"
        repository.create.assert_called_once_with(db, data)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(category)


def test_create_category_integrity_error(service, db):
    data = CategoryCreate(nombre="Pasteles")

    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_name.return_value = None
        repository.create.side_effect = IntegrityError(
            "INSERT",
            {},
            Exception("Duplicate category"),
        )

        with pytest.raises(HTTPException) as exc:
            service.create_category(db, data)

        assert exc.value.status_code == 409
        db.rollback.assert_called_once()
        db.commit.assert_not_called()


def test_update_nonexistent_category(service, db):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.update_category(
                db,
                999,
                CategoryUpdate(nombre="Galletas"),
            )

        assert exc.value.status_code == 404


def test_reject_null_category_name(service, db, category):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = category

        with pytest.raises(HTTPException) as exc:
            service.update_category(
                db,
                1,
                CategoryUpdate(nombre=None),
            )

        assert exc.value.status_code == 422
        db.commit.assert_not_called()


def test_update_category(service, db, category):
    data = CategoryUpdate(nombre="Pasteles Premium")

    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = category
        repository.get_by_name.return_value = None

        def update(db_session, category_obj, update_data):
            category_obj.nombre = update_data.nombre
            return category_obj

        repository.update.side_effect = update

        result = service.update_category(db, 1, data)

        assert result.nombre == "Pasteles Premium"
        repository.update.assert_called_once_with(
            db,
            category,
            data,
        )
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(category)


def test_deactivate_nonexistent_category(service, db):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.deactivate_category(db, 999)

        assert exc.value.status_code == 404


def test_reject_deactivation_with_active_products(
    service,
    db,
    category,
):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = category
        repository.has_active_products.return_value = True

        with pytest.raises(HTTPException) as exc:
            service.deactivate_category(db, 1)

        assert exc.value.status_code == 409
        repository.deactivate.assert_not_called()
        db.commit.assert_not_called()


def test_deactivate_category(service, db, category):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = category
        repository.has_active_products.return_value = False

        def deactivate(db_session, category_obj):
            category_obj.activo = False
            return category_obj

        repository.deactivate.side_effect = deactivate

        result = service.deactivate_category(db, 1)

        assert result.activo is False
        repository.has_active_products.assert_called_once_with(
            db,
            1,
        )
        repository.deactivate.assert_called_once_with(
            db,
            category,
        )
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(category)


def test_reactivate_nonexistent_category(service, db):
    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.reactivate_category(db, 999)

        assert exc.value.status_code == 404


def test_reactivate_category(service, db, category):
    category.activo = False

    with patch(
        "app.services.category_service.category_repository"
    ) as repository:
        repository.get_by_id.return_value = category

        def reactivate(db_session, category_obj):
            category_obj.activo = True
            return category_obj

        repository.reactivate.side_effect = reactivate

        result = service.reactivate_category(db, 1)

        assert result.activo is True
        repository.reactivate.assert_called_once_with(
            db,
            category,
        )
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(category)
