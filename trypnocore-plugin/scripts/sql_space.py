"""Dependency-free SQLite memory pools with the core MettaSpace interface."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

MAX_ATOMS = 300
POOL_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


def check_pool(pool: str) -> str:
    pool = (pool or "default").strip().lower()
    if not POOL_RE.fullmatch(pool):
        raise ValueError(f"bad pool name: {pool!r}")
    return pool


def data_home() -> Path:
    root = os.environ.get("TRYP_DATA_HOME", str(Path.home() / ".local" / "share" / "trypnocore"))
    return Path(root) / "metta"


class SqlSpace:
    """One durable SQLite pool. Every write is committed immediately."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS atoms ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "claim TEXT NOT NULL, pointer TEXT NOT NULL UNIQUE, evidence TEXT NOT NULL)"
            )

    @classmethod
    def for_pool(cls, pool: str) -> "SqlSpace":
        return cls(data_home() / f"pool-{check_pool(pool)}.sqlite3")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=15)

    def claims(self) -> list[str]:
        with self._connect() as con:
            return [row[0] for row in con.execute("SELECT claim FROM atoms ORDER BY id")]

    def count(self) -> int:
        with self._connect() as con:
            return con.execute("SELECT count(*) FROM atoms").fetchone()[0]

    def exists(self, pointer: str) -> bool:
        with self._connect() as con:
            return con.execute("SELECT 1 FROM atoms WHERE pointer = ?", (pointer,)).fetchone() is not None

    def remember(self, proof) -> None:
        claim = proof.claim.strip()
        if not claim or claim.startswith("saw:") or claim.startswith("heard:"):
            return
        with self._connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO atoms (claim, pointer, evidence) VALUES (?, ?, ?)",
                (claim, proof.pointer, proof.evidence),
            )
            con.execute(
                "DELETE FROM atoms WHERE id NOT IN (SELECT id FROM atoms ORDER BY id DESC LIMIT ?)",
                (MAX_ATOMS,),
            )
