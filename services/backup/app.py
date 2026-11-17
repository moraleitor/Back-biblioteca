"""Servicio de respaldo: instantáneas de la biblioteca y restauración.

Habla con los servicios de biblioteca y notas usando el mismo token del usuario.
"""
import json

from fastapi import Depends, FastAPI, Header, HTTPException

from common import registry
from common.security import current_user_id
from common.store import Db, default_path, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  books INTEGER NOT NULL,
  pages INTEGER NOT NULL,
  highlights INTEGER NOT NULL,
  payload TEXT NOT NULL
);
"""


def create_app(db_path: str | None = None) -> FastAPI:
    db = Db(db_path or default_path("backup"), SCHEMA)
    app = FastAPI(title="Servicio de respaldo")

    async def call(service: str, method: str, path: str, authorization: str | None, **kw):
        try:
            async with registry.client(service) as c:
                r = await c.request(method, path, headers=registry.forward_headers(authorization), **kw)
        except Exception:
            raise HTTPException(503, f"El servicio {service} no responde")
        if r.status_code >= 400:
            raise HTTPException(502, f"Error en el servicio {service} ({r.status_code})")
        return r.json() if r.content else None

    def meta(row: dict) -> dict:
        return {k: row[k] for k in ("id", "created_at", "books", "pages", "highlights")}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "backup"}

    @app.post("/snapshots", status_code=201)
    async def create_snapshot(uid: int = Depends(current_user_id), authorization: str | None = Header(default=None)):
        library = await call("library", "GET", "/export", authorization)
        highlights = await call("notes", "GET", "/highlights", authorization)
        pages = sum(len(b["pages"]) for b in library["books"])
        payload = {"version": 1, "created_at": now(), "books": library["books"], "highlights": highlights}
        sid = db.execute(
            "INSERT INTO snapshots (user_id, created_at, books, pages, highlights, payload) VALUES (?,?,?,?,?,?)",
            (uid, payload["created_at"], len(library["books"]), pages, len(highlights), json.dumps(payload)),
        )
        return meta(db.one("SELECT * FROM snapshots WHERE id = ?", (sid,)))

    @app.get("/snapshots")
    def list_snapshots(uid: int = Depends(current_user_id)):
        return [meta(r) for r in db.all("SELECT * FROM snapshots WHERE user_id = ? ORDER BY id DESC", (uid,))]

    def own(sid: int, uid: int) -> dict:
        row = db.one("SELECT * FROM snapshots WHERE id = ? AND user_id = ?", (sid, uid))
        if not row:
            raise HTTPException(404, "Respaldo no encontrado")
        return row

    @app.get("/snapshots/{sid}/download")
    def download(sid: int, uid: int = Depends(current_user_id)):
        return json.loads(own(sid, uid)["payload"])

    @app.delete("/snapshots/{sid}", status_code=204)
    def delete_snapshot(sid: int, uid: int = Depends(current_user_id)):
        own(sid, uid)
        db.execute("DELETE FROM snapshots WHERE id = ?", (sid,))

    @app.post("/snapshots/{sid}/restore")
    async def restore(sid: int, uid: int = Depends(current_user_id), authorization: str | None = Header(default=None)):
        data = json.loads(own(sid, uid)["payload"])
        page_map: dict[int, int] = {}
        books = pages = 0
        for b in data["books"]:
            nb = await call("library", "POST", "/books", authorization,
                            json={"title": f"{b['title']} (restaurado)", "author": b.get("author", "")})
            books += 1
            for p in b["pages"]:
                np_ = await call("library", "POST", f"/books/{nb['id']}/pages", authorization,
                                 json={"text": p["text"], "page_number": p["page_number"], "source": "restore"})
                page_map[p["id"]] = np_["id"]
                pages += 1
        restored_hl = 0
        for h in data["highlights"]:
            new_page = page_map.get(h["page_id"])
            if new_page is None:
                continue
            await call("notes", "POST", f"/pages/{new_page}/highlights", authorization,
                       json={"start": h["start"], "end": h["end"], "color": h["color"], "note": h["note"]})
            restored_hl += 1
        return {"books": books, "pages": pages, "highlights": restored_hl}

    return app
