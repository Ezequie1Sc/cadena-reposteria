"""Reservas comerciales reutilizando el repositorio y sus bloqueos ordenados."""

from fastapi import HTTPException
from sqlalchemy import select
from app.modules.products.model import Product
from app.modules.inventory.model import Inventory
from app.modules.inventory.repository import inventory_repository as repository
from app.shared.commerce import money


def price_lines(db, items):
    lines = []
    for item in items:
        product = db.scalar(
            select(Product)
            .where(Product.id == item.producto_id)
            .with_for_update(read=True)
        )
        if product is None:
            raise HTTPException(404, "Producto no encontrado")
        if not product.activo:
            raise HTTPException(409, "Producto inactivo")
        price = money(product.precio)
        lines.append(
            dict(
                producto_id=product.id,
                cantidad=item.cantidad,
                precio_unitario=price,
                descuento=money(0),
                subtotal=money(price * item.cantidad),
                producto_nombre=product.nombre,
                producto_sku=product.sku,
            )
        )
    return lines


def move_stock(db, branch_id, lines, *, restore, resource, resource_id, actor_id):
    quantities = {line.producto_id: line.cantidad for line in lines}
    inventories = list(
        db.scalars(
            select(Inventory)
            .where(
                Inventory.sucursal_id == branch_id,
                Inventory.producto_id.in_(quantities),
            )
            .order_by(Inventory.id)
        )
    )
    if len(inventories) != len(quantities):
        raise HTTPException(409, "Falta inventario de un producto")
    locked = [repository.get_by_id(db, i.id, for_update=True) for i in inventories]
    for inv in locked:
        qty = quantities[inv.producto_id]
        if not restore and inv.cantidad < qty:
            raise HTTPException(409, "Inventario insuficiente")
        if restore and inv.cantidad + qty > 2147483647:
            raise HTTPException(409, "Existencias fuera de rango")
        repository.update_quantity(db, inv, inv.cantidad + (qty if restore else -qty))
        repository.create_movement(
            db,
            inventario_id=inv.id,
            tipo="ENTRADA" if restore else "VENTA",
            cantidad=qty,
            motivo="Cancelación comercial" if restore else "Reserva por venta",
            referencia_tipo=resource,
            referencia_id=resource_id,
            usuario_id=actor_id,
        )
