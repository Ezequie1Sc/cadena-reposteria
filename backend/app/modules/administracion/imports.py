import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Annotated
from zipfile import ZipFile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.auth import DbSession
from app.core.permissions import AdminUser
from app.core.roles import RoleID
from app.shared.commerce import PositiveID

from .common import execute, required, row
from .onboarding import Hire, hire
from .responses import BatchStatus, ImportResult

router = APIRouter(
    prefix="/administracion/importaciones", tags=["Importación de empleados"]
)
HEADERS = ("nombre", "apellido", "email", "puesto", "codigo_sucursal")
MAX_ROWS = 5000


def sheet_rows(content):
    with ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 500 or sum(i.file_size for i in entries) > 20 * 1024**2:
            raise ValueError("Libro demasiado grande")
    book = load_workbook(
        io.BytesIO(content), read_only=True, data_only=False, keep_links=False
    )
    try:
        if len(book.worksheets) != 1:
            raise ValueError("Se requiere una sola hoja")
        sheet = book.active
        sheet.reset_dimensions()
        for cells in sheet.iter_rows():
            if len(cells) > len(HEADERS) or any(c.data_type == "f" for c in cells):
                raise ValueError("Columnas o fórmulas no admitidas")
            yield [str(c.value).strip() if c.value is not None else "" for c in cells]
    finally:
        book.close()


def parse_file(content, suffix):
    if len(content) > 5 * 1024**2:
        raise HTTPException(413, "Archivo demasiado grande")
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(415, "Se requiere CSV UTF-8 o XLSX")
    try:
        reader = (
            sheet_rows(content)
            if suffix == ".xlsx"
            else csv.reader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        )
        if tuple(next(reader, [])) != HEADERS:
            raise ValueError("Encabezados distintos de la plantilla")
        result = []
        for number, values in enumerate(reader, 2):
            if number > MAX_ROWS + 1:
                raise ValueError("Máximo 5000 filas")
            if any(len(v) > 300 for v in values):
                raise ValueError("Una celda excede el límite")
            if any(values):
                result.append(
                    {
                        "fila": number,
                        "datos": dict(zip(HEADERS, values)),
                        "error": None
                        if len(values) == len(HEADERS)
                        else "Número de columnas incorrecto",
                    }
                )
        if not result:
            raise ValueError("Archivo vacío")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            422, "Archivo inválido; utiliza la plantilla sin fórmulas"
        ) from exc


@router.get("/plantilla")
def template(actor: AdminUser):
    return Response(
        ",".join(HEADERS) + "\r\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=empleados.csv"},
    )


@router.post(
    "/vista-previa", response_model=ImportResult, response_model_exclude_none=True
)
def preview(db: DbSession, actor: AdminUser, archivo: Annotated[UploadFile, File()]):
    content = archivo.file.read(5 * 1024**2 + 1)
    fingerprint = hashlib.sha256(content).hexdigest()
    items = parse_file(content, Path(archivo.filename or "").suffix.lower())
    branches = dict(
        execute(db, "SELECT codigo,id FROM public.sucursales WHERE activo").all()
    )
    emails = [i["datos"].get("email", "").strip().lower() for i in items]
    used = set(
        execute(
            db,
            "SELECT lower(btrim(email)) FROM public.usuarios WHERE lower(btrim(email))=ANY(:emails)",
            emails=emails,
        ).scalars()
    )
    for item, email in zip(items, emails):
        data = dict(item["datos"])
        branch = branches.get(data.pop("codigo_sucursal", "").strip())
        try:
            hire_data = Hire(**data, sucursal_id=branch)
            item["alta"] = hire_data.model_dump(mode="json")
        except ValidationError:
            item["error"] = "Campos inválidos o sucursal inactiva/desconocida"
        if email in used:
            item["error"] = "Correo repetido o ya registrado"
        used.add(email)
        item["estado"] = "ERROR" if item["error"] else "VALIDA"
    batch = row(
        db,
        """INSERT INTO gestion_interna.lote(actor_id,huella,filas) VALUES(:a,:h,CAST(:f AS jsonb))
        ON CONFLICT(actor_id,huella) DO UPDATE SET huella=excluded.huella RETURNING id,estado,filas""",
        a=actor.id,
        h=fingerprint,
        f=json.dumps(items),
    )
    db.commit()
    return batch


def owned(db, identifier, actor, lock=False):
    return required(
        row(
            db,
            "SELECT * FROM gestion_interna.lote WHERE id=:id AND actor_id=:a"
            + (" FOR UPDATE" if lock else ""),
            id=identifier,
            a=actor.id,
        )
    )


@router.get(
    "/{identifier}", response_model=ImportResult, response_model_exclude_none=True
)
def detail(identifier: PositiveID, db: DbSession, actor: AdminUser):
    return owned(db, identifier, actor)


@router.post("/{identifier}/confirmar", response_model=BatchStatus)
def confirm(identifier: PositiveID, db: DbSession, actor: AdminUser):
    batch = owned(db, identifier, actor, True)
    if batch["estado"] == "PREVIO":
        execute(
            db,
            "UPDATE gestion_interna.lote SET estado='CONFIRMADO' WHERE id=:id",
            id=identifier,
        )
    db.commit()
    return {
        "id": identifier,
        "estado": "CONFIRMADO" if batch["estado"] == "PREVIO" else batch["estado"],
    }


def process_chunk(db):
    batch = row(
        db,
        """SELECT * FROM gestion_interna.lote WHERE estado='CONFIRMADO'
        ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED""",
    )
    if not batch:
        return False
    if not row(
        db,
        """SELECT u.id FROM public.usuarios u JOIN public.roles r ON r.id=u.rol_id
                   WHERE u.id=:id AND u.rol_id=:role AND r.nombre=:name AND u.activo AND r.activo FOR SHARE""",
        id=batch["actor_id"],
        role=RoleID.ADMINISTRADOR,
        name=RoleID.ADMINISTRADOR.catalog_name,
    ):
        execute(
            db,
            "UPDATE gestion_interna.lote SET estado='SUSPENDIDO' WHERE id=:id",
            id=batch["id"],
        )
        db.commit()
        return True
    items = batch["filas"]
    for item in [i for i in items if i["estado"] == "VALIDA"][:50]:
        try:
            with db.begin_nested():
                identifier = hire(db, Hire(**item["alta"]), batch["actor_id"])
            item.update(estado="CREADA", empleado_id=identifier)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
            item.update(estado="ERROR", error=exc.detail)
        except IntegrityError:
            item.update(
                estado="ERROR", error="Conflicto de integridad; revisar registro"
            )
    state = "CONFIRMADO" if any(i["estado"] == "VALIDA" for i in items) else "TERMINADO"
    execute(
        db,
        "UPDATE gestion_interna.lote SET filas=CAST(:f AS jsonb),estado=:s WHERE id=:id",
        f=json.dumps(items),
        s=state,
        id=batch["id"],
    )
    db.commit()
    return True


@router.get("/{identifier}/errores.csv")
def errors(identifier: PositiveID, db: DbSession, actor: AdminUser):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(("fila", "error"))
    for item in owned(db, identifier, actor)["filas"]:
        if item["error"]:
            writer.writerow((item["fila"], item["error"]))
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=errores.csv"},
    )
