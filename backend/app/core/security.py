"""Funciones de seguridad para el manejo de contraseñas."""

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type


_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Genera un hash seguro Argon2id."""

    if not isinstance(password, str):
        raise TypeError("La contraseña debe ser una cadena de texto.")

    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    return _password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """Verifica una contraseña contra su hash."""

    if not isinstance(password, str):
        return False

    if not isinstance(password_hash, str):
        return False

    try:
        return _password_hasher.verify(
            password_hash,
            password,
        )
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Comprueba si el hash necesita actualizarse."""

    if not isinstance(password_hash, str):
        return True

    try:
        return _password_hasher.check_needs_rehash(
            password_hash,
        )
    except (InvalidHashError, ValueError, TypeError):
        return True