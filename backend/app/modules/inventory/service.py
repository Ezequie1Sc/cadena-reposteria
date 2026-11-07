
"""Lógica de negocio para inventarios por sucursal."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.branches.model import Branch
from app.modules.inventory.model import Inventory
from app.modules.inventory.repository import inventory_repository
from app.modules.inventory.schemas import (
    InventoryAdjustmentCreate,
    InventoryCreate,
    InventoryListResponse,
    InventoryMovementCreate,
    InventoryMovementListResponse,
    InventoryMovementResponse,
    InventoryResponse,
    InventoryTransferCreate,
    InventoryTransferResponse,
    InventoryUpdate,
    MovementType,
)
from app.modules.products.model import Product


class InventoryService:
    """Administración transaccional de existencias."""

    @staticmethod
    def _response(inventory: Inventory) -> InventoryResponse:
        return InventoryResponse.model_validate(inventory)

    @staticmethod
    def _require_inventory(
        db: Session,
        inventory_id: int,
        *,
        lock: bool = False,
    ) -> Inventory:
        inventory = inventory_repository.get_by_id(
            db,
            inventory_id,
            for_update=lock,
        )

        if inventory is None:
            raise HTTPException(
                status_code=404,
                detail="Inventario no encontrado",
            )

        return inventory

    @staticmethod
    def _validate_product_and_branch(
        db: Session,
        producto_id: int,
        sucursal_id: int,
    ) -> None:
        product = db.get(Product, producto_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado",
            )

        if not product.activo:
            raise HTTPException(
                status_code=409,
                detail="El producto está inactivo",
            )

        branch = db.get(Branch, sucursal_id)

        if branch is None:
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada",
            )

        if not branch.activo:
            raise HTTPException(
                status_code=409,
                detail="La sucursal está inactiva",
            )

    @staticmethod
    def _save(db: Session, inventory: Inventory) -> InventoryResponse:
        db.commit()
        db.refresh(inventory)
        return InventoryResponse.model_validate(inventory)

    def get_all(
        self,
        db: Session,
        sucursal_id: int | None = None,
        producto_id: int | None = None,
        solo_bajo_stock: bool = False,
    ) -> InventoryListResponse:
        inventories = inventory_repository.get_all(
            db,
            sucursal_id=sucursal_id,
            producto_id=producto_id,
            solo_bajo_stock=solo_bajo_stock,
        )

        return InventoryListResponse(
            total=len(inventories),
            inventarios=[
                self._response(item) for item in inventories
            ],
        )

    def get_by_id(
        self,
        db: Session,
        inventory_id: int,
    ) -> InventoryResponse:
        inventory = self._require_inventory(db, inventory_id)
        return self._response(inventory)

    def create(
        self,
        db: Session,
        data: InventoryCreate,
    ) -> InventoryResponse:
        self._validate_product_and_branch(
            db,
            data.producto_id,
            data.sucursal_id,
        )

        existing = inventory_repository.get_by_product_and_branch(
            db,
            data.producto_id,
            data.sucursal_id,
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="El inventario ya existe para esta sucursal",
            )

        try:
            inventory = inventory_repository.create(
                db,
                producto_id=data.producto_id,
                sucursal_id=data.sucursal_id,
                stock_minimo=data.stock_minimo,
            )

            return self._save(db, inventory)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Conflicto al crear el inventario",
            ) from exc

    def update_minimum_stock(
        self,
        db: Session,
        inventory_id: int,
        data: InventoryUpdate,
    ) -> InventoryResponse:
        try:
            inventory = self._require_inventory(
                db,
                inventory_id,
                lock=True,
            )

            inventory_repository.update_minimum_stock(
                db,
                inventory,
                data.stock_minimo,
            )

            return self._save(db, inventory)

        except Exception:
            db.rollback()
            raise

    def _change_stock(
        self,
        db: Session,
        inventory_id: int,
        *,
        delta: int,
        movement_type: MovementType,
        motivo: str | None,
        usuario_id: int | None,
        referencia_tipo: str | None = None,
        referencia_id: int | None = None,
    ) -> InventoryResponse:
        if delta == 0:
            raise HTTPException(
                status_code=422,
                detail="El movimiento debe modificar las existencias",
            )

        try:
            inventory = self._require_inventory(
                db,
                inventory_id,
                lock=True,
            )

            self._validate_product_and_branch(
                db,
                inventory.producto_id,
                inventory.sucursal_id,
            )

            new_quantity = inventory.cantidad + delta

            if new_quantity < 0:
                raise HTTPException(
                    status_code=409,
                    detail="Existencias insuficientes",
                )

            inventory_repository.update_quantity(
                db,
                inventory,
                new_quantity,
            )

            inventory_repository.create_movement(
                db,
                inventario_id=inventory.id,
                tipo=movement_type.value,
                cantidad=abs(delta),
                motivo=motivo,
                referencia_tipo=referencia_tipo,
                referencia_id=referencia_id,
                usuario_id=usuario_id,
            )

            return self._save(db, inventory)

        except Exception:
            db.rollback()
            raise

    def register_entry(
        self,
        db: Session,
        inventory_id: int,
        data: InventoryMovementCreate,
        *,
        usuario_id: int | None = None,
    ) -> InventoryResponse:
        return self._change_stock(
            db,
            inventory_id,
            delta=data.cantidad,
            movement_type=MovementType.ENTRADA,
            motivo=data.motivo,
            usuario_id=usuario_id,
        )

    def register_exit(
        self,
        db: Session,
        inventory_id: int,
        data: InventoryMovementCreate,
        *,
        usuario_id: int | None = None,
    ) -> InventoryResponse:
        return self._change_stock(
            db,
            inventory_id,
            delta=-data.cantidad,
            movement_type=MovementType.SALIDA,
            motivo=data.motivo,
            usuario_id=usuario_id,
        )

    def register_sale(
        self,
        db: Session,
        inventory_id: int,
        cantidad: int,
        *,
        usuario_id: int | None = None,
        referencia_id: int | None = None,
    ) -> InventoryResponse:
        if cantidad <= 0:
            raise HTTPException(
                status_code=422,
                detail="La cantidad debe ser mayor que cero",
            )

        return self._change_stock(
            db,
            inventory_id,
            delta=-cantidad,
            movement_type=MovementType.VENTA,
            motivo="Venta de producto",
            usuario_id=usuario_id,
            referencia_tipo="VENTA" if referencia_id is not None else None,
            referencia_id=referencia_id,
        )

    def adjust_stock(
        self,
        db: Session,
        inventory_id: int,
        data: InventoryAdjustmentCreate,
        *,
        usuario_id: int | None = None,
    ) -> InventoryResponse:
        try:
            inventory = self._require_inventory(
                db,
                inventory_id,
                lock=True,
            )

            self._validate_product_and_branch(
                db,
                inventory.producto_id,
                inventory.sucursal_id,
            )

            difference = data.cantidad_final - inventory.cantidad

            if difference == 0:
                return self._response(inventory)

            inventory_repository.update_quantity(
                db,
                inventory,
                data.cantidad_final,
            )

            direction = (
                "INCREMENTO" if difference > 0 else "DISMINUCION"
            )

            inventory_repository.create_movement(
                db,
                inventario_id=inventory.id,
                tipo=MovementType.AJUSTE.value,
                cantidad=abs(difference),
                motivo=f"{direction}: {data.motivo}",
                usuario_id=usuario_id,
            )

            return self._save(db, inventory)

        except Exception:
            db.rollback()
            raise

    def transfer(
        self,
        db: Session,
        inventory_id: int,
        data: InventoryTransferCreate,
        *,
        usuario_id: int | None = None,
    ) -> InventoryTransferResponse:
        try:
            source_info = self._require_inventory(
                db,
                inventory_id,
            )

            if source_info.sucursal_id == data.sucursal_destino_id:
                raise HTTPException(
                    status_code=422,
                    detail="La sucursal destino debe ser diferente",
                )

            self._validate_product_and_branch(
                db,
                source_info.producto_id,
                source_info.sucursal_id,
            )

            self._validate_product_and_branch(
                db,
                source_info.producto_id,
                data.sucursal_destino_id,
            )

            destination_info = (
                inventory_repository.get_by_product_and_branch(
                    db,
                    source_info.producto_id,
                    data.sucursal_destino_id,
                )
            )

            if destination_info is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No existe inventario del producto "
                        "en la sucursal destino"
                    ),
                )

            # Bloquear siempre en orden de ID para evitar
            # interbloqueos entre traspasos opuestos.
            locked = {}

            for item_id in sorted(
                (inventory_id, destination_info.id)
            ):
                locked[item_id] = self._require_inventory(
                    db,
                    item_id,
                    lock=True,
                )

            source = locked[inventory_id]
            destination = locked[destination_info.id]

            if source.cantidad < data.cantidad:
                raise HTTPException(
                    status_code=409,
                    detail="Existencias insuficientes para el traspaso",
                )

            inventory_repository.update_quantity(
                db,
                source,
                source.cantidad - data.cantidad,
            )

            inventory_repository.update_quantity(
                db,
                destination,
                destination.cantidad + data.cantidad,
            )

            inventory_repository.create_movement(
                db,
                inventario_id=source.id,
                tipo=MovementType.TRASPASO.value,
                cantidad=data.cantidad,
                motivo=data.motivo or "Salida por traspaso",
                referencia_tipo="INVENTARIO_DESTINO",
                referencia_id=destination.id,
                usuario_id=usuario_id,
            )

            inventory_repository.create_movement(
                db,
                inventario_id=destination.id,
                tipo=MovementType.TRASPASO.value,
                cantidad=data.cantidad,
                motivo=data.motivo or "Entrada por traspaso",
                referencia_tipo="INVENTARIO_ORIGEN",
                referencia_id=source.id,
                usuario_id=usuario_id,
            )

            db.commit()
            db.refresh(source)
            db.refresh(destination)

            return InventoryTransferResponse(
                origen=self._response(source),
                destino=self._response(destination),
            )

        except Exception:
            db.rollback()
            raise

    def get_movements(
        self,
        db: Session,
        inventory_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> InventoryMovementListResponse:
        self._require_inventory(db, inventory_id)

        movements = inventory_repository.get_movements(
            db,
            inventario_id=inventory_id,
            limit=limit,
            offset=offset,
        )

        return InventoryMovementListResponse(
            total=len(movements),
            movimientos=[
                InventoryMovementResponse.model_validate(item)
                for item in movements
            ],
        )


inventory_service = InventoryService()
