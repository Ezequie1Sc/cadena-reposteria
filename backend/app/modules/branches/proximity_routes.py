from math import radians, sin, cos, atan2, sqrt
from typing import Annotated
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select
from app.core.auth import DbSession, CurrentUser
from app.modules.branches.model import Branch

router = APIRouter(prefix="/sucursales-cercanas", tags=["Sucursales"])


class NearbyBranch(BaseModel):
    id: int
    nombre: str
    distancia_km: float
    tipo_distancia: str = (
        "Geodésica; no es distancia por carretera ni cobertura de reparto"
    )


@router.get("", response_model=list[NearbyBranch])
def nearest(
    db: DbSession,
    actor: CurrentUser,
    latitud: Annotated[float, Query(ge=-90, le=90)],
    longitud: Annotated[float, Query(ge=-180, le=180)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    branches = db.scalars(
        select(Branch).where(
            Branch.activo.is_(True),
            Branch.latitud.is_not(None),
            Branch.longitud.is_not(None),
        )
    )
    result = []
    for b in branches:
        lat1, lat2 = radians(latitud), radians(float(b.latitud))
        dl = radians(float(b.longitud) - longitud)
        a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dl / 2) ** 2
        distance = 6371 * 2 * atan2(sqrt(max(0, a)), sqrt(max(0, 1 - a)))
        result.append(
            NearbyBranch(id=b.id, nombre=b.nombre, distancia_km=round(distance, 3))
        )
    return sorted(result, key=lambda b: (b.distancia_km, b.id))[:limit]
