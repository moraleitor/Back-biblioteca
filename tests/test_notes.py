from tests.test_library import new_book
from tests.conftest import make_user


def page(gw, auth, text="El respaldo automático protege tus notas."):
    book = new_book(gw, auth)
    return gw.post(f"/api/library/books/{book['id']}/pages", json={"text": text}, headers=auth).json()


def test_highlight_lifecycle(gw, auth):
    p = page(gw, auth)
    r = gw.post(f"/api/notes/pages/{p['id']}/highlights", json={"start": 3, "end": 11, "color": "green", "note": "clave"}, headers=auth)
    assert r.status_code == 201
    h = r.json()
    assert h["snippet"] == p["text"][3:11] and h["color"] == "green"
    assert gw.patch(f"/api/notes/highlights/{h['id']}", json={"note": "editada"}, headers=auth).json()["note"] == "editada"
    assert len(gw.get(f"/api/notes/pages/{p['id']}/highlights", headers=auth).json()) == 1
    assert gw.delete(f"/api/notes/highlights/{h['id']}", headers=auth).status_code == 204
    assert gw.get("/api/notes/highlights", headers=auth).json() == []


def test_highlight_bounds_and_color(gw, auth):
    p = page(gw, auth)
    url = f"/api/notes/pages/{p['id']}/highlights"
    assert gw.post(url, json={"start": 5, "end": 5}, headers=auth).status_code in (422,)
    assert gw.post(url, json={"start": 0, "end": 9999}, headers=auth).status_code == 422
    assert gw.post(url, json={"start": 0, "end": 4, "color": "rojo"}, headers=auth).status_code == 422
    assert gw.post(url, json={"start": 8, "end": 4}, headers=auth).status_code == 422


def test_cannot_highlight_foreign_or_missing_page(gw, auth):
    p = page(gw, auth)
    other = make_user(gw, "luis@correo.com")
    assert gw.post(f"/api/notes/pages/{p['id']}/highlights", json={"start": 0, "end": 3}, headers=other).status_code == 404
    assert gw.post("/api/notes/pages/9999/highlights", json={"start": 0, "end": 3}, headers=auth).status_code == 404


def test_other_user_cannot_touch_highlight(gw, auth):
    p = page(gw, auth)
    h = gw.post(f"/api/notes/pages/{p['id']}/highlights", json={"start": 0, "end": 3}, headers=auth).json()
    other = make_user(gw, "luis@correo.com")
    assert gw.delete(f"/api/notes/highlights/{h['id']}", headers=other).status_code == 404
    assert gw.get("/api/notes/highlights", headers=other).json() == []
