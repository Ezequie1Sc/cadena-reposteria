
from fastapi import FastAPI

from app.core.config import settings
from app.api.routes.health import router as health_router
from app.api.routes.roles import router as roles_router
from app.modules.products.routes import router as products_router
from app.modules.categories.routes import router as categories_router
from app.modules.branches.routes import router as branches_router
from app.modules.customers.routes import router as customers_router


app = FastAPI(
    title=settings.app_name,
    description=(
        "API para administrar ventas, inventario, "
        "sucursales y pagos de una cadena de repostería."
    ),
    version="1.0.0",
    debug=settings.debug,
)

# Registrar las rutas de la API
app.include_router(health_router)
app.include_router(roles_router)
app.include_router(products_router)
app.include_router(categories_router)
app.include_router(branches_router)
app.include_router(customers_router)


@app.get("/", tags=["Inicio"])
def root():
    return {
        "message": "Sistema de Gestión de Repostería",
        "status": "ok",
    }
