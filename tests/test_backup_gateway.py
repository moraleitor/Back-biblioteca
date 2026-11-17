import pytest

from tests.conftest import HAS_TESSERACT, make_user, text_image
from tests.test_library import new_book


def seed(gw, auth):
    book = new_book(gw, auth)
    p = gw.post(f"/api/library/books/{book['id']}/pages", json={"text": "Texto para respaldar y restaurar."}, headers=auth).json()
    gw.post(f"/api/notes/pages/{p['id']}/highlights", json={"start": 0, "end": 5, "note": "n"}, headers=auth)
    return book, p


def test_snapshot_and_restore(gw, auth):
    seed(gw, auth)
    snap = gw.post("/api/backup/snapshots", headers=auth)
    assert snap.status_code == 201
    assert (snap.json()["books"], snap.json()["pages"], snap.json()["highlights"]) == (1, 1, 1)
    dl = gw.get(f"/api/backup/snapshots/{snap.json()['id']}/download", headers=auth).json()
    assert dl["books"][0]["pages"][0]["text"].startswith("Texto")
    res = gw.post(f"/api/backup/snapshots/{snap.json()['id']}/restore", headers=auth).json()
    assert res == {"books": 1, "pages": 1, "highlights": 1}
    titles = [b["title"] for b in gw.get("/api/library/books", headers=auth).json()]
    assert any(t.endswith("(restaurado)") for t in titles)


def test_snapshots_are_private(gw, auth):
    seed(gw, auth)
    sid = gw.post("/api/backup/snapshots", headers=auth).json()["id"]
    other = make_user(gw, "luis@correo.com")
    assert gw.get(f"/api/backup/snapshots/{sid}/download", headers=other).status_code == 404
    assert gw.get("/api/backup/snapshots", headers=other).json() == []
    assert gw.delete(f"/api/backup/snapshots/{sid}", headers=auth).status_code == 204


def test_gateway_health_and_unknown_service(gw):
    h = gw.get("/health").json()
    assert h["status"] == "ok" and set(h["services"]) == {"auth", "library", "notes", "ocr", "ai", "backup"}
    assert gw.get("/api/nada/x", headers={"Authorization": "Bearer x"}).status_code in (401, 404)


def test_gateway_blocks_without_token_but_allows_public_routes(gw):
    assert gw.get("/api/library/books").status_code == 401
    assert gw.post("/api/auth/login", json={"email": "x@y.co", "password": "12345678"}).status_code == 401


@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract no instalado")
def test_scan_flow_photo_to_page(gw, auth):
    book = new_book(gw, auth)
    r = gw.post("/api/scan", headers=auth, data={"book_id": book["id"], "page_number": 12},
                files={"file": ("foto.png", text_image("Hello World"), "image/png")})
    assert r.status_code == 201, r.text
    page = r.json()["page"]
    assert page["page_number"] == 12 and page["source"] == "ocr" and "hello" in page["text"].lower()
    # el texto queda editable y se puede subrayar y resumir
    assert gw.put(f"/api/library/pages/{page['id']}", json={"text": "Hello corregido World"}, headers=auth).status_code == 200
    assert gw.post("/api/ai/summary", json={"text": "Una frase. Otra frase distinta."}, headers=auth).status_code == 200


def test_scan_rejects_bad_inputs(gw, auth):
    book = new_book(gw, auth)
    bad = gw.post("/api/scan", headers=auth, data={"book_id": book["id"]}, files={"file": ("a.txt", b"hola", "text/plain")})
    assert bad.status_code == 415
    missing_book = gw.post("/api/scan", headers=auth, data={"book_id": 999},
                           files={"file": ("a.png", text_image("Hello World"), "image/png")})
    assert missing_book.status_code == 404
    assert gw.post("/api/scan", data={"book_id": book["id"]}, files={"file": ("a.png", text_image(), "image/png")}).status_code == 401


def test_scan_with_blank_image_reports_no_text(gw, auth):
    from PIL import Image
    import io
    buf = io.BytesIO(); Image.new("RGB", (600, 300), "white").save(buf, "PNG")
    book = new_book(gw, auth)
    r = gw.post("/api/scan", headers=auth, data={"book_id": book["id"]}, files={"file": ("b.png", buf.getvalue(), "image/png")})
    assert r.status_code == 422
