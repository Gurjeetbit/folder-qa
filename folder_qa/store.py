"""SQLite storage for chunks, feedback votes and the curated Q&A bank.

All app data lives in ~/.folder-qa/ (or FOLDER_QA_HOME). The folder you index
is only ever read, never modified.
"""
import os
import sqlite3
import time
from pathlib import Path

HOME = Path(os.environ.get("FOLDER_QA_HOME", Path.home() / ".folder-qa"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    indexed_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    chunk_path TEXT NOT NULL,
    chunk_position INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('like', 'accept', 'flag')),
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS qa_bank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL,
    accepts INTEGER NOT NULL DEFAULT 1,
    flags INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


def db_path_for(folder: str) -> Path:
    """One database per indexed folder, so Desktop and Documents stay separate."""
    safe = str(Path(folder).expanduser().resolve()).strip("/").replace("/", "__") or "root"
    HOME.mkdir(parents=True, exist_ok=True)
    return HOME / f"{safe}.sqlite3"


def connect(folder: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path_for(folder), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now() -> float:
    return time.time()
