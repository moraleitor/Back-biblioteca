"""Servicio de notas y subrayados. Valida las páginas consultando al servicio de biblioteca."""
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from common import registry
from common.security import current_user_id
from common.store import Db, default_path, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS highlights (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  page_id INTEGER NOT NULL,
  start INTEGER NOT NULL,
  "end" INTEGER NOT NULL,
  color TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  snippet TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hl_page ON highlights(page_id);
"""
COLORS = "yellow|green|blue|pink"


class HighlightIn(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    color: str = Field(default="yellow", pattern=f"^({COLORS})$")
    note: str = Field(default="", max_length=1000)


class NoteUpdate(BaseModel):
    note: str = Field(max_length=1000)


def create_app(db_path: str | None = None) -> FastAPI:
    db = Db(db_path or default_path("notes"), SCHEMA)
    app = FastAPI(title="Servicio de notas")

    async def fetch_page(page_id: int, authorization: str | None) -> dict:
        try:
            async with registry.client("library") as c:
                r = await c.get(f"/pages/{page_id}", headers=registry.forward_headers(authorization))
        except Exception:
            raise HTTPException(503, "El servicio de biblioteca no responde")
        if r.status_code == 404:
            raise HTTPException(404, "Página no encontrada")
        if r.status_code != 200:
            raise HTTPException(r.status_code, "No se pudo validar la página")
        return r.json()

    def out(row: dict) -> dict:
        return {"id": row["id"], "page_id": row["page_id"], "start": row["start"], "end": row["end"],
                "color": row["color"], "note": row["note"], "snippet": row["snippet"], "created_at": row["created_at"]}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "notes"}

    @app.post("/pages/{page_id}/highlights", status_code=201)
    async def create_highlight(page_id: int, body: HighlightIn, uid: int = Depends(current_user_id),
                               authorization: str | None = Header(default=None)):
        page = await fetch_page(page_id, authorization)
        if body.end <= body.start:
            raise HTTPException(422, "El fin del subrayado debe ser mayor que el inicio")
        if body.end > len(page["text"]):
            raise HTTPException(422, "El subrayado se sale del texto de la página")
        hid = db.execute(
            'INSERT INTO highlights (user_id, page_id, start, "end", color, note, snippet, created_at) VALUES (?,?,?,?,?,?,?,?)',
            (uid, page_id, body.start, body.end, body.color, body.note, page["text"][body.start : body.end], now()),
        )
        return out(db.one("SELECT * FROM highlights WHERE id = ?", (hid,)))

    @app.get("/pages/{page_id}/highlights")
    def page_highlights(page_id: int, uid: int = Depends(current_user_id)):
        rows = db.all('SELECT * FROM highlights WHERE page_id = ? AND user_id = ? ORDER BY start', (page_id, uid))
        return [out(r) for r in rows]

    @app.get("/highlights")
    def all_highlights(page_id: int | None = Query(default=None), uid: int = Depends(current_user_id)):
        if page_id is not None:
            rows = db.all("SELECT * FROM highlights WHERE user_id = ? AND page_id = ? ORDER BY id", (uid, page_id))
        else:
            rows = db.all("SELECT * FROM highlights WHERE user_id = ? ORDER BY id", (uid,))
        return [out(r) for r in rows]

    @app.patch("/highlights/{hid}")
    def update_note(hid: int, body: NoteUpdate, uid: int = Depends(current_user_id)):
        if not db.one("SELECT id FROM highlights WHERE id = ? AND user_id = ?", (hid, uid)):
            raise HTTPException(404, "Subrayado no encontrado")
        db.execute("UPDATE highlights SET note = ? WHERE id = ?", (body.note, hid))
        return out(db.one("SELECT * FROM highlights WHERE id = ?", (hid,)))

    @app.delete("/highlights/{hid}", status_code=204)
    def delete_highlight(hid: int, uid: int = Depends(current_user_id)):
        if not db.one("SELECT id FROM highlights WHERE id = ? AND user_id = ?", (hid, uid)):
            raise HTTPException(404, "Subrayado no encontrado")
        db.execute("DELETE FROM highlights WHERE id = ?", (hid,))

    return app
