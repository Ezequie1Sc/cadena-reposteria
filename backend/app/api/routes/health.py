
from fastapi import APIRouter, HTTPException
from postgrest.exceptions import APIError

from app.core.supabase import supabase


router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "API funcionando correctamente",
    }


@router.get("/health/database")
def database_health():
    try:
        supabase.table("roles").select("id").limit(1).execute()

        return {
            "status": "ok",
            "database": "connected",
            "provider": "Supabase",
        }

    except APIError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos de Supabase",
        ) from exc


@router.get("/roles", tags=["Roles"])
def get_roles():
    try:
        response = (
            supabase.table("roles")
            .select("id, nombre, descripcion, activo")
            .eq("activo", True)
            .execute()
        )

        return {
            "total": len(response.data),
            "roles": response.data,
        }

    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar los roles en Supabase",
        ) from exc
