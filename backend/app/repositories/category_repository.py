
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryRepository:
    """Operaciones de acceso a datos para categorías."""

    def get_all(
        self,
        db: Session,
        busqueda: str | None = None,
        solo_activos: bool = True,
    ) -> list[Category]:
        query = select(Category)

        if solo_activos:
            query = query.where(Category.activo.is_(True))

        if busqueda:
            termino = busqueda.strip()

            if termino:
                query = query.where(
                    Category.nombre.ilike(f"%{termino}%")
                )

        query = query.order_by(Category.nombre)

        return list(db.scalars(query).all())

    def get_by_id(
        self,
        db: Session,
        category_id: int,
    ) -> Category | None:
        return db.get(Category, category_id)

    def get_by_name(
        self,
        db: Session,
        nombre: str,
    ) -> Category | None:
        query = select(Category).where(
            func.lower(Category.nombre) == nombre.strip().lower()
        )

        return db.scalar(query)

    def create(
        self,
        db: Session,
        data: CategoryCreate,
    ) -> Category:
        category = Category(**data.model_dump())

        db.add(category)
        db.flush()
        db.refresh(category)

        return category

    def update(
        self,
        db: Session,
        category: Category,
        data: CategoryUpdate,
    ) -> Category:
        changes = data.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(category, field, value)

        if changes:
            db.flush()
            db.refresh(category)

        return category

    def deactivate(
        self,
        db: Session,
        category: Category,
    ) -> Category:
        category.activo = False

        db.flush()
        db.refresh(category)

        return category

    def reactivate(
        self,
        db: Session,
        category: Category,
    ) -> Category:
        category.activo = True

        db.flush()
        db.refresh(category)

        return category

    def has_active_products(
        self,
        db: Session,
        category_id: int,
    ) -> bool:
        """Comprueba si existen productos activos asociados."""

        query = select(
            select(Product.id)
            .where(
                Product.categoria_id == category_id,
                Product.activo.is_(True),
            )
            .exists()
        )

        return bool(db.scalar(query))


category_repository = CategoryRepository()
