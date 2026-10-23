
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.branches.repository import branch_repository
from app.modules.branches.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
)


class BranchService:
    """Lógica de negocio para administrar sucursales."""

    def get_branches(
        self,
        db: Session,
        busqueda: str | None = None,
        solo_activos: bool = True,
    ) -> list[BranchResponse]:
        branches = branch_repository.get_all(
            db=db,
            busqueda=busqueda,
            solo_activos=solo_activos,
        )

        return [
            BranchResponse.model_validate(branch)
            for branch in branches
        ]

    def get_branch_by_id(
        self,
        db: Session,
        branch_id: int,
    ) -> BranchResponse | None:
        branch = branch_repository.get_by_id(
            db=db,
            branch_id=branch_id,
        )

        if branch is None:
            return None

        return BranchResponse.model_validate(branch)

    def validate_code(
        self,
        db: Session,
        codigo: str,
        exclude_branch_id: int | None = None,
    ) -> None:
        existing = branch_repository.get_by_code(
            db,
            codigo,
        )

        if (
            existing is not None
            and existing.id != exclude_branch_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Ya existe una sucursal con este código",
            )

    def create_branch(
        self,
        db: Session,
        data: BranchCreate,
    ) -> BranchResponse:
        self.validate_code(db, data.codigo)

        try:
            branch = branch_repository.create(db, data)

            db.commit()
            db.refresh(branch)

            return BranchResponse.model_validate(branch)

        except IntegrityError as exc:
            db.rollback()

            raise HTTPException(
                status_code=409,
                detail=(
                    "No se pudo crear la sucursal "
                    "por un conflicto de datos"
                ),
            ) from exc

    def update_branch(
        self,
        db: Session,
        branch_id: int,
        data: BranchUpdate,
    ) -> BranchResponse:
        branch = branch_repository.get_by_id(
            db,
            branch_id,
        )

        if branch is None:
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada",
            )

        changes = data.model_dump(exclude_unset=True)

        # Campos obligatorios según la estructura de Supabase.
        required_fields = {
            "nombre",
            "codigo",
            "direccion",
            "ciudad",
            "estado",
        }

        # Evitar valores NULL en columnas NOT NULL.
        if any(
            field in changes and changes[field] is None
            for field in required_fields
        ):
            raise HTTPException(
                status_code=422,
                detail="Los campos obligatorios no pueden ser nulos",
            )

        # Verificar que el código no pertenezca a otra sucursal.
        if "codigo" in changes:
            self.validate_code(
                db,
                changes["codigo"],
                exclude_branch_id=branch_id,
            )

        try:
            branch = branch_repository.update(
                db,
                branch,
                data,
            )

            db.commit()
            db.refresh(branch)

            return BranchResponse.model_validate(branch)

        except IntegrityError as exc:
            db.rollback()

            raise HTTPException(
                status_code=409,
                detail=(
                    "No se pudo actualizar la sucursal "
                    "por un conflicto de datos"
                ),
            ) from exc

    def deactivate_branch(
        self,
        db: Session,
        branch_id: int,
    ) -> BranchResponse:
        branch = branch_repository.get_by_id(
            db,
            branch_id,
        )

        if branch is None:
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada",
            )

        if branch.activo:
            try:
                branch = branch_repository.deactivate(
                    db,
                    branch,
                )

                db.commit()
                db.refresh(branch)

            except IntegrityError as exc:
                db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="No se pudo desactivar la sucursal",
                ) from exc

        return BranchResponse.model_validate(branch)

    def reactivate_branch(
        self,
        db: Session,
        branch_id: int,
    ) -> BranchResponse:
        branch = branch_repository.get_by_id(
            db,
            branch_id,
        )

        if branch is None:
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada",
            )

        if not branch.activo:
            try:
                branch = branch_repository.reactivate(
                    db,
                    branch,
                )

                db.commit()
                db.refresh(branch)

            except IntegrityError as exc:
                db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="No se pudo reactivar la sucursal",
                ) from exc

        return BranchResponse.model_validate(branch)


branch_service = BranchService()
