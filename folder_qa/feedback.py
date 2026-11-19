"""Record like / accept / flag votes and maintain the curated Q&A bank."""
import json

from .search import similarity
from .store import now


def record(conn, query: str, sources: list[dict], kind: str) -> None:
    for s in sources:
        conn.execute(
            "INSERT INTO votes(query, chunk_path, chunk_position, kind, created_at) VALUES (?,?,?,?,?)",
            (query, s["path"], s["position"], kind, now()),
        )
    conn.commit()


def accept_answer(conn, question: str, answer: str, sources: list[dict]) -> None:
    """Accepted answers go into the Q&A bank (or strengthen an existing similar entry)."""
    record(conn, question, sources, "accept")
    for row in conn.execute("SELECT id, question FROM qa_bank").fetchall():
        if similarity(question, row["question"]) >= 0.8:
            conn.execute("UPDATE qa_bank SET accepts = accepts + 1, answer=?, sources=?, updated_at=? "
                         "WHERE id=?", (answer, json.dumps(sources), now(), row["id"]))
            conn.commit()
            return
    conn.execute("INSERT INTO qa_bank(question, answer, sources, created_at, updated_at) "
                 "VALUES (?,?,?,?,?)", (question, answer, json.dumps(sources), now(), now()))
    conn.commit()


def flag_answer(conn, question: str, sources: list[dict], bank_id: int | None = None) -> None:
    record(conn, question, sources, "flag")
    if bank_id is not None:
        conn.execute("UPDATE qa_bank SET flags = flags + 1, updated_at=? WHERE id=?", (now(), bank_id))
        conn.commit()


def stats(conn) -> dict:
    q = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "files": q("SELECT COUNT(*) FROM files"),
        "chunks": q("SELECT COUNT(*) FROM chunks"),
        "likes": q("SELECT COUNT(*) FROM votes WHERE kind='like'"),
        "accepts": q("SELECT COUNT(*) FROM votes WHERE kind='accept'"),
        "flags": q("SELECT COUNT(*) FROM votes WHERE kind='flag'"),
        "verified": q("SELECT COUNT(*) FROM qa_bank WHERE accepts > flags"),
    }
