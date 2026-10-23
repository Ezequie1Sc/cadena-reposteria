
import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)
from app.modules.customers.service import (
    CustomerConflictError,
    CustomerNotFoundError,
    CustomerService,
    CustomerValidationError,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"],
)

DbSession = Annotated[Session, Depends(get_db)]


def get_customer_service(db: DbSession) -> CustomerService:
    return CustomerService(db)


CustomerServiceDependency = Annotated[
    CustomerService,
    Depends(get_customer_service),
]


# ============================================================
# LISTAR CLIENTES
# ============================================================

@router.get(
    "",
    response_model=CustomerListResponse,
    summary="Listar clientes",
    responses={
        503: {"description": "Error de base de datos"},
    },
)
def get_customers(
    service: CustomerServiceDependency,
    page: int = Query(
        default=1,
        ge=1,
        description="Número de página",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Clientes por página",
    ),
    solo_activos: bool | None = Query(
        default=None,
        description=(
            "true: clientes activos; "
            "false: clientes inactivos; "
            "sin parámetro: todos los clientes"
        ),
    ),
):
    """Lista clientes con paginación y filtro opcional por estado."""

    try:
        return service.get_all(
            page=page,
            page_size=page_size,
            solo_activos=solo_activos,
        )

    except CustomerValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError:
        logger.exception("Error al listar clientes")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar los clientes",
        ) from None


# ============================================================
# CONSULTAR CLIENTE
# ============================================================

@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Consultar cliente",
    responses={
        404: {"description": "Cliente no encontrado"},
        503: {"description": "Error de base de datos"},
    },
)
def get_customer(
    service: CustomerServiceDependency,
    customer_id: int = Path(gt=0),
):
    """Consulta un cliente activo o inactivo por su ID."""

    try:
        return service.get_by_id(customer_id)

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError:
        logger.exception(
            "Error al consultar cliente %s",
            customer_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar el cliente",
        ) from None


# ============================================================
# CREAR CLIENTE
# ============================================================

@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cliente",
    responses={
        400: {"description": "Usuario asociado no válido"},
        409: {"description": "Conflicto de datos"},
        503: {"description": "Error de base de datos"},
    },
)
def create_customer(
    data: CustomerCreate,
    service: CustomerServiceDependency,
):
    """Registra un nuevo cliente con estado activo."""

    try:
        return service.create(data)

    except CustomerValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except CustomerConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError:
        logger.exception("Error al crear cliente")
        raise HTTPException(
            status_code=503,
            detail="No fue posible crear el cliente",
        ) from None


# ============================================================
# ACTUALIZAR CLIENTE
# ============================================================

@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Actualizar cliente",
    responses={
        400: {"description": "Datos de usuario no válidos"},
        404: {"description": "Cliente no encontrado"},
        409: {"description": "Conflicto de datos"},
        503: {"description": "Error de base de datos"},
    },
)
def update_customer(
    data: CustomerUpdate,
    service: CustomerServiceDependency,
    customer_id: int = Path(gt=0),
):
    """Actualiza parcialmente los datos de un cliente."""

    try:
        return service.update(
            customer_id,
            data,
        )

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except CustomerValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except CustomerConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError:
        logger.exception(
            "Error al actualizar cliente %s",
            customer_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar el cliente",
        ) from None


# ============================================================
# DESACTIVAR CLIENTE (SOFT DELETE)
# ============================================================

@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar cliente",
    responses={
        404: {"description": "Cliente no encontrado"},
        409: {"description": "Cliente ya desactivado"},
        503: {"description": "Error de base de datos"},
    },
)
def deactivate_customer(
    service: CustomerServiceDependency,
    customer_id: int = Path(gt=0),
):
    """
    Desactiva un cliente sin eliminarlo físicamente.

    El registro permanece en la base de datos y conserva
    sus relaciones con pedidos, ventas y facturas.
    """

    try:
        service.deactivate(customer_id)

        return None

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except CustomerConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError:
        logger.exception(
            "Error al desactivar cliente %s",
            customer_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible desactivar el cliente",
        ) from None


# ============================================================
# REACTIVAR CLIENTE
# ============================================================

@router.patch(
    "/{customer_id}/reactivar",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivar cliente",
    responses={
        404: {"description": "Cliente no encontrado"},
        409: {"description": "Cliente ya activo"},
        503: {"description": "Error de base de datos"},
    },
)
def reactivate_customer(
    service: CustomerServiceDependency,
    customer_id: int = Path(gt=0),
):
    """Reactiva un cliente previamente desactivado."""

    try:
        return service.reactivate(customer_id)

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except CustomerConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError:
        logger.exception(
            "Error al reactivar cliente %s",
            customer_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible reactivar el cliente",
        ) from None
