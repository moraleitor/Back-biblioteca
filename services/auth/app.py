"""Servicio de autenticación: registro, inicio de sesión y perfil."""
import re
import sqlite3

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.security import create_token, current_user_id, hash_password, verify_password
from common.store import Db, default_path, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


def create_app(db_path: str | None = None) -> FastAPI:
    db = Db(db_path or default_path("auth"), SCHEMA)
    app = FastAPI(title="Servicio de autenticación")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "auth"}

    @app.post("/register", status_code=201)
    def register(body: RegisterIn):
        email = body.email.strip().lower()
        if not EMAIL_RE.match(email):
            raise HTTPException(422, "Correo electrónico no válido")
        try:
            uid = db.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?,?,?,?)",
                (email, body.name.strip(), hash_password(body.password), now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Ya existe una cuenta con ese correo")
        return {"id": uid, "email": email, "name": body.name.strip()}

    @app.post("/login")
    def login(body: LoginIn):
        user = db.one("SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),))
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Correo o contraseña incorrectos")
        return {"access_token": create_token(user["id"], user["email"]), "token_type": "bearer"}

    @app.get("/me")
    def me(user_id: int = Depends(current_user_id)):
        user = db.one("SELECT id, email, name, created_at FROM users WHERE id = ?", (user_id,))
        if not user:
            raise HTTPException(404, "Usuario no encontrado")
        return user

    return app
