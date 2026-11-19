"""Folder Q&A — ask questions about any folder on your Mac.

Run:  streamlit run app.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from folder_qa import feedback, llm
from folder_qa.index import index_folder
from folder_qa.search import find_verified, search
from folder_qa.store import connect

st.set_page_config(page_title="Folder Q&A", page_icon=":mag:", layout="wide")

# ---------- Sidebar: choose and index a folder ----------
st.sidebar.title("Folder Q&A")
default = os.environ.get("FOLDER_QA_DEFAULT", str(Path.home() / "Desktop"))
folder = st.sidebar.text_input("Folder to search", value=st.session_state.get("folder", default))
st.session_state.folder = folder

if st.sidebar.button("Index / refresh folder", type="primary", use_container_width=True):
    status = st.sidebar.empty()
    try:
        result = index_folder(folder, progress=lambda m: status.caption(m))
        status.success(f"{result['files']} files, {result['chunks']} passages "
                       f"({result['updated']} updated, {result['removed']} removed)")
    except Exception as exc:
        status.error(str(exc))

st.sidebar.caption(f"Answer engine: **{llm.backend_name()}**")
st.sidebar.caption("Your folder is only read, never changed. Index and votes are stored in ~/.folder-qa/")

try:
    conn = connect(folder)
except Exception as exc:
    st.error(f"Can't open index: {exc}")
    st.stop()

s = feedback.stats(conn)
c = st.sidebar.columns(3)
c[0].metric("Files", s["files"])
c[1].metric("Accepted", s["accepts"])
c[2].metric("Verified Q&A", s["verified"])


def reveal(path: str) -> None:
    """Show the file in Finder (macOS). Does not modify it."""
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", path], check=False)


# ---------- Main: ask ----------
st.title("Ask your files")
if s["chunks"] == 0:
    st.info("Pick a folder in the sidebar and press **Index / refresh folder** first.")

with st.form("ask", clear_on_submit=False):
    q = st.text_input("Question", placeholder="e.g. What is my notice period in the BofA offer letter?")
    go = st.form_submit_button("Search")

if go and q.strip():
    hits = search(conn, q.strip(), k=6)
    sources = [{"path": h.path, "position": h.position, "text": h.text,
                "relevance": h.relevance, "feedback": h.feedback} for h in hits]
    verified, vsim = find_verified(conn, q.strip())
    st.session_state.result = {
        "q": q.strip(), "sources": sources,
        "answer": llm.answer(q.strip(), sources[:5]) if sources else None,
        "verified": dict(verified) if verified else None,
        "voted": False,
    }

res = st.session_state.get("result")
if res:
    q, sources = res["q"], res["sources"]
    short = lambda p: str(Path(p).relative_to(Path(folder).expanduser().resolve())) \
        if p.startswith(str(Path(folder).expanduser().resolve())) else p

    if res["verified"]:
        v = res["verified"]
        with st.container(border=True):
            st.markdown(f":green[**Verified answer**] · accepted {v['accepts']}× · "
                        f"for a similar question: _{v['question']}_")
            st.markdown(v["answer"])
            if st.button("This verified answer is wrong", key="flag_verified"):
                feedback.flag_answer(conn, q, json.loads(v["sources"]), bank_id=v["id"])
                st.toast("Flagged. It will drop out once flags outnumber accepts.")

    if not sources:
        st.warning("Nothing matched. Try different words, or re-index the folder.")
    else:
        st.subheader("Answer")
        if res["answer"]:
            st.markdown(res["answer"])
        else:
            st.caption("Search-only mode (no model running). Best passages below. "
                       "Install Ollama for written answers — see README.")

        b = st.columns([1, 1, 1, 5])
        top = sources[:5]
        if b[0].button("Like", disabled=res["voted"]):
            feedback.record(conn, q, top, "like"); res["voted"] = True; st.toast("Thanks — ranking updated.")
        if b[1].button("Accept", type="primary", disabled=res["voted"]):
            feedback.accept_answer(conn, q, res["answer"] or sources[0]["text"], top)
            res["voted"] = True; st.toast("Saved to your verified Q&A bank.")
        if b[2].button("Flag wrong", disabled=res["voted"]):
            feedback.flag_answer(conn, q, top); res["voted"] = True
            st.toast("Flagged — these passages will rank lower for similar questions.")

        st.subheader("Sources")
        for i, src in enumerate(sources, 1):
            with st.expander(f"[{i}] {short(src['path'])}  ·  passage {src['position'] + 1}"
                             + (f"  ·  feedback {src['feedback']:+.1f}" if src["feedback"] else "")):
                st.text(src["text"][:1500])
                cols = st.columns([1, 1, 1, 5])
                if cols[0].button("Helpful", key=f"like{i}"):
                    feedback.record(conn, q, [src], "like"); st.toast("Marked helpful.")
                if cols[1].button("Not relevant", key=f"flag{i}"):
                    feedback.record(conn, q, [src], "flag"); st.toast("Will rank lower next time.")
                if cols[2].button("Show in Finder", key=f"open{i}"):
                    reveal(src["path"])
