
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.categories.model import Category
from app.modules.products.repository import product_repository
from app.modules.products.schemas import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)


class ProductService:
    """Lógica de negocio para administrar productos."""

    def get_products(
        self,
        db: Session,
        busqueda: str | None = None,
        categoria_id: int | None = None,
        solo_activos: bool = True,
    ) -> list[ProductResponse]:
        products = product_repository.get_all(
            db=db,
            busqueda=busqueda,
            categoria_id=categoria_id,
            solo_activos=solo_activos,
        )

        return [
            ProductResponse.model_validate(product)
            for product in products
        ]

    def get_product_by_id(
        self,
        db: Session,
        product_id: int,
    ) -> ProductResponse | None:
        product = product_repository.get_by_id(
            db=db,
            product_id=product_id,
        )

        if product is None:
            return None

        return ProductResponse.model_validate(product)

    def validate_category(
        self,
        db: Session,
        category_id: int,
    ) -> None:
        category = db.get(Category, category_id)

        if category is None or not category.activo:
            raise HTTPException(
                status_code=422,
                detail="La categoría no existe o está inactiva",
            )

    def validate_sku(
        self,
        db: Session,
        sku: str,
        exclude_product_id: int | None = None,
    ) -> None:
        existing = product_repository.get_by_sku(db, sku)

        if existing is not None and existing.id != exclude_product_id:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un producto con este SKU",
            )

    def create_product(
        self,
        db: Session,
        data: ProductCreate,
    ) -> ProductResponse:
        self.validate_category(db, data.categoria_id)
        self.validate_sku(db, data.sku)

        try:
            product = product_repository.create(db, data)
            db.commit()
            db.refresh(product)

            return ProductResponse.model_validate(product)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo crear el producto por un conflicto de datos",
            ) from exc

    def update_product(
        self,
        db: Session,
        product_id: int,
        data: ProductUpdate,
    ) -> ProductResponse:
        product = product_repository.get_by_id(db, product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado",
            )

        changes = data.model_dump(exclude_unset=True)

        required_fields = {
            "categoria_id",
            "nombre",
            "sku",
            "precio",
        }

        if any(
            field in changes and changes[field] is None
            for field in required_fields
        ):
            raise HTTPException(
                status_code=422,
                detail="Los campos obligatorios no pueden ser nulos",
            )

        if "categoria_id" in changes:
            self.validate_category(db, changes["categoria_id"])

        if "sku" in changes:
            self.validate_sku(
                db,
                changes["sku"],
                exclude_product_id=product_id,
            )

        try:
            product = product_repository.update(db, product, data)
            db.commit()
            db.refresh(product)

            return ProductResponse.model_validate(product)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo actualizar el producto por un conflicto de datos",
            ) from exc

    def deactivate_product(
        self,
        db: Session,
        product_id: int,
    ) -> ProductResponse:
        product = product_repository.get_by_id(db, product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado",
            )

        if product.activo:
            product = product_repository.deactivate(db, product)
            db.commit()
            db.refresh(product)

        return ProductResponse.model_validate(product)

    def reactivate_product(
        self,
        db: Session,
        product_id: int,
    ) -> ProductResponse:
        product = product_repository.get_by_id(db, product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado",
            )

        self.validate_category(db, product.categoria_id)

        if not product.activo:
            product = product_repository.reactivate(db, product)
            db.commit()
            db.refresh(product)

        return ProductResponse.model_validate(product)


product_service = ProductService()
