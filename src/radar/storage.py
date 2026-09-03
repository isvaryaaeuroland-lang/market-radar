"""Snapshot persistence: a JSON file per crawl (human-inspectable, easy to
demo) plus a thin SQLite index used only to answer "what's the latest /
previous snapshot for domain X" and to hold the watchlist. Not a general
purpose database — kept intentionally small (TRD §5)."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .schemas import CompanyProfile, CrawlSnapshot

DB_PATH = settings.data_dir / "radar.db"
SNAPSHOTS_DIR = settings.data_dir / "snapshots"


def _safe_domain_dirname(domain: str) -> str:
    return re.sub(r"[^a-zA-Z0-9.\-]", "_", domain.replace("https://", "").replace("http://", ""))


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                taken_at TEXT NOT NULL,
                path TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS watchlist (
                domain TEXT PRIMARY KEY,
                is_own_company INTEGER NOT NULL DEFAULT 0,
                added_at TEXT NOT NULL
            )"""
        )


def save_snapshot(snapshot: CrawlSnapshot) -> Path:
    init_db()
    domain_dir = SNAPSHOTS_DIR / _safe_domain_dirname(snapshot.profile.domain)
    domain_dir.mkdir(parents=True, exist_ok=True)

    file_path = domain_dir / f"{snapshot.id}.json"
    file_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO snapshots (id, domain, taken_at, path) VALUES (?, ?, ?, ?)",
            (snapshot.id, snapshot.profile.domain, snapshot.profile.extracted_at.isoformat(), str(file_path)),
        )
    return file_path


def _load_snapshot(path: str) -> CrawlSnapshot:
    return CrawlSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))


def get_latest_snapshot(domain: str) -> CrawlSnapshot | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT path FROM snapshots WHERE domain = ? ORDER BY taken_at DESC LIMIT 1", (domain,)
        ).fetchone()
    return _load_snapshot(row["path"]) if row else None


def make_snapshot_id(domain: str, at: datetime | None = None) -> str:
    at = at or datetime.now(timezone.utc)
    return f"{_safe_domain_dirname(domain)}__{at.strftime('%Y%m%dT%H%M%SZ')}"


def add_to_watchlist(domain: str, is_own_company: bool = False) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO watchlist (domain, is_own_company, added_at) VALUES (?, ?, ?)",
            (domain, int(is_own_company), datetime.now(timezone.utc).isoformat()),
        )


def remove_from_watchlist(domain: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE domain = ?", (domain,))


def list_watchlist() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT domain, is_own_company, added_at FROM watchlist ORDER BY added_at").fetchall()
    return [dict(row) for row in rows]
