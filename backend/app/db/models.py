"""Registro centralizado de modelos SQLAlchemy para Alembic."""

from app.modules.auth.rate_limit_model import AuthRateLimit
from app.modules.branches.model import Branch
from app.modules.categories.model import Category
from app.modules.customers.model import Customer
from app.modules.employees.model import Employee
from app.modules.products.model import Product
from app.modules.users.model import User
from app.modules.inventory.model import Inventory, InventoryMovement
from app.modules.orders.model import Order, OrderDetail
from app.shared.models.role_reference import roles_reference
from app.shared.models.user_reference import users_reference


__all__ = [
    "AuthRateLimit",
    "Branch",
    "Category",
    "Customer",
    "Employee",
    "Product",
    "User",
    "Inventory",
    "InventoryMovement",
    "Order",
    "OrderDetail",
    "roles_reference",
    "users_reference",
]

from app.modules.sales.model import Sale, SaleDetail

from app.modules.payments.model import Payment, PaymentMethod

from app.modules.tickets.model import Ticket

from app.modules.invoices.model import Invoice

from app.shared.commerce_models import CommercialEvent, IdempotencyRecord

__all__ += [
    "Sale",
    "SaleDetail",
    "Payment",
    "PaymentMethod",
    "Ticket",
    "Invoice",
    "CommercialEvent",
    "IdempotencyRecord",
]
