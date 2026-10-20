
from typing import Any

from postgrest.exceptions import APIError

from app.core.supabase import supabase


class ProductRepository:
    """Gestiona el acceso a productos almacenados en Supabase."""

    def get_all(
        self,
        busqueda: str | None = None,
        categoria_id: int | None = None,
        solo_activos: bool = True,
    ) -> list[dict[str, Any]]:
        query = supabase.table("productos").select(
            "id, categoria_id, nombre, descripcion, sku, "
            "precio, imagen_url, activo, created_at, updated_at"
        )

        if solo_activos:
            query = query.eq("activo", True)

        if busqueda:
            termino = busqueda.strip()
            if termino:
                query = query.ilike("nombre", f"%{termino}%")

        if categoria_id is not None:
            query = query.eq("categoria_id", categoria_id)

        response = query.order("nombre").execute()

        return response.data

    def get_by_id(
        self,
        product_id: int,
    ) -> dict[str, Any] | None:
        response = (
            supabase.table("productos")
            .select(
                "id, categoria_id, nombre, descripcion, sku, "
                "precio, imagen_url, activo, created_at, updated_at"
            )
            .eq("id", product_id)
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None


product_repository = ProductRepository()
