
"""Lógica de negocio para la gestión de pedidos."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.inventory.repository import inventory_repository
from app.modules.orders.model import Order
from app.modules.orders.repository import order_repository
from app.modules.orders.schemas import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatus,
    OrderStatusUpdate,
)


MONEY = Decimal("0.01")

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDIENTE: {
        OrderStatus.CONFIRMADO,
        OrderStatus.CANCELADO,
    },
    OrderStatus.CONFIRMADO: {
        OrderStatus.PREPARANDO,
        OrderStatus.CANCELADO,
    },
    OrderStatus.PREPARANDO: {
        OrderStatus.LISTO,
        OrderStatus.CANCELADO,
    },
    OrderStatus.LISTO: {
        OrderStatus.ENTREGADO,
        OrderStatus.CANCELADO,
    },
    OrderStatus.ENTREGADO: set(),
    OrderStatus.CANCELADO: set(),
}


class OrderService:
    """Administración transaccional de pedidos."""

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        """Normaliza un importe a dos decimales."""
        return value.quantize(
            MONEY,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _response(order: Order) -> OrderResponse:
        return OrderResponse.model_validate(order)

    @staticmethod
    def _require_order(
        db: Session,
        order_id: int,
        *,
        lock: bool = False,
    ) -> Order:
        order = order_repository.get_by_id(
            db,
            order_id,
            for_update=lock,
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Pedido no encontrado",
            )

        return order

    @staticmethod
    def _generate_order_number() -> str:
        """Genera un identificador de pedido de 32 caracteres."""
        return f"PED-{uuid4().hex[:28].upper()}"

    @staticmethod
    def _validate_customer_and_branch(
        db: Session,
        cliente_id: int,
        sucursal_id: int,
    ) -> None:
        customer = order_repository.get_customer(
            db,
            cliente_id,
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado",
            )

        if not customer.activo:
            raise HTTPException(
                status_code=409,
                detail="El cliente está inactivo",
            )

        branch = order_repository.get_branch(
            db,
            sucursal_id,
        )

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

    def get_all(
        self,
        db: Session,
        *,
        cliente_id: int | None = None,
        sucursal_id: int | None = None,
        estado: OrderStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> OrderListResponse:
        """Lista pedidos con filtros y paginación."""

        if limit < 1 or limit > 100 or offset < 0:
            raise HTTPException(
                status_code=422,
                detail="Parámetros de paginación inválidos",
            )

        status_value = estado.value if estado else None

        orders = order_repository.get_all(
            db,
            cliente_id=cliente_id,
            sucursal_id=sucursal_id,
            estado=status_value,
            limit=limit,
            offset=offset,
        )

        total = order_repository.count(
            db,
            cliente_id=cliente_id,
            sucursal_id=sucursal_id,
            estado=status_value,
        )

        return OrderListResponse(
            total=total,
            pedidos=[
                self._response(order)
                for order in orders
            ],
        )

    def get_by_id(
        self,
        db: Session,
        order_id: int,
    ) -> OrderResponse:
        """Obtiene un pedido con sus detalles."""

        order = self._require_order(db, order_id)
        return self._response(order)

    def get_by_number(
        self,
        db: Session,
        numero_pedido: str,
    ) -> OrderResponse:
        """Obtiene un pedido por su número."""

        order = order_repository.get_by_number(
            db,
            numero_pedido,
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Pedido no encontrado",
            )

        return self._response(order)

    def create(
        self,
        db: Session,
        data: OrderCreate,
        *,
        usuario_id: int | None = None,
    ) -> OrderResponse:
        """Crea un pedido y descuenta existencias atómicamente."""

        try:
            self._validate_customer_and_branch(
                db,
                data.cliente_id,
                data.sucursal_id,
            )

            # Validar productos y precios antes de modificar stock.
            products = {}

            for item in data.productos:
                product = order_repository.get_product(
                    db,
                    item.producto_id,
                )

                if product is None:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Producto {item.producto_id} "
                            "no encontrado"
                        ),
                    )

                if not product.activo:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"El producto {item.producto_id} "
                            "está inactivo"
                        ),
                    )

                price = Decimal(str(product.precio))

                if not price.is_finite() or price < 0:
                    raise HTTPException(
                        status_code=409,
                        detail="El producto tiene un precio inválido",
                    )

                products[item.producto_id] = product

            # Localizar inventarios antes de adquirir bloqueos.
            inventory_ids = {}

            for item in data.productos:
                inventory = order_repository.get_inventory(
                    db,
                    producto_id=item.producto_id,
                    sucursal_id=data.sucursal_id,
                )

                if inventory is None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "No existe inventario para el producto "
                            f"{item.producto_id} en esta sucursal"
                        ),
                    )

                inventory_ids[item.producto_id] = inventory.id

            # Bloquear siempre por ID ascendente.
            locked_inventories = {}

            for inventory_id in sorted(
                set(inventory_ids.values())
            ):
                inventory = inventory_repository.get_by_id(
                    db,
                    inventory_id,
                    for_update=True,
                )

                if inventory is None:
                    raise HTTPException(
                        status_code=409,
                        detail="El inventario ya no está disponible",
                    )

                locked_inventories[inventory.id] = inventory

            details = []
            subtotal = Decimal("0.00")

            for item in data.productos:
                inventory = locked_inventories[
                    inventory_ids[item.producto_id]
                ]

                if inventory.cantidad < item.cantidad:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Existencias insuficientes para "
                            f"el producto {item.producto_id}"
                        ),
                    )

                product = products[item.producto_id]

                unit_price = self._money(
                    Decimal(str(product.precio))
                )

                line_total = self._money(
                    unit_price * item.cantidad
                )

                subtotal += line_total

                details.append(
                    {
                        "producto_id": item.producto_id,
                        "cantidad": item.cantidad,
                        "precio_unitario": unit_price,
                        "descuento": Decimal("0.00"),
                        "subtotal": line_total,
                    }
                )

            subtotal = self._money(subtotal)
            discount = Decimal("0.00")
            total = self._money(subtotal - discount)

            order = order_repository.create(
                db,
                numero_pedido=self._generate_order_number(),
                cliente_id=data.cliente_id,
                sucursal_id=data.sucursal_id,
                subtotal=subtotal,
                descuento=discount,
                total=total,
                direccion_entrega=data.direccion_entrega,
                notas=data.notas,
            )

            order_repository.create_details(
                db,
                order_id=order.id,
                items=details,
            )

            for item in sorted(
                data.productos,
                key=lambda value: inventory_ids[value.producto_id],
            ):
                inventory = locked_inventories[
                    inventory_ids[item.producto_id]
                ]

                inventory_repository.update_quantity(
                    db,
                    inventory,
                    inventory.cantidad - item.cantidad,
                )

                inventory_repository.create_movement(
                    db,
                    inventario_id=inventory.id,
                    tipo="SALIDA",
                    cantidad=item.cantidad,
                    motivo="Reserva de existencias por pedido",
                    referencia_tipo="PEDIDO",
                    referencia_id=order.id,
                    usuario_id=usuario_id,
                )

            db.commit()

            # Recuperar el pedido con los detalles cargados.
            saved_order = self._require_order(db, order.id)

            return self._response(saved_order)

        except Exception:
            db.rollback()
            raise

    def update_status(
        self,
        db: Session,
        order_id: int,
        data: OrderStatusUpdate,
        *,
        usuario_id: int | None = None,
    ) -> OrderResponse:
        """Actualiza el estado y repone stock al cancelar."""

        try:
            order = self._require_order(
                db,
                order_id,
                lock=True,
            )

            current_status = OrderStatus(order.estado)
            new_status = data.estado

            if new_status == current_status:
                raise HTTPException(
                    status_code=409,
                    detail="El pedido ya tiene ese estado",
                )

            allowed = ALLOWED_TRANSITIONS[current_status]

            if new_status not in allowed:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Transición de estado no permitida: "
                        f"{current_status.value} -> "
                        f"{new_status.value}"
                    ),
                )

            if new_status == OrderStatus.CANCELADO:
                # Los detalles se consultan explícitamente
                # porque el pedido fue bloqueado con FOR UPDATE.
                db.refresh(order, attribute_names=["detalles"])

                inventory_ids = {}

                for detail in order.detalles:
                    inventory = order_repository.get_inventory(
                        db,
                        producto_id=detail.producto_id,
                        sucursal_id=order.sucursal_id,
                    )

                    if inventory is None:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                "No se puede cancelar: falta "
                                "el inventario de un producto"
                            ),
                        )

                    inventory_ids[detail.producto_id] = inventory.id

                locked_inventories = {}

                for inventory_id in sorted(
                    set(inventory_ids.values())
                ):
                    inventory = inventory_repository.get_by_id(
                        db,
                        inventory_id,
                        for_update=True,
                    )

                    if inventory is None:
                        raise HTTPException(
                            status_code=409,
                            detail="Inventario no disponible",
                        )

                    locked_inventories[inventory.id] = inventory

                for detail in sorted(
                    order.detalles,
                    key=lambda value: inventory_ids[value.producto_id],
                ):
                    inventory = locked_inventories[
                        inventory_ids[detail.producto_id]
                    ]

                    inventory_repository.update_quantity(
                        db,
                        inventory,
                        inventory.cantidad + detail.cantidad,
                    )

                    inventory_repository.create_movement(
                        db,
                        inventario_id=inventory.id,
                        tipo="ENTRADA",
                        cantidad=detail.cantidad,
                        motivo="Reposición por cancelación de pedido",
                        referencia_tipo="PEDIDO",
                        referencia_id=order.id,
                        usuario_id=usuario_id,
                    )

            order_repository.update_status(
                db,
                order,
                new_status.value,
            )

            db.commit()

            saved_order = self._require_order(db, order_id)
            return self._response(saved_order)

        except Exception:
            db.rollback()
            raise


order_service = OrderService()
