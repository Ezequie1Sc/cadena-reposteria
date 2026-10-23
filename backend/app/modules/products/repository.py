
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.products.model import Product
from app.modules.products.schemas import ProductCreate, ProductUpdate


class ProductRepository:
    """Operaciones de acceso a datos para productos."""

    def get_all(
        self,
        db: Session,
        busqueda: str | None = None,
        categoria_id: int | None = None,
        solo_activos: bool = True,
    ) -> list[Product]:
        query = select(Product)

        if solo_activos:
            query = query.where(Product.activo.is_(True))

        if busqueda:
            termino = busqueda.strip()

            if termino:
                query = query.where(
                    Product.nombre.ilike(f"%{termino}%")
                )

        if categoria_id is not None:
            query = query.where(
                Product.categoria_id == categoria_id
            )

        query = query.order_by(Product.nombre)

        return list(db.scalars(query).all())

    def get_by_id(
        self,
        db: Session,
        product_id: int,
    ) -> Product | None:
        return db.get(Product, product_id)

    def get_by_sku(
        self,
        db: Session,
        sku: str,
    ) -> Product | None:
        query = select(Product).where(
            Product.sku == sku
        )

        return db.scalar(query)

    def create(
        self,
        db: Session,
        data: ProductCreate,
    ) -> Product:
        product = Product(**data.model_dump())

        db.add(product)
        db.flush()
        db.refresh(product)

        return product

    def update(
        self,
        db: Session,
        product: Product,
        data: ProductUpdate,
    ) -> Product:
        changes = data.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(product, field, value)

        if changes:
            product.updated_at = datetime.now(timezone.utc)
            db.flush()
            db.refresh(product)

        return product

    def deactivate(
        self,
        db: Session,
        product: Product,
    ) -> Product:
        product.activo = False
        product.updated_at = datetime.now(timezone.utc)

        db.flush()
        db.refresh(product)

        return product

    def reactivate(
        self,
        db: Session,
        product: Product,
    ) -> Product:
        product.activo = True
        product.updated_at = datetime.now(timezone.utc)

        db.flush()
        db.refresh(product)

        return product


product_repository = ProductRepository()
