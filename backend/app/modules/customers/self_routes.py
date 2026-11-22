from app.core.roles import RoleID
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.core.auth import CurrentUser, DbSession
from app.modules.users.model import User
from app.modules.customers.model import Customer
from app.modules.customers.schemas import CustomerResponse
from app.shared.commerce import atomic

router = APIRouter(prefix="/mi-perfil", tags=["Perfil de cliente"])


@atomic
def ensure_profile(db, actor):
    if actor.rol_id != RoleID.CLIENTE:
        raise HTTPException(403, "Sólo clientes")
    db.execute(select(User.id).where(User.id == actor.id).with_for_update())
    profile = db.scalar(select(Customer).where(Customer.usuario_id == actor.id))
    if profile is None:
        profile = Customer(
            usuario_id=actor.id,
            nombre=actor.nombre,
            apellido=actor.apellido,
            email=actor.email,
            telefono=actor.telefono,
            activo=True,
        )
        db.add(profile)
        db.flush()
    if not profile.activo:
        raise HTTPException(403, "Perfil desactivado")
    return CustomerResponse.model_validate(profile)


@router.post("", response_model=CustomerResponse)
def create_profile(db: DbSession, actor: CurrentUser):
    """Completa una cuenta cliente antigua; nunca vincula por correo ni cambia propietario."""
    return ensure_profile(db, actor)
