
"""Repositorio de pedidos y detalles de pedidos."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.branches.model import Branch
from app.modules.customers.model import Customer
from app.modules.inventory.model import Inventory
from app.modules.orders.model import Order, OrderDetail
from app.modules.products.model import Product


class OrderRepository:
    """Operaciones de persistencia para pedidos."""

    def get_all(
        self,
        db: Session,
        *,
        cliente_id: int | None = None,
        sucursal_id: int | None = None,
        estado: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Order]:
        """Lista pedidos con filtros y paginación."""

        statement = select(Order).options(
            selectinload(Order.detalles)
        )

        if cliente_id is not None:
            statement = statement.where(
                Order.cliente_id == cliente_id
            )

        if sucursal_id is not None:
            statement = statement.where(
                Order.sucursal_id == sucursal_id
            )

        if estado is not None:
            statement = statement.where(
                Order.estado == estado
            )

        statement = (
            statement
            .order_by(
                Order.fecha_pedido.desc(),
                Order.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(db.scalars(statement).all())

    def count(
        self,
        db: Session,
        *,
        cliente_id: int | None = None,
        sucursal_id: int | None = None,
        estado: str | None = None,
    ) -> int:
        """Cuenta pedidos aplicando los filtros."""

        statement = (
            select(func.count())
            .select_from(Order)
        )

        if cliente_id is not None:
            statement = statement.where(
                Order.cliente_id == cliente_id
            )

        if sucursal_id is not None:
            statement = statement.where(
                Order.sucursal_id == sucursal_id
            )

        if estado is not None:
            statement = statement.where(
                Order.estado == estado
            )

        return db.scalar(statement) or 0

    def get_by_id(
        self,
        db: Session,
        order_id: int,
        *,
        for_update: bool = False,
    ) -> Order | None:
        """Obtiene un pedido por ID."""

        statement = select(Order).where(
            Order.id == order_id
        )

        if for_update:
            statement = statement.with_for_update()
        else:
            statement = statement.options(
                selectinload(Order.detalles)
            )

        return db.scalar(statement)

    def get_by_number(
        self,
        db: Session,
        numero_pedido: str,
    ) -> Order | None:
        """Busca un pedido por su número único."""

        statement = (
            select(Order)
            .options(selectinload(Order.detalles))
            .where(
                Order.numero_pedido == numero_pedido
            )
        )

        return db.scalar(statement)

    def create(
        self,
        db: Session,
        *,
        numero_pedido: str,
        cliente_id: int,
        sucursal_id: int,
        subtotal: Decimal,
        descuento: Decimal = Decimal("0.00"),
        total: Decimal,
        direccion_entrega: str | None = None,
        notas: str | None = None,
    ) -> Order:
        """Registra el encabezado de un pedido."""

        order = Order(
            numero_pedido=numero_pedido,
            cliente_id=cliente_id,
            sucursal_id=sucursal_id,
            estado="PENDIENTE",
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            direccion_entrega=direccion_entrega,
            notas=notas,
        )

        db.add(order)
        db.flush()

        return order

    def create_details(
        self,
        db: Session,
        *,
        order_id: int,
        items: Sequence[dict],
    ) -> list[OrderDetail]:
        """Registra los productos asociados a un pedido."""

        details = [
            OrderDetail(
                pedido_id=order_id,
                producto_id=item["producto_id"],
                cantidad=item["cantidad"],
                precio_unitario=item["precio_unitario"],
                descuento=item.get(
                    "descuento",
                    Decimal("0.00"),
                ),
                subtotal=item["subtotal"],
            )
            for item in items
        ]

        db.add_all(details)
        db.flush()

        return details

    def update_status(
        self,
        db: Session,
        order: Order,
        estado: str,
    ) -> Order:
        """Actualiza el estado de un pedido."""

        order.estado = estado
        order.updated_at = datetime.now(timezone.utc)

        db.flush()

        return order

    def get_customer(
        self,
        db: Session,
        customer_id: int,
    ) -> Customer | None:
        """Obtiene un cliente por ID."""

        return db.get(Customer, customer_id)

    def get_branch(
        self,
        db: Session,
        branch_id: int,
    ) -> Branch | None:
        """Obtiene una sucursal por ID."""

        return db.get(Branch, branch_id)

    def get_product(
        self,
        db: Session,
        product_id: int,
    ) -> Product | None:
        """Obtiene un producto por ID."""

        return db.get(Product, product_id)

    def get_inventory(
        self,
        db: Session,
        *,
        producto_id: int,
        sucursal_id: int,
        for_update: bool = False,
    ) -> Inventory | None:
        """Obtiene el inventario de un producto en una sucursal."""

        statement = select(Inventory).where(
            Inventory.producto_id == producto_id,
            Inventory.sucursal_id == sucursal_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return db.scalar(statement)


order_repository = OrderRepository()
