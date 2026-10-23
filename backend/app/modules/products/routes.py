
import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.modules.products.service import product_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/productos",
    tags=["Productos"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=ProductListResponse,
    summary="Listar productos",
)
def get_products(
    db: DbSession,
    busqueda: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    categoria_id: int | None = Query(
        default=None,
        ge=1,
    ),
    solo_activos: bool = Query(
        default=True,
        description="Mostrar únicamente productos activos",
    ),
):
    try:
        products = product_service.get_products(
            db=db,
            busqueda=busqueda,
            categoria_id=categoria_id,
            solo_activos=solo_activos,
        )

        return ProductListResponse(
            total=len(products),
            productos=products,
        )

    except SQLAlchemyError:
        logger.exception("Error al listar productos")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar los productos",
        ) from None


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    responses={404: {"description": "Producto no encontrado"}},
    summary="Consultar producto",
)
def get_product(
    db: DbSession,
    product_id: int = Path(gt=0),
):
    try:
        product = product_service.get_product_by_id(
            db=db,
            product_id=product_id,
        )

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado",
            )

        return product

    except SQLAlchemyError:
        logger.exception("Error al consultar producto %s", product_id)
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar el producto",
        ) from None


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto",
)
def create_product(
    data: ProductCreate,
    db: DbSession,
):
    try:
        return product_service.create_product(db, data)

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al crear producto")
        raise HTTPException(
            status_code=503,
            detail="No fue posible crear el producto",
        ) from None


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Actualizar producto",
)
def update_product(
    data: ProductUpdate,
    db: DbSession,
    product_id: int = Path(gt=0),
):
    try:
        return product_service.update_product(
            db=db,
            product_id=product_id,
            data=data,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al actualizar producto %s", product_id)
        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar el producto",
        ) from None


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar producto",
    description="Desactiva un producto sin eliminarlo físicamente.",
)
def deactivate_product(
    db: DbSession,
    product_id: int = Path(gt=0),
):
    try:
        product_service.deactivate_product(db, product_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al desactivar producto %s", product_id)
        raise HTTPException(
            status_code=503,
            detail="No fue posible desactivar el producto",
        ) from None


@router.patch(
    "/{product_id}/reactivar",
    response_model=ProductResponse,
    summary="Reactivar producto",
)
def reactivate_product(
    db: DbSession,
    product_id: int = Path(gt=0),
):
    try:
        return product_service.reactivate_product(
            db=db,
            product_id=product_id,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al reactivar producto %s", product_id)
        raise HTTPException(
            status_code=503,
            detail="No fue posible reactivar el producto",
        ) from None
