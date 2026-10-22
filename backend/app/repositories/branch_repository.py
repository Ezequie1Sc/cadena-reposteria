
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.schemas.branch import BranchCreate, BranchUpdate


class BranchRepository:
    """Operaciones de acceso a datos para sucursales."""

    def get_all(
        self,
        db: Session,
        busqueda: str | None = None,
        solo_activos: bool = True,
    ) -> list[Branch]:
        query = select(Branch)

        if solo_activos:
            query = query.where(Branch.activo.is_(True))

        if busqueda:
            termino = busqueda.strip()

            if termino:
                query = query.where(
                    Branch.nombre.ilike(f"%{termino}%")
                    | Branch.codigo.ilike(f"%{termino}%")
                )

        query = query.order_by(Branch.nombre, Branch.id)

        return list(db.scalars(query).all())

    def get_by_id(
        self,
        db: Session,
        branch_id: int,
    ) -> Branch | None:
        return db.get(Branch, branch_id)

    def get_by_code(
        self,
        db: Session,
        codigo: str,
    ) -> Branch | None:
        query = select(Branch).where(
            func.lower(Branch.codigo) == codigo.strip().lower()
        )

        return db.scalar(query)

    def create(
        self,
        db: Session,
        data: BranchCreate,
    ) -> Branch:
        branch = Branch(**data.model_dump())

        db.add(branch)
        db.flush()
        db.refresh(branch)

        return branch

    def update(
        self,
        db: Session,
        branch: Branch,
        data: BranchUpdate,
    ) -> Branch:
        changes = data.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(branch, field, value)

        if changes:
            db.flush()
            db.refresh(branch)

        return branch

    def deactivate(
        self,
        db: Session,
        branch: Branch,
    ) -> Branch:
        branch.activo = False

        db.flush()
        db.refresh(branch)

        return branch

    def reactivate(
        self,
        db: Session,
        branch: Branch,
    ) -> Branch:
        branch.activo = True

        db.flush()
        db.refresh(branch)

        return branch


branch_repository = BranchRepository()
