
"""Registro centralizado de modelos SQLAlchemy para Alembic."""

from app.modules.auth.rate_limit_model import AuthRateLimit
from app.modules.branches.model import Branch
from app.modules.categories.model import Category
from app.modules.customers.model import Customer
from app.modules.employees.model import Employee
from app.modules.products.model import Product
from app.modules.users.model import User
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
    "roles_reference",
    "users_reference",
]
