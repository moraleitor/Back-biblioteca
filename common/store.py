"""Capa mínima de persistencia SQLite (cada microservicio tiene su propia base)."""
import os
import sqlite3
import threading
from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_path(service: str) -> str:
    return os.path.join(os.getenv("DATA_DIR", "data"), f"{service}.db")


class Db:
    def __init__(self, path: str, schema: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(schema)
            self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid

    def one(self, sql: str, params: tuple = ()):
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
