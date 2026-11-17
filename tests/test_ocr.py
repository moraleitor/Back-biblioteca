import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from services.ocr.app import OcrUnavailable, create_app
from common.security import create_token
from tests.conftest import HAS_TESSERACT, text_image

H = {"Authorization": f"Bearer {create_token(1, 'a@b.co')}"}


def post(client, data, ctype="image/png", name="p.png"):
    return client.post("/extract", files={"file": (name, data, ctype)}, headers=H)


@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract no instalado")
def test_real_ocr_reads_text():
    r = post(TestClient(create_app()), text_image("Hello World"))
    assert r.status_code == 200
    body = r.json()
    assert "hello" in body["text"].lower() and body["confidence"] > 50


def test_engine_is_pluggable():
    fake = lambda img: {"text": "texto falso", "confidence": 99.0, "language": "eng"}
    r = post(TestClient(create_app(engine=fake)), text_image())
    assert r.json()["text"] == "texto falso"


def test_rejects_non_image_type_and_corrupt_and_empty():
    c = TestClient(create_app(engine=lambda i: {"text": "", "confidence": 0, "language": "eng"}))
    assert post(c, b"hola", "text/plain", "a.txt").status_code == 415
    assert post(c, b"no-soy-imagen").status_code == 400
    assert post(c, b"").status_code == 400


def test_too_large(monkeypatch):
    import services.ocr.app as mod
    monkeypatch.setattr(mod, "MAX_BYTES", 100)
    assert post(TestClient(create_app(engine=lambda i: {})), text_image()).status_code == 413


def test_engine_unavailable_is_503():
    def boom(img):
        raise OcrUnavailable("sin tesseract")
    assert post(TestClient(create_app(engine=boom)), text_image()).status_code == 503


def test_requires_auth():
    r = TestClient(create_app()).post("/extract", files={"file": ("p.png", text_image(), "image/png")})
    assert r.status_code == 401
