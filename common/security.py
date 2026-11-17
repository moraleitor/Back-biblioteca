"""Utilidades compartidas de seguridad: hash de contraseñas y tokens JWT."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

ALGORITHM = "HS256"
TOKEN_HOURS = 8
ITERATIONS = 120_000


def secret() -> str:
    return os.getenv("JWT_SECRET", "dev-secret-change-me-please-32bytes!!")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "email": email, "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "El token expiró")
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido")


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta el token de autenticación")
    return authorization.split(" ", 1)[1].strip()


def current_user_id(authorization: str | None = Header(default=None)) -> int:
    """Dependencia FastAPI: devuelve el id del usuario autenticado."""
    return int(decode_token(bearer_token(authorization))["sub"])
