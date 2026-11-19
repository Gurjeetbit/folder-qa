"""Incremental indexer: walks a folder, extracts text, chunks it, stores it.

Only changed or new files are re-read; deleted files are dropped from the index.
The folder itself is opened read-only.
"""
from array import array
from pathlib import Path
from typing import Callable

from . import llm
from .extract import SUPPORTED, chunk_text, extract_text
from .store import connect, now

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "Library",
             ".Trash", "Applications", ".cache"}
MAX_BYTES = 25 * 1024 * 1024


def iter_files(root: Path):
    for p in root.rglob("*"):
        if any(part.startswith(".") or part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            try:
                if p.stat().st_size <= MAX_BYTES:
                    yield p
            except OSError:
                continue


def index_folder(folder: str, progress: Callable[[str], None] = lambda m: None) -> dict:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a folder: {root}")
    conn = connect(str(root))
    seen, added, skipped = set(), 0, 0
    use_embeddings = llm.ollama_available()

    for path in iter_files(root):
        key = str(path)
        seen.add(key)
        st = path.stat()
        row = conn.execute("SELECT mtime, size FROM files WHERE path=?", (key,)).fetchone()
        if row and row["mtime"] == st.st_mtime and row["size"] == st.st_size:
            skipped += 1
            continue
        progress(f"Reading {path.relative_to(root)}")
        text = extract_text(path)
        chunks = chunk_text(text) if text.strip() else []
        vectors = llm.embed(chunks) if (chunks and use_embeddings) else None
        conn.execute("DELETE FROM chunks WHERE path=?", (key,))
        for i, c in enumerate(chunks):
            blob = array("f", vectors[i]).tobytes() if vectors else None
            conn.execute("INSERT INTO chunks(path, position, text, embedding) VALUES (?,?,?,?)",
                         (key, i, c, blob))
        conn.execute("INSERT OR REPLACE INTO files(path, mtime, size, indexed_at) VALUES (?,?,?,?)",
                     (key, st.st_mtime, st.st_size, now()))
        added += 1
        if added % 20 == 0:
            conn.commit()

    removed = 0
    for row in conn.execute("SELECT path FROM files").fetchall():
        if row["path"] not in seen:
            conn.execute("DELETE FROM chunks WHERE path=?", (row["path"],))
            conn.execute("DELETE FROM files WHERE path=?", (row["path"],))
            removed += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    conn.close()
    return {"files": files, "chunks": total, "updated": added, "unchanged": skipped,
            "removed": removed, "embeddings": use_embeddings}
