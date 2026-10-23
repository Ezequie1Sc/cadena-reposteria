
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.categories.repository import category_repository
from app.modules.categories.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)


class CategoryService:
    """Lógica de negocio para administrar categorías."""

    def get_categories(
        self,
        db: Session,
        busqueda: str | None = None,
        solo_activos: bool = True,
    ) -> list[CategoryResponse]:
        categories = category_repository.get_all(
            db=db,
            busqueda=busqueda,
            solo_activos=solo_activos,
        )

        return [
            CategoryResponse.model_validate(category)
            for category in categories
        ]

    def get_category_by_id(
        self,
        db: Session,
        category_id: int,
    ) -> CategoryResponse | None:
        category = category_repository.get_by_id(
            db=db,
            category_id=category_id,
        )

        if category is None:
            return None

        return CategoryResponse.model_validate(category)

    def validate_name(
        self,
        db: Session,
        nombre: str,
        exclude_category_id: int | None = None,
    ) -> None:
        existing = category_repository.get_by_name(
            db,
            nombre,
        )

        if (
            existing is not None
            and existing.id != exclude_category_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Ya existe una categoría con este nombre",
            )

    def create_category(
        self,
        db: Session,
        data: CategoryCreate,
    ) -> CategoryResponse:
        self.validate_name(db, data.nombre)

        try:
            category = category_repository.create(db, data)

            db.commit()
            db.refresh(category)

            return CategoryResponse.model_validate(category)

        except IntegrityError as exc:
            db.rollback()

            raise HTTPException(
                status_code=409,
                detail="No se pudo crear la categoría por un conflicto de datos",
            ) from exc

    def update_category(
        self,
        db: Session,
        category_id: int,
        data: CategoryUpdate,
    ) -> CategoryResponse:
        category = category_repository.get_by_id(
            db,
            category_id,
        )

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="Categoría no encontrada",
            )

        changes = data.model_dump(exclude_unset=True)

        if "nombre" in changes:
            if changes["nombre"] is None:
                raise HTTPException(
                    status_code=422,
                    detail="El nombre de la categoría no puede ser nulo",
                )

            self.validate_name(
                db,
                changes["nombre"],
                exclude_category_id=category_id,
            )

        try:
            category = category_repository.update(
                db,
                category,
                data,
            )

            db.commit()
            db.refresh(category)

            return CategoryResponse.model_validate(category)

        except IntegrityError as exc:
            db.rollback()

            raise HTTPException(
                status_code=409,
                detail="No se pudo actualizar la categoría por un conflicto de datos",
            ) from exc

    def deactivate_category(
        self,
        db: Session,
        category_id: int,
    ) -> CategoryResponse:
        category = category_repository.get_by_id(
            db,
            category_id,
        )

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="Categoría no encontrada",
            )

        if category.activo:
            if category_repository.has_active_products(
                db,
                category_id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "No se puede desactivar la categoría "
                        "porque tiene productos activos asociados"
                    ),
                )

            try:
                category = category_repository.deactivate(
                    db,
                    category,
                )

                db.commit()
                db.refresh(category)

            except IntegrityError as exc:
                db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="No se pudo desactivar la categoría",
                ) from exc

        return CategoryResponse.model_validate(category)

    def reactivate_category(
        self,
        db: Session,
        category_id: int,
    ) -> CategoryResponse:
        category = category_repository.get_by_id(
            db,
            category_id,
        )

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="Categoría no encontrada",
            )

        if not category.activo:
            try:
                category = category_repository.reactivate(
                    db,
                    category,
                )

                db.commit()
                db.refresh(category)

            except IntegrityError as exc:
                db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="No se pudo reactivar la categoría",
                ) from exc

        return CategoryResponse.model_validate(category)


category_service = CategoryService()
