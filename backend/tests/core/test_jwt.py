
"""Pruebas de generación y validación de tokens JWT."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.jwt import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
)


def sign_token(payload: dict, secret: str | None = None) -> str:
    """Firma un payload para probar distintos escenarios."""

    return jwt.encode(
        payload,
        secret if secret is not None else settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def valid_payload(user_id: str = "1") -> dict:
    """Genera las reclamaciones obligatorias de un token válido."""

    now = datetime.now(timezone.utc)

    return {
        "sub": user_id,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=30),
        "type": "access",
    }


def test_create_and_decode_access_token():
    token = create_access_token(15)

    assert isinstance(token, str)
    assert decode_access_token(token) == 15


def test_token_contains_required_claims():
    token = create_access_token(7)

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "7"
    assert payload["type"] == "access"
    assert all(
        claim in payload
        for claim in ("iat", "nbf", "exp")
    )


def test_custom_expiration():
    token = create_access_token(
        1,
        expires_delta=timedelta(minutes=5),
    )

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["exp"] - payload["iat"] == 300


@pytest.mark.parametrize("user_id", [0, -1, True, "1", None])
def test_create_rejects_invalid_user_id(user_id):
    with pytest.raises(ValueError):
        create_access_token(user_id)


@pytest.mark.parametrize(
    "duration",
    [
        timedelta(seconds=0),
        timedelta(seconds=-1),
    ],
)
def test_create_rejects_invalid_duration(duration):
    with pytest.raises(ValueError):
        create_access_token(1, expires_delta=duration)


def test_rejects_expired_token():
    payload = valid_payload()
    payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)

    token = sign_token(payload)

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_rejects_token_not_yet_valid():
    payload = valid_payload()
    payload["nbf"] = datetime.now(timezone.utc) + timedelta(minutes=5)

    token = sign_token(payload)

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_rejects_invalid_signature():
    token = sign_token(
        valid_payload(),
        secret="una-clave-distinta-a-la-configurada",
    )

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_rejects_modified_payload():
    token = create_access_token(1)

    header, payload, signature = token.split(".")

    modified_payload = (
        payload[:-1] + ("A" if payload[-1] != "A" else "B")
    )

    modified_token = (
        f"{header}.{modified_payload}.{signature}"
    )

    with pytest.raises(TokenValidationError):
        decode_access_token(modified_token)


def test_rejects_wrong_token_type():
    payload = valid_payload()
    payload["type"] = "refresh"

    token = sign_token(payload)

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_rejects_missing_required_claim():
    payload = valid_payload()
    del payload["exp"]

    token = sign_token(payload)

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "subject",
    ["0", "-1", "abc", "1.5", "", " 1", "١", None],
)
def test_rejects_invalid_subject(subject):
    payload = valid_payload()
    payload["sub"] = subject

    token = sign_token(payload)

    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "token",
    ["", " ", "invalid.token.value", None, 123],
)
def test_rejects_malformed_token(token):
    with pytest.raises(TokenValidationError):
        decode_access_token(token)
