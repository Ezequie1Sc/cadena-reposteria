from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import DbSession
from app.core.permissions import AdminUser, StaffUser, require_inventory_access
from app.core.roles import RoleID
from app.modules.inventory.model import Inventory
from app.modules.inventory.repository import inventory_repository as stock
from app.modules.inventory.schemas import (
    InventoryAdjustmentCreate,
    InventoryMovementCreate,
    InventoryTransferCreate,
)
from app.modules.inventory.service import inventory_service
from app.shared.commerce import (
    Key,
    StrictModel,
    atomic,
    begin_idempotency,
    finish_idempotency,
)

from .common import execute, reserve_code, row
from .responses import MovementReceipt, RegisteredProduct

router = APIRouter(tags=["Catálogo administrativo"])


class InitialStock(StrictModel):
    sucursal_id: int = Field(gt=0)
    existencias_iniciales: int = Field(ge=0, le=2147483647)
    stock_minimo: int = Field(ge=0, le=2147483647)


class ProductRegistration(StrictModel):
    nombre: str = Field(min_length=2, max_length=150)
    descripcion: str | None = Field(None, max_length=4000)
    categoria_id: int = Field(gt=0)
    precio: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    inventarios: list[InitialStock] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def distinct_branches(self):
        if len({i.sucursal_id for i in self.inventarios}) != len(self.inventarios):
            raise ValueError("Sucursal repetida")
        return self


@router.post(
    "/administracion/productos", status_code=201, response_model=RegisteredProduct
)
def register_product(
    data: ProductRegistration, db: DbSession, actor: AdminUser, idempotency_key: Key
):
    return create_product(db, actor, data, idempotency_key)


@atomic
def create_product(db, actor, data, key):
    return product_transaction(db, actor, data, key)


def product_transaction(db, actor, data, key):
    prior, digest = begin_idempotency(
        db, actor, "alta_producto", key, data.model_dump(mode="json")
    )
    if prior is None:
        if not row(
            db,
            "SELECT id FROM public.categorias WHERE id=:id AND activo FOR SHARE",
            id=data.categoria_id,
        ):
            raise HTTPException(422, "Categoría no disponible")
        identifier, sku = reserve_code(db)
        execute(
            db,
            """INSERT INTO public.productos (id,sku,categoria_id,nombre,descripcion,precio)
                OVERRIDING SYSTEM VALUE VALUES (:id,:sku,:categoria_id,:nombre,:descripcion,:precio)""",
            id=identifier,
            sku=sku,
            **data.model_dump(exclude={"inventarios"}),
        )
        for item in sorted(data.inventarios, key=lambda entry: entry.sucursal_id):
            if not row(
                db,
                "SELECT id FROM public.sucursales WHERE id=:id AND activo FOR SHARE",
                id=item.sucursal_id,
            ):
                raise HTTPException(422, "Sucursal no disponible")
            inventory = stock.create(
                db,
                producto_id=identifier,
                sucursal_id=item.sucursal_id,
                stock_minimo=item.stock_minimo,
            )
            if item.existencias_iniciales:
                stock.update_quantity(db, inventory, item.existencias_iniciales)
                stock.create_movement(
                    db,
                    inventario_id=inventory.id,
                    tipo="ENTRADA",
                    cantidad=item.existencias_iniciales,
                    motivo="Alta inicial",
                    usuario_id=actor.id,
                    cantidad_anterior=0,
                    cantidad_nueva=item.existencias_iniciales,
                )
        finish_idempotency(db, actor, "alta_producto", key, digest, identifier)
    else:
        identifier = prior
    return {
        "producto": row(
            db, "SELECT * FROM public.productos WHERE id=:id", id=identifier
        ),
        "inventarios": [
            {
                "id": i.id,
                "sucursal_id": i.sucursal_id,
                "cantidad": i.cantidad,
                "stock_minimo": i.stock_minimo,
            }
            for i in db.scalars(
                select(Inventory)
                .where(Inventory.producto_id == identifier)
                .order_by(Inventory.id)
            )
        ],
    }


class Entry(InventoryMovementCreate):
    cantidad: int = Field(gt=0, le=2147483647)
    tipo: Literal["entrada", "salida"]


class Adjust(InventoryAdjustmentCreate):
    cantidad_final: int = Field(ge=0, le=2147483647)
    tipo: Literal["ajuste"]


class Transfer(InventoryTransferCreate):
    cantidad: int = Field(gt=0, le=2147483647)
    tipo: Literal["traspaso"]


@router.post(
    "/inventario-operativo/{identifier}/movimiento", response_model=MovementReceipt
)
def inventory_write(
    identifier: int,
    data: Annotated[Entry | Adjust | Transfer, Field(discriminator="tipo")],
    db: DbSession,
    actor: StaffUser,
    idempotency_key: Key,
):
    return change_inventory(db, actor, identifier, data, idempotency_key)


@atomic
def change_inventory(db, actor, identifier, data, key):
    if actor.rol_id != RoleID.ADMINISTRADOR and data.tipo in ("ajuste", "traspaso"):
        raise HTTPException(403, "Operación administrativa")
    require_inventory_access(db, actor, identifier)
    prior, digest = begin_idempotency(
        db, actor, "mov_inventario", key, {"id": identifier, **data.model_dump()}
    )
    if prior is None:
        methods = {
            "entrada": inventory_service.register_entry,
            "salida": inventory_service.register_exit,
            "ajuste": inventory_service.adjust_stock,
            "traspaso": inventory_service.transfer,
        }
        # Los servicios heredados confirman su sesión. El SAVEPOINT hace que stock
        # y recibo idempotente dependan del mismo commit exterior.
        with Session(
            bind=db.connection(), join_transaction_mode="create_savepoint"
        ) as nested:
            methods[data.tipo](nested, identifier, data, usuario_id=actor.id)
        finish_idempotency(db, actor, "mov_inventario", key, digest, identifier)
    return {"inventario_id": identifier, "tipo": data.tipo, "confirmado": True}
