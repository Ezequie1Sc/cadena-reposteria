"""Autorización basada en roles para endpoints protegidos."""

from app.core.roles import RoleID
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, DbSession
from app.modules.users.model import User


def require_roles(*allowed_roles: RoleID):
    """
    Crea una dependencia que permite únicamente
    los roles indicados.

    La autenticación y el estado activo del usuario
    y su rol se verifican mediante CurrentUser.
    """

    if not allowed_roles:
        raise ValueError("Debe especificarse al menos un rol permitido")

    allowed_role_ids = frozenset(int(role) for role in allowed_roles)

    def check_permissions(
        current_user: CurrentUser,
    ) -> User:
        """Comprueba que el usuario tenga un rol autorizado."""

        if current_user.rol_id not in allowed_role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("No tienes permisos para realizar esta operación"),
            )

        return current_user

    return check_permissions


# ============================================================
# DEPENDENCIAS REUTILIZABLES
# ============================================================


AdminUser = Annotated[
    User,
    Depends(require_roles(RoleID.ADMINISTRADOR)),
]

StaffUser = Annotated[
    User,
    Depends(
        require_roles(
            RoleID.ADMINISTRADOR,
            RoleID.EMPLEADO,
        )
    ),
]


def employee_branch_id(db: Session, actor: User) -> int | None:
    """Admin is global; employees require an active assignment and branch.

    Shared locks retain the assignment through a write transaction, preventing
    reassignment/deactivation between authorization and commit in PostgreSQL.
    """
    if actor.rol_id == RoleID.ADMINISTRADOR:
        return None
    if actor.rol_id != RoleID.EMPLEADO:
        raise HTTPException(status_code=403, detail="Operación no autorizada")
    from app.modules.employees.model import Employee
    from app.modules.branches.model import Branch

    branch_id = db.scalar(
        select(Employee.sucursal_id)
        .join(Branch, Branch.id == Employee.sucursal_id)
        .where(
            Employee.usuario_id == actor.id,
            Employee.activo.is_(True),
            Branch.activo.is_(True),
        )
        .with_for_update(read=True)
    )
    if branch_id is None:
        raise HTTPException(
            status_code=403, detail="Se requiere una asignación activa de sucursal"
        )
    return branch_id


def scope_branch(db: Session, actor: User, requested: int | None) -> int | None:
    branch_id = employee_branch_id(db, actor)
    if branch_id is not None and requested is not None and requested != branch_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta sucursal")
    return branch_id if branch_id is not None else requested


def require_inventory_access(db: Session, actor: User, inventory_id: int) -> None:
    branch_id = employee_branch_id(db, actor)
    if branch_id is None:
        return
    from app.modules.inventory.model import Inventory

    resource_branch = db.scalar(
        select(Inventory.sucursal_id).where(Inventory.id == inventory_id)
    )
    if resource_branch is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    if resource_branch != branch_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta sucursal")


def require_order_access(
    db: Session, actor: User, *, order_id: int | None = None, number: str | None = None
) -> None:
    branch_id = employee_branch_id(db, actor)
    if branch_id is None:
        return
    from app.modules.orders.model import Order

    condition = (
        Order.id == order_id if order_id is not None else Order.numero_pedido == number
    )
    resource_branch = db.scalar(select(Order.sucursal_id).where(condition))
    if resource_branch is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if resource_branch != branch_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta sucursal")


def require_customer_access(
    db: Session, actor: User, customer_id: int, *, changes: set[str] | None = None
) -> None:
    if actor.rol_id == RoleID.ADMINISTRADOR:
        return
    if actor.rol_id != RoleID.CLIENTE:
        raise HTTPException(status_code=403, detail="Operación no autorizada")
    if changes is not None and not changes <= {
        "nombre",
        "apellido",
        "email",
        "telefono",
        "fecha_nacimiento",
    }:
        raise HTTPException(
            status_code=403, detail="No puedes modificar la vinculación de la cuenta"
        )
    from app.modules.customers.model import Customer

    owned = db.scalar(
        select(Customer.id)
        .where(
            Customer.id == customer_id,
            Customer.usuario_id == actor.id,
            Customer.activo.is_(True),
        )
        .with_for_update(read=changes is None)
    )
    if owned is None:
        raise HTTPException(status_code=403, detail="No tienes acceso a este cliente")
