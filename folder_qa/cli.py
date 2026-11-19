"""Command line: index a folder or ask a question without the web UI.

  python -m folder_qa index ~/Desktop
  python -m folder_qa ask ~/Desktop "what is my notice period?"
"""
import argparse

from . import llm
from .index import index_folder
from .search import find_verified, search
from .store import connect


def main() -> None:
    p = argparse.ArgumentParser(prog="folder_qa")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("index"); i.add_argument("folder")
    a = sub.add_parser("ask"); a.add_argument("folder"); a.add_argument("question")
    args = p.parse_args()

    if args.cmd == "index":
        print(index_folder(args.folder, progress=print))
        return

    conn = connect(args.folder)
    verified, _ = find_verified(conn, args.question)
    if verified:
        print(f"VERIFIED (accepted {verified['accepts']}x): {verified['answer']}\n")
    hits = search(conn, args.question)
    sources = [{"path": h.path, "position": h.position, "text": h.text} for h in hits]
    ans = llm.answer(args.question, sources[:5]) if sources else None
    print(ans or "(search only — no model available)\n")
    for n, h in enumerate(hits, 1):
        print(f"[{n}] {h.path} (passage {h.position + 1}, score {h.score:.4f}, feedback {h.feedback:+.1f})")


if __name__ == "__main__":
    main()
