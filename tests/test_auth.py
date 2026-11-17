from tests.conftest import make_user


def test_register_login_me(gw):
    h = make_user(gw)
    me = gw.get("/api/auth/me", headers=h)
    assert me.status_code == 200
    assert me.json()["email"] == "ana@correo.com"
    assert "password" not in me.text


def test_duplicate_email_conflict(gw):
    make_user(gw)
    r = gw.post("/api/auth/register", json={"email": "ANA@correo.com", "name": "Otra", "password": "otra-clave-1"})
    assert r.status_code == 409


def test_invalid_email_and_short_password(gw):
    assert gw.post("/api/auth/register", json={"email": "no-es-correo", "name": "A", "password": "12345678"}).status_code == 422
    assert gw.post("/api/auth/register", json={"email": "a@b.co", "name": "A", "password": "123"}).status_code == 422


def test_wrong_password_rejected(gw):
    make_user(gw)
    r = gw.post("/api/auth/login", json={"email": "ana@correo.com", "password": "incorrecta-123"})
    assert r.status_code == 401


def test_password_is_hashed(apps):
    from common.security import hash_password, verify_password
    h = hash_password("secreto-123")
    assert "secreto-123" not in h and verify_password("secreto-123", h) and not verify_password("otro", h)
