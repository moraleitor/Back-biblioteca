from tests.conftest import make_user


def new_book(gw, auth, title="Cien años de soledad"):
    r = gw.post("/api/library/books", json={"title": title, "author": "García Márquez"}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_requires_token(gw):
    assert gw.get("/api/library/books").status_code == 401
    assert gw.get("/api/library/books", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_book_and_pages_crud(gw, auth):
    book = new_book(gw, auth)
    p1 = gw.post(f"/api/library/books/{book['id']}/pages", json={"text": "Primera página"}, headers=auth).json()
    p2 = gw.post(f"/api/library/books/{book['id']}/pages", json={"text": "Segunda página"}, headers=auth).json()
    assert (p1["page_number"], p2["page_number"]) == (1, 2)
    upd = gw.put(f"/api/library/pages/{p1['id']}", json={"text": "Texto corregido"}, headers=auth).json()
    assert upd["text"] == "Texto corregido"
    listing = gw.get("/api/library/books", headers=auth).json()
    assert listing[0]["page_count"] == 2
    assert gw.delete(f"/api/library/pages/{p2['id']}", headers=auth).status_code == 204
    assert len(gw.get(f"/api/library/books/{book['id']}/pages", headers=auth).json()) == 1
    assert gw.delete(f"/api/library/books/{book['id']}", headers=auth).status_code == 204
    assert gw.get(f"/api/library/books/{book['id']}", headers=auth).status_code == 404


def test_duplicate_page_number(gw, auth):
    book = new_book(gw, auth)
    url = f"/api/library/books/{book['id']}/pages"
    assert gw.post(url, json={"text": "a", "page_number": 7}, headers=auth).status_code == 201
    assert gw.post(url, json={"text": "b", "page_number": 7}, headers=auth).status_code == 409


def test_users_are_isolated(gw, auth):
    book = new_book(gw, auth)
    other = make_user(gw, "luis@correo.com")
    assert gw.get(f"/api/library/books/{book['id']}", headers=other).status_code == 404
    assert gw.get("/api/library/books", headers=other).json() == []
    assert gw.post(f"/api/library/books/{book['id']}/pages", json={"text": "x"}, headers=other).status_code == 404


def test_search(gw, auth):
    book = new_book(gw, auth)
    gw.post(f"/api/library/books/{book['id']}/pages", json={"text": "Muchos años después, frente al pelotón de fusilamiento"}, headers=auth)
    hits = gw.get("/api/library/search", params={"q": "PELOTÓN"}, headers=auth).json()
    assert len(hits) == 1 and "pelotón" in hits[0]["snippet"].lower() and hits[0]["title"] == book["title"]
    assert gw.get("/api/library/search", params={"q": "a"}, headers=auth).status_code == 422


def test_validation(gw, auth):
    assert gw.post("/api/library/books", json={"title": ""}, headers=auth).status_code == 422
    book = new_book(gw, auth)
    assert gw.post(f"/api/library/books/{book['id']}/pages", json={"text": ""}, headers=auth).status_code == 422
