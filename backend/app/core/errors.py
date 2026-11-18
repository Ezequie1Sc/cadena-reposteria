"""Respuestas de error sin cuerpos de entrada, SQL ni credenciales."""

import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # input/ctx may contain passwords, nested payloads or arbitrary objects.
        errors = [
            {"type": item["type"], "loc": item["loc"], "msg": item["msg"]}
            for item in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "No fue posible completar la operación de base de datos"
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled application error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500, content={"detail": "Error interno del servidor"}
        )
