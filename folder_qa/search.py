"""Hybrid search with feedback-boosted ranking.

score = RRF(keyword rank, semantic rank) x feedback multiplier

Feedback multiplier: accepts count most, likes a little, flags push down hard.
Votes decay over time (half-life 90 days) and count double when they were cast
on a similar question. tanh() caps the effect, so votes nudge ranking but never
override relevance.
"""
import math
import re
from array import array
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from . import llm
from .store import now

WEIGHTS = {"accept": 2.0, "like": 1.0, "flag": -3.0}
HALF_LIFE_DAYS = 90
RRF_K = 60
_TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("a an the of to in on for and or is are was were be what how why when where which who "
           "do does did i my me you your it this that with by from as at can".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP]


def similarity(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


@dataclass
class Hit:
    path: str
    position: int
    text: str
    relevance: float
    feedback: float
    score: float


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def feedback_scores(conn, query: str) -> dict[tuple[str, int], float]:
    scores: dict[tuple[str, int], float] = {}
    t = now()
    for v in conn.execute("SELECT query, chunk_path, chunk_position, kind, created_at FROM votes"):
        age_days = (t - v["created_at"]) / 86400
        w = WEIGHTS[v["kind"]] * 0.5 ** (age_days / HALF_LIFE_DAYS)
        if similarity(query, v["query"]) >= 0.3:
            w *= 2
        key = (v["chunk_path"], v["chunk_position"])
        scores[key] = scores.get(key, 0.0) + w
    return scores


def search(conn, query: str, k: int = 6) -> list[Hit]:
    rows = conn.execute("SELECT path, position, text, embedding FROM chunks").fetchall()
    if not rows:
        return []
    q_tokens = tokens(query) or query.lower().split()

    bm25 = BM25Okapi([tokens(r["text"]) or ["_"] for r in rows])
    kw = bm25.get_scores(q_tokens)
    kw_rank = {i: r for r, i in enumerate(sorted(range(len(rows)), key=lambda i: -kw[i]))}

    sem_rank = {}
    if any(r["embedding"] for r in rows):
        qv = llm.embed([query])
        if qv:
            sims = []
            for i, r in enumerate(rows):
                if r["embedding"]:
                    sims.append((i, _cosine(qv[0], array("f", r["embedding"]))))
            sem_rank = {i: rank for rank, (i, _) in enumerate(sorted(sims, key=lambda x: -x[1]))}

    fb = feedback_scores(conn, query)
    hits = []
    for i, r in enumerate(rows):
        if kw[i] <= 0 and i not in sem_rank:
            continue
        rel = 1 / (RRF_K + kw_rank[i])
        if i in sem_rank:
            rel += 1 / (RRF_K + sem_rank[i])
        f = fb.get((r["path"], r["position"]), 0.0)
        mult = 1 + 0.5 * math.tanh(f / 3)
        hits.append(Hit(r["path"], r["position"], r["text"], rel, f, rel * mult))
    hits.sort(key=lambda h: -h.score)
    return hits[:k]


def find_verified(conn, query: str, threshold: float = 0.5):
    """Return the best matching curated Q&A entry, if one is close enough and trusted."""
    best, best_sim = None, 0.0
    for row in conn.execute("SELECT * FROM qa_bank WHERE accepts > flags"):
        s = similarity(query, row["question"])
        if s > best_sim:
            best, best_sim = row, s
    return (best, best_sim) if best is not None and best_sim >= threshold else (None, 0.0)
