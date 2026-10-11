
from fastapi import APIRouter, HTTPException
from postgrest.exceptions import APIError

from app.core.supabase import supabase


router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
)


@router.get("")
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
