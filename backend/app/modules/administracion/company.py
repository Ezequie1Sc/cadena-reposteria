from datetime import date

from fastapi import APIRouter
from pydantic import Field, HttpUrl, model_validator

from app.core.auth import DbSession
from app.core.permissions import AdminUser
from app.shared.commerce import PositiveID, StrictModel, atomic

from .common import execute, required, row, rows

router = APIRouter(prefix="/administracion", tags=["Configuración empresarial"])


class Identity(StrictModel):
    nombre: str = Field(min_length=1, max_length=150)
    logotipo: HttpUrl | None = None
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    mensaje: str = Field(max_length=2000)
    firma: str = Field(max_length=300)
    contacto: str = Field(max_length=300)


class Benefit(StrictModel):
    nombre: str = Field(min_length=1, max_length=160)
    condiciones: str = Field(max_length=2000)
    activo: bool = True
    inicio: date | None = None
    fin: date | None = None
    sucursal_id: int | None = Field(None, gt=0)
    empleado_id: int | None = Field(None, gt=0)
    puesto: str | None = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def interval(self):
        if self.inicio and self.fin and self.fin < self.inicio:
            raise ValueError("Vigencia invertida")
        return self


class ConfiguredBenefit(Benefit):
    id: int


def applicable(db, emp):
    return rows(
        db,
        """SELECT nombre, condiciones FROM gestion_interna.beneficio WHERE activo
      AND (inicio IS NULL OR inicio<=CURRENT_DATE) AND (fin IS NULL OR fin>=CURRENT_DATE)
      AND (sucursal_id IS NULL OR sucursal_id=:sucursal_id)
      AND (puesto IS NULL OR lower(puesto)=lower(:puesto))
      AND (empleado_id IS NULL OR empleado_id=:empleado_id) ORDER BY id""",
        **dict(emp),
    )


@router.get("/identidad", response_model=Identity | None)
def identity(db: DbSession, actor: AdminUser):
    return execute(
        db, "SELECT datos FROM gestion_interna.identidad WHERE id=1"
    ).scalar_one_or_none()


@router.put("/identidad", response_model=Identity)
def put_identity(data: Identity, db: DbSession, actor: AdminUser):
    execute(
        db,
        """INSERT INTO gestion_interna.identidad VALUES(1,CAST(:d AS jsonb))
            ON CONFLICT(id) DO UPDATE SET datos=excluded.datos""",
        d=data.model_dump_json(),
    )
    db.commit()
    return data


@router.get("/beneficios", response_model=list[ConfiguredBenefit])
def benefits(db: DbSession, actor: AdminUser):
    return rows(db, "SELECT * FROM gestion_interna.beneficio ORDER BY id")


@atomic
def save_benefit(db, data, identifier=None):
    fields = data.model_dump()
    if identifier is None:
        sql = f"INSERT INTO gestion_interna.beneficio ({','.join(fields)}) VALUES ({','.join(':' + k for k in fields)})"
    else:
        sql = (
            "UPDATE gestion_interna.beneficio SET "
            + ",".join(k + "=:" + k for k in fields)
            + " WHERE id=:id"
        )
    return required(row(db, sql + " RETURNING *", id=identifier, **fields))


@router.post("/beneficios", status_code=201, response_model=ConfiguredBenefit)
def new_benefit(data: Benefit, db: DbSession, actor: AdminUser):
    return save_benefit(db, data)


@router.put("/beneficios/{identifier}", response_model=ConfiguredBenefit)
def edit_benefit(
    identifier: PositiveID, data: Benefit, db: DbSession, actor: AdminUser
):
    return save_benefit(db, data, identifier)
