"""Punto de entrada principal de la API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.errors import register_error_handlers

from app.core.config import settings

# ============================================================
# RUTAS GENERALES
# ============================================================

from app.api.routes.health import router as health_router
from app.api.routes.roles import router as roles_router
from app.api.routes.auth import router as auth_router

# ============================================================
# MÓDULOS DEL SISTEMA
# ============================================================

from app.modules.products.routes import router as products_router
from app.modules.categories.routes import router as categories_router
from app.modules.branches.routes import router as branches_router
from app.modules.customers.routes import router as customers_router
from app.modules.employees.routes import router as employees_router
from app.modules.users.routes import router as users_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.orders.routes import router as orders_router


# ============================================================
# CONFIGURACIÓN DE FASTAPI
# ============================================================

app = FastAPI(
    title=settings.app_name,
    description=(
        "API para administrar ventas, inventario, "
        "sucursales y pagos de una cadena de repostería."
    ),
    version="1.0.0",
    debug=settings.debug,
    docs_url="/docs"
    if settings.docs_enabled and settings.app_env not in {"production", "staging"}
    else None,
    redoc_url="/redoc"
    if settings.docs_enabled and settings.app_env not in {"production", "staging"}
    else None,
    openapi_url="/openapi.json"
    if settings.docs_enabled and settings.app_env not in {"production", "staging"}
    else None,
)


register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


# ============================================================
# REGISTRO DE RUTAS GENERALES
# ============================================================

app.include_router(health_router)
app.include_router(roles_router)
app.include_router(auth_router)


# ============================================================
# REGISTRO DE MÓDULOS
# ============================================================

app.include_router(products_router)
app.include_router(categories_router)
app.include_router(branches_router)
app.include_router(customers_router)
app.include_router(employees_router)
app.include_router(users_router)
app.include_router(inventory_router)
app.include_router(orders_router)


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================


@app.get("/", tags=["Inicio"])
def root():
    """Comprueba que la API está disponible."""

    return {
        "message": "Sistema de Gestión de Repostería",
        "status": "ok",
    }


import app.db.models as registered_models  # noqa: F401
from app.modules.sales.routes import router as sales_router

app.include_router(sales_router)
from app.modules.payments.routes import router as payments_router

app.include_router(payments_router)
from app.modules.tickets.routes import router as tickets_router

app.include_router(tickets_router)
from app.modules.invoices.routes import router as invoices_router

app.include_router(invoices_router)
from app.modules.reports.routes import router as reports_router

app.include_router(reports_router)
from app.modules.orders.customer_routes import router as orders_customer_routes

app.include_router(orders_customer_routes)
from app.modules.customers.self_routes import router as customers_self_routes

app.include_router(customers_self_routes)
from app.modules.branches.proximity_routes import router as branches_proximity_routes

app.include_router(branches_proximity_routes)
