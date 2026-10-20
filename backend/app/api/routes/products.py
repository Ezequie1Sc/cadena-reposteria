
from fastapi import APIRouter, HTTPException, Path, Query
from postgrest.exceptions import APIError

from app.schemas.product import ProductListResponse, ProductResponse
from app.services.product_service import product_service


router = APIRouter(
    prefix="/productos",
    tags=["Productos"],
)


@router.get("", response_model=ProductListResponse)
def get_products(
    busqueda: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Buscar productos por nombre",
    ),
    categoria_id: int | None = Query(
        default=None,
        ge=1,
        description="Filtrar productos por categoría",
    ),
):
    try:
        products = product_service.get_products(
            busqueda=busqueda,
            categoria_id=categoria_id,
        )

        return {
            "total": len(products),
            "productos": products,
        }

    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar los productos en Supabase",
        ) from exc


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int = Path(
        gt=0,
        description="Identificador del producto",
    ),
):
    try:
        product = product_service.get_product_by_id(product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado",
            )

        return product

    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar el producto en Supabase",
        ) from exc
