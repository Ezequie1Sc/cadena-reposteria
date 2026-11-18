from app.shared.commerce import Dates
from typing import Annotated, Literal
from fastapi import APIRouter, Query
from app.core.auth import DbSession
from app.core.permissions import AdminUser
from app.shared.commerce import Limit, Offset
from app.modules.reports import repository, service
from app.modules.reports.schemas import (
    SalesAggregate,
    ProductAggregate,
    PaymentAggregate,
    Dashboard,
)
from app.modules.inventory.schemas import InventoryResponse, InventoryMovementResponse

router = APIRouter(prefix="/reportes", tags=["Reportes administrativos"])
BranchID = Annotated[int | None, Query(gt=0)]


@router.get("/ventas", response_model=list[SalesAggregate])
def sales(
    db: DbSession,
    actor: AdminUser,
    dates: Dates,
    agrupacion: Literal["dia", "semana", "mes", "anio", "sucursal", "empleado"] = "dia",
    orden: Literal["grupo", "total_asc", "total_desc"] = "grupo",
    sucursal_id: BranchID = None,
    zona_horaria: str = "America/Merida",
    limit: Limit = 100,
    offset: Offset = 0,
):
    service.zone(db, zona_horaria)
    return repository.sales_totals(
        db, dates, sucursal_id, agrupacion, zona_horaria, limit, offset, orden
    )


@router.get("/productos", response_model=list[ProductAggregate])
def products(
    db: DbSession,
    actor: AdminUser,
    dates: Dates,
    sucursal_id: BranchID = None,
    menos_vendidos: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
):
    return repository.top_products(
        db, dates, sucursal_id, limit, offset, menos_vendidos
    )


@router.get("/pagos", response_model=list[PaymentAggregate])
def payments(
    db: DbSession,
    actor: AdminUser,
    dates: Dates,
    sucursal_id: BranchID = None,
    solo_confirmados: bool = False,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return repository.payment_totals(
        db, dates, sucursal_id, solo_confirmados, limit, offset
    )


@router.get("/inventarios", response_model=list[InventoryResponse])
def stock(
    db: DbSession,
    actor: AdminUser,
    sucursal_id: BranchID = None,
    solo_bajo_stock: bool = False,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return repository.stock(db, sucursal_id, solo_bajo_stock, limit, offset)


@router.get("/movimientos", response_model=list[InventoryMovementResponse])
def movements(
    db: DbSession,
    actor: AdminUser,
    dates: Dates,
    sucursal_id: BranchID = None,
    tipo: Literal["ENTRADA", "SALIDA", "VENTA", "AJUSTE", "TRASPASO"] | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return repository.movements(db, dates, sucursal_id, tipo, limit, offset)


@router.get("/dashboard", response_model=Dashboard)
def dashboard(
    db: DbSession,
    actor: AdminUser,
    sucursal_id: BranchID = None,
    zona_horaria: str = "America/Merida",
):
    return service.dashboard(db, sucursal_id, zona_horaria)
