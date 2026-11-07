
"""Repositorio de inventarios y movimientos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.model import (
    Inventory,
    InventoryMovement,
)


class InventoryRepository:
    """Operaciones de persistencia para inventarios."""

    def get_all(
        self,
        db: Session,
        sucursal_id: int | None = None,
        producto_id: int | None = None,
        solo_bajo_stock: bool = False,
    ) -> list[Inventory]:
        statement = select(Inventory)

        if sucursal_id is not None:
            statement = statement.where(
                Inventory.sucursal_id == sucursal_id
            )

        if producto_id is not None:
            statement = statement.where(
                Inventory.producto_id == producto_id
            )

        if solo_bajo_stock:
            statement = statement.where(
                Inventory.cantidad <= Inventory.stock_minimo
            )

        statement = statement.order_by(Inventory.id)

        return list(db.scalars(statement).all())

    def get_by_id(
        self,
        db: Session,
        inventory_id: int,
        *,
        for_update: bool = False,
    ) -> Inventory | None:
        statement = select(Inventory).where(
            Inventory.id == inventory_id
        )

        if for_update:
            statement = statement.with_for_update()

        return db.scalar(statement)

    def get_by_product_and_branch(
        self,
        db: Session,
        producto_id: int,
        sucursal_id: int,
        *,
        for_update: bool = False,
    ) -> Inventory | None:
        statement = select(Inventory).where(
            Inventory.producto_id == producto_id,
            Inventory.sucursal_id == sucursal_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return db.scalar(statement)

    def create(
        self,
        db: Session,
        *,
        producto_id: int,
        sucursal_id: int,
        stock_minimo: int = 0,
    ) -> Inventory:
        inventory = Inventory(
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            cantidad=0,
            stock_minimo=stock_minimo,
        )

        db.add(inventory)
        db.flush()

        return inventory

    def update_minimum_stock(
        self,
        db: Session,
        inventory: Inventory,
        stock_minimo: int,
    ) -> Inventory:
        inventory.stock_minimo = stock_minimo
        db.flush()

        return inventory

    def update_quantity(
        self,
        db: Session,
        inventory: Inventory,
        cantidad: int,
    ) -> Inventory:
        inventory.cantidad = cantidad
        db.flush()

        return inventory

    def create_movement(
        self,
        db: Session,
        *,
        inventario_id: int,
        tipo: str,
        cantidad: int,
        motivo: str | None = None,
        referencia_tipo: str | None = None,
        referencia_id: int | None = None,
        usuario_id: int | None = None,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            inventario_id=inventario_id,
            tipo=tipo,
            cantidad=cantidad,
            motivo=motivo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            usuario_id=usuario_id,
        )

        db.add(movement)
        db.flush()

        return movement

    def get_movements(
        self,
        db: Session,
        inventario_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryMovement]:
        statement = (
            select(InventoryMovement)
            .where(
                InventoryMovement.inventario_id == inventario_id
            )
            .order_by(
                InventoryMovement.created_at.desc(),
                InventoryMovement.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(db.scalars(statement).all())


inventory_repository = InventoryRepository()
