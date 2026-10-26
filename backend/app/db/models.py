"""Registro centralizado de modelos SQLAlchemy para Alembic."""

from app.modules.branches.model import Branch
from app.modules.categories.model import Category
from app.modules.customers.model import Customer
from app.modules.employees.model import Employee
from app.modules.products.model import Product
from app.shared.models.user_reference import users_reference

__all__ = [
    "Branch",
    "Category",
    "Customer",
    "Employee",
    "Product",
    "users_reference",
]