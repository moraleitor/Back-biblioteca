"""Servicio de biblioteca: libros y páginas con texto editable, más búsqueda."""
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from common.security import current_user_id
from common.store import Db, default_path, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  author TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  page_number INTEGER NOT NULL,
  text TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (book_id, page_number)
);
CREATE INDEX IF NOT EXISTS idx_books_user ON books(user_id);
CREATE INDEX IF NOT EXISTS idx_pages_book ON pages(book_id);
"""
MAX_TEXT = 50_000


class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(default="", max_length=120)


class PageIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    page_number: int | None = Field(default=None, ge=1)
    source: str = Field(default="manual", pattern="^(manual|ocr|restore)$")


class PageUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)


def create_app(db_path: str | None = None) -> FastAPI:
    db = Db(db_path or default_path("library"), SCHEMA)
    app = FastAPI(title="Servicio de biblioteca")

    def own_book(book_id: int, user_id: int) -> dict:
        book = db.one("SELECT * FROM books WHERE id = ? AND user_id = ?", (book_id, user_id))
        if not book:
            raise HTTPException(404, "Libro no encontrado")
        return book

    def own_page(page_id: int, user_id: int) -> dict:
        page = db.one("SELECT * FROM pages WHERE id = ? AND user_id = ?", (page_id, user_id))
        if not page:
            raise HTTPException(404, "Página no encontrada")
        return page

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "library"}

    # ---- libros ----
    @app.post("/books", status_code=201)
    def create_book(body: BookIn, uid: int = Depends(current_user_id)):
        bid = db.execute(
            "INSERT INTO books (user_id, title, author, created_at) VALUES (?,?,?,?)",
            (uid, body.title.strip(), body.author.strip(), now()),
        )
        return {**own_book(bid, uid), "page_count": 0}

    @app.get("/books")
    def list_books(uid: int = Depends(current_user_id)):
        return db.all(
            """SELECT b.*, COUNT(p.id) AS page_count FROM books b
               LEFT JOIN pages p ON p.book_id = b.id WHERE b.user_id = ?
               GROUP BY b.id ORDER BY b.id DESC""",
            (uid,),
        )

    @app.get("/books/{book_id}")
    def get_book(book_id: int, uid: int = Depends(current_user_id)):
        book = own_book(book_id, uid)
        book["page_count"] = db.one("SELECT COUNT(*) AS n FROM pages WHERE book_id = ?", (book_id,))["n"]
        return book

    @app.delete("/books/{book_id}", status_code=204)
    def delete_book(book_id: int, uid: int = Depends(current_user_id)):
        own_book(book_id, uid)
        db.execute("DELETE FROM pages WHERE book_id = ?", (book_id,))
        db.execute("DELETE FROM books WHERE id = ?", (book_id,))

    # ---- páginas ----
    @app.post("/books/{book_id}/pages", status_code=201)
    def create_page(book_id: int, body: PageIn, uid: int = Depends(current_user_id)):
        own_book(book_id, uid)
        number = body.page_number
        if number is None:
            number = db.one("SELECT COALESCE(MAX(page_number), 0) + 1 AS n FROM pages WHERE book_id = ?", (book_id,))["n"]
        stamp = now()
        try:
            pid = db.execute(
                "INSERT INTO pages (book_id, user_id, page_number, text, source, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (book_id, uid, number, body.text, body.source, stamp, stamp),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, f"La página {number} ya existe en este libro")
        return own_page(pid, uid)

    @app.get("/books/{book_id}/pages")
    def list_pages(book_id: int, uid: int = Depends(current_user_id)):
        own_book(book_id, uid)
        return db.all("SELECT * FROM pages WHERE book_id = ? ORDER BY page_number", (book_id,))

    @app.get("/pages/{page_id}")
    def get_page(page_id: int, uid: int = Depends(current_user_id)):
        return own_page(page_id, uid)

    @app.put("/pages/{page_id}")
    def update_page(page_id: int, body: PageUpdate, uid: int = Depends(current_user_id)):
        own_page(page_id, uid)
        db.execute("UPDATE pages SET text = ?, updated_at = ? WHERE id = ?", (body.text, now(), page_id))
        return own_page(page_id, uid)

    @app.delete("/pages/{page_id}", status_code=204)
    def delete_page(page_id: int, uid: int = Depends(current_user_id)):
        own_page(page_id, uid)
        db.execute("DELETE FROM pages WHERE id = ?", (page_id,))

    # ---- búsqueda y exportación ----
    @app.get("/search")
    def search(q: str = Query(min_length=2, max_length=100), uid: int = Depends(current_user_id)):
        like = f"%{q.lower()}%"
        rows = db.all(
            """SELECT p.id AS page_id, p.page_number, p.text, b.id AS book_id, b.title
               FROM pages p JOIN books b ON b.id = p.book_id
               WHERE p.user_id = ? AND LOWER(p.text) LIKE ? ORDER BY b.id, p.page_number LIMIT 50""",
            (uid, like),
        )
        results = []
        for r in rows:
            pos = r["text"].lower().find(q.lower())
            start = max(0, pos - 40)
            snippet = r["text"][start : pos + len(q) + 40].replace("\n", " ")
            results.append({"book_id": r["book_id"], "title": r["title"], "page_id": r["page_id"],
                            "page_number": r["page_number"], "snippet": snippet})
        return results

    @app.get("/export")
    def export(uid: int = Depends(current_user_id)):
        books = db.all("SELECT * FROM books WHERE user_id = ? ORDER BY id", (uid,))
        for b in books:
            b["pages"] = db.all("SELECT * FROM pages WHERE book_id = ? ORDER BY page_number", (b["id"],))
        return {"books": books}

    return app
