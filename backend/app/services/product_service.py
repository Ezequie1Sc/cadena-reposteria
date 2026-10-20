
from app.repositories.product_repository import product_repository
from app.schemas.product import ProductResponse


class ProductService:
    """Contiene la lógica de negocio para consultar productos."""

    def get_products(
        self,
        busqueda: str | None = None,
        categoria_id: int | None = None,
    ) -> list[ProductResponse]:
        if busqueda is not None:
            busqueda = busqueda.strip() or None

        products = product_repository.get_all(
            busqueda=busqueda,
            categoria_id=categoria_id,
            solo_activos=True,
        )

        return [
            ProductResponse.model_validate(product)
            for product in products
        ]

    def get_product_by_id(
        self,
        product_id: int,
    ) -> ProductResponse | None:
        product = product_repository.get_by_id(product_id)

        if product is None:
            return None

        return ProductResponse.model_validate(product)


product_service = ProductService()
