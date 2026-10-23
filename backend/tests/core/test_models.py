
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db.session import SessionLocal
from app.db.models import Category, Product


def main():
    print("Verificando modelos SQLAlchemy...")

    with SessionLocal() as db:
        categories_count = db.scalar(
            select(func.count()).select_from(Category)
        )

        products_count = db.scalar(
            select(func.count()).select_from(Product)
        )

        print("\nConexion PostgreSQL exitosa")
        print(f"Categorias registradas: {categories_count}")
        print(f"Productos registrados: {products_count}")

        products = db.scalars(
            select(Product)
            .options(joinedload(Product.categoria))
            .order_by(Product.id)
        ).all()

        print("\nListado de productos:")
        print("-" * 60)

        for product in products:
            print(f"ID: {product.id}")
            print(f"Nombre: {product.nombre}")
            print(f"SKU: {product.sku}")
            print(f"Precio: ${product.precio:.2f}")
            print(f"Categoria: {product.categoria.nombre}")
            print(f"Activo: {product.activo}")
            print("-" * 60)

        print("\nModelos verificados correctamente.")


if __name__ == "__main__":
    main()
