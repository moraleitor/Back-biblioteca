import io
import shutil

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from common import registry
from services.ai.app import create_app as ai_app
from services.auth.app import create_app as auth_app
from services.backup.app import create_app as backup_app
from services.gateway.app import create_app as gateway_app
from services.library.app import create_app as library_app
from services.notes.app import create_app as notes_app
from services.ocr.app import create_app as ocr_app

HAS_TESSERACT = shutil.which("tesseract") is not None


@pytest.fixture
def apps(tmp_path):
    built = {
        "auth": auth_app(str(tmp_path / "auth.db")),
        "library": library_app(str(tmp_path / "library.db")),
        "notes": notes_app(str(tmp_path / "notes.db")),
        "ocr": ocr_app(),
        "ai": ai_app(),
        "backup": backup_app(str(tmp_path / "backup.db")),
    }
    registry.use_apps(built)
    yield built
    registry._transports.clear()


@pytest.fixture
def gw(apps):
    return TestClient(gateway_app())


def make_user(client: TestClient, email="ana@correo.com", password="clave-segura-1"):
    r = client.post("/api/auth/register", json={"email": email, "name": "Ana", "password": password})
    assert r.status_code == 201, r.text
    t = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def auth(gw):
    return make_user(gw)


def text_image(text="Hello World", size=(900, 260), font_size=64, fmt="PNG") -> bytes:
    img = Image.new("RGB", size, "white")
    ImageDraw.Draw(img).text((30, 80), text, fill="black", font=ImageFont.load_default(size=font_size))
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()
