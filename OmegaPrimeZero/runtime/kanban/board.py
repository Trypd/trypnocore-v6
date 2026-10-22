"""One mind's board. No worker mind."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class BoardError(RuntimeError):
    pass


class Board:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, title TEXT)")

    def add_card(self, title: str) -> int:
        cursor = self._db.execute("INSERT INTO cards (title) VALUES (?)", (title,))
        self._db.commit()
        return int(cursor.lastrowid)

    def spawn_worker(self) -> None:
        raise BoardError("no worker mind")

    def close(self) -> None:
        self._db.close()
