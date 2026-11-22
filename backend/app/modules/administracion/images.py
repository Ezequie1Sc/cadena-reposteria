import hashlib
import json
import re
import uuid
import warnings
from io import BytesIO
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from app.core.auth import DbSession
from app.core.config import settings
from app.core.permissions import AdminUser
from app.shared.commerce import (
    Key,
    PositiveID,
    atomic,
    begin_idempotency,
    finish_idempotency,
)

from .catalog import ProductRegistration, product_transaction
from .common import execute, required, row
from .responses import Photo, ProductWithPhoto

router = APIRouter(tags=["Fotografías"])
MAX_BYTES = 5 * 1024 * 1024
FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


def validate_image(content, declared):
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Máximo 5 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as img:
                fmt = img.format
                if fmt not in FORMATS or FORMATS[fmt][1] != declared:
                    raise HTTPException(415, "Formato de imagen incompatible")
                if (
                    img.width * img.height > 20000000
                    or getattr(img, "n_frames", 1) != 1
                ):
                    raise HTTPException(422, "Dimensiones o animación no permitidas")
                img.verify()
            with Image.open(BytesIO(content)) as img:
                img.load()
                # Sirve una imagen recodificada sin EXIF ni bytes anexos.
                out = BytesIO()
                img = img.convert("RGB" if fmt == "JPEG" else "RGBA")
                img.info.clear()
                img.save(out, format=fmt)
                clean = out.getvalue()
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ):
        raise HTTPException(422, "Archivo de imagen inválido") from None
    if len(clean) > MAX_BYTES:
        raise HTTPException(413, "La imagen procesada supera 5 MiB")
    return clean, *FORMATS[fmt]


def storage_base():
    base = (settings.supabase_url or "").rstrip("/")
    if urlsplit(base).scheme != "https" or not settings.supabase_storage_key:
        raise HTTPException(503, "Configura el acceso de Storage en el servidor")
    return base + "/storage/v1/object"


def storage(method, key, content=None, mime=None):
    if not re.fullmatch(r"catalogo/[0-9a-f]{32}\.(jpg|png|webp)", key):
        raise ValueError("Clave de objeto fuera del catálogo gestionado")
    headers = {"apikey": settings.supabase_storage_key}
    if not settings.supabase_storage_key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + settings.supabase_storage_key
    if mime:
        headers["Content-Type"] = mime
    try:
        if method == "DELETE":
            resp = httpx.request(
                "DELETE",
                storage_base() + "/productos",
                headers=headers,
                json={"prefixes": [key]},
                timeout=15,
            )
        else:
            resp = httpx.request(
                "POST",
                storage_base() + "/productos/" + key,
                headers=headers,
                content=content,
                timeout=15,
            )
        resp.raise_for_status()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Storage no confirmó la operación") from None


def retire(db, product):
    old = row(
        db,
        "SELECT id FROM public.producto_imagenes WHERE producto_id=:id AND es_principal FOR UPDATE",
        id=product,
    )
    if old:
        execute(
            db,
            """UPDATE gestion_interna.objeto SET estado='RETIRADO', revisar=now()+interval '1 day'
                   WHERE imagen_id=:id""",
            id=old["id"],
        )
        execute(
            db,
            "UPDATE public.producto_imagenes SET es_principal=false WHERE id=:id",
            id=old["id"],
        )


@atomic
def attach(
    db, actor, product, registration, key, fingerprint, object_key, content, mime
):
    prior, digest = begin_idempotency(db, actor, "foto_producto", key, fingerprint)
    if prior:
        return execute(
            db,
            "SELECT respuesta FROM gestion_interna.recibo_foto WHERE actor_id=:a AND clave=:k",
            a=actor.id,
            k=key,
        ).scalar_one()
    required(
        row(
            db,
            "SELECT clave FROM gestion_interna.objeto WHERE clave=:k AND estado='PREPARADO' FOR UPDATE",
            k=object_key,
        )
    )
    result = {}
    if registration:
        result = product_transaction(db, actor, registration, key)
        product = result["producto"]["id"]
    required(
        row(db, "SELECT id FROM public.productos WHERE id=:id FOR UPDATE", id=product)
    )
    storage("POST", object_key, content, mime)
    retire(db, product)
    url = storage_base() + "/public/productos/" + object_key
    image = execute(
        db,
        """INSERT INTO public.producto_imagenes(producto_id,url,es_principal)
                   VALUES(:p,:url,true) RETURNING id""",
        p=product,
        url=url,
    ).scalar_one()
    execute(
        db,
        "UPDATE public.productos SET imagen_url=:url, updated_at=now() WHERE id=:p",
        url=url,
        p=product,
    )
    execute(
        db,
        "UPDATE gestion_interna.objeto SET estado='VIGENTE',producto_id=:p,imagen_id=:i WHERE clave=:k",
        p=product,
        i=image,
        k=object_key,
    )
    finish_idempotency(db, actor, "foto_producto", key, digest, product)
    if registration:
        result["producto"] = {**result["producto"], "imagen_url": url}
    response = jsonable_encoder(
        {**result, "producto_id": product, "imagen_id": image, "url": url}
    )
    execute(
        db,
        "INSERT INTO gestion_interna.recibo_foto VALUES(:a,:k,CAST(:v AS jsonb))",
        a=actor.id,
        k=key,
        v=json.dumps(response),
    )
    return response


def upload(db, actor, file, key, product=None, registration=None):
    raw = file.file.read(MAX_BYTES + 1)
    clean, ext, mime = validate_image(raw, file.content_type)
    fingerprint = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "producto": product,
        "alta": registration.model_dump(mode="json") if registration else None,
    }
    prior, _ = begin_idempotency(db, actor, "foto_producto", key, fingerprint)
    if prior:
        return execute(
            db,
            "SELECT respuesta FROM gestion_interna.recibo_foto WHERE actor_id=:a AND clave=:k",
            a=actor.id,
            k=key,
        ).scalar_one()
    if product:
        required(row(db, "SELECT id FROM public.productos WHERE id=:p", p=product))
    object_key = "catalogo/" + uuid.uuid4().hex + "." + ext
    execute(
        db,
        "INSERT INTO gestion_interna.objeto(clave,producto_id,estado) VALUES(:k,:p,'PREPARADO')",
        k=object_key,
        p=product,
    )
    db.commit()
    return attach(
        db, actor, product, registration, key, fingerprint, object_key, clean, mime
    )


@router.post(
    "/administracion/productos/con-imagen",
    status_code=201,
    response_model=ProductWithPhoto,
)
def product_with_image(
    db: DbSession,
    actor: AdminUser,
    idempotency_key: Key,
    datos: Annotated[str, Form()],
    archivo: Annotated[UploadFile, File()],
):
    try:
        data = ProductRegistration.model_validate_json(datos)
    except ValidationError:
        raise HTTPException(422, "Datos de producto o inventarios inválidos") from None
    return upload(db, actor, archivo, idempotency_key, registration=data)


@router.put("/administracion/productos/{identifier}/imagen", response_model=Photo)
def replace_photo(
    identifier: PositiveID,
    db: DbSession,
    actor: AdminUser,
    idempotency_key: Key,
    archivo: Annotated[UploadFile, File()],
):
    return upload(db, actor, archivo, idempotency_key, product=identifier)


@router.delete("/administracion/productos/{identifier}/imagenes/{image_id}")
def remove_photo(
    identifier: PositiveID, image_id: PositiveID, db: DbSession, actor: AdminUser
):
    required(
        row(db, "SELECT id FROM public.productos WHERE id=:p FOR UPDATE", p=identifier)
    )
    old = required(
        row(
            db,
            """SELECT i.es_principal,o.clave FROM public.producto_imagenes i
        JOIN gestion_interna.objeto o ON o.imagen_id=i.id
        WHERE i.id=:i AND i.producto_id=:p FOR UPDATE""",
            i=image_id,
            p=identifier,
        )
    )
    execute(
        db,
        "UPDATE gestion_interna.objeto SET estado='RETIRADO',revisar=now()+interval '1 day' WHERE clave=:k",
        k=old["clave"],
    )
    if old["es_principal"]:
        execute(
            db,
            "UPDATE public.productos SET imagen_url=NULL, updated_at=now() WHERE id=:p",
            p=identifier,
        )
    execute(db, "DELETE FROM public.producto_imagenes WHERE id=:i", i=image_id)
    db.commit()
    return {"retirada": True}


def clean_one(db):
    item = row(
        db,
        """SELECT * FROM gestion_interna.objeto WHERE estado IN ('PREPARADO','RETIRADO')
        AND revisar<=now() ORDER BY revisar LIMIT 1 FOR UPDATE SKIP LOCKED""",
    )
    if not item:
        return False
    url = storage_base() + "/public/productos/" + item["clave"]
    if row(
        db,
        """SELECT 1 FROM public.producto_imagenes WHERE id=:id AND es_principal""",
        id=item["imagen_id"],
    ) or row(
        db,
        """SELECT 1 FROM public.productos WHERE imagen_url=:url UNION ALL
              SELECT 1 FROM public.producto_imagenes WHERE url=:url AND id IS DISTINCT FROM :id LIMIT 1""",
        url=url,
        id=item["imagen_id"],
    ):
        execute(
            db,
            "UPDATE gestion_interna.objeto SET revisar=now()+interval '1 day' WHERE clave=:k",
            k=item["clave"],
        )
    else:
        try:
            storage("DELETE", item["clave"])
        except HTTPException:
            execute(
                db,
                "UPDATE gestion_interna.objeto SET revisar=now()+interval '10 minutes' WHERE clave=:k",
                k=item["clave"],
            )
            db.commit()
            raise
        execute(
            db,
            "DELETE FROM public.producto_imagenes WHERE id=:id AND NOT es_principal",
            id=item["imagen_id"],
        )
        execute(
            db, "DELETE FROM gestion_interna.objeto WHERE clave=:k", k=item["clave"]
        )
    db.commit()
    return True
