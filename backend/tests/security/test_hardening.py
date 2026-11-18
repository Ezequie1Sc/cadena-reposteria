from datetime import datetime, timedelta, timezone
import jwt
import pytest
from pydantic import ValidationError
from app.core.config import Settings, settings
from app.core.jwt import decode_access_token, TokenValidationError


@pytest.mark.parametrize(
    "subject", ["9" * 5000, "9223372036854775808", "0", "-1", "1.0"]
)
def test_invalid_jwt_subject_controlled(subject):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": subject,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "values",
    [
        {"jwt_secret_key": "short"},
        {"jwt_secret_key": "a" * 64},
        {"jwt_algorithm": "none"},
        {"debug": True, "app_env": "production"},
        {"jwt_access_token_expire_minutes": 0},
        {"cors_origins": ["*"]},
    ],
)
def test_unsafe_configuration_rejected(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
