# Folder Q&A

Ask questions about any folder on your Mac, such as Desktop or Documents, and get answers that cite the exact file. You don't have to open files one by one.

Every answer has **Like**, **Accept** and **Flag wrong** buttons. Your votes change how results rank next time, and accepted answers build a personal bank of **verified Q&A**.

> Your folder is only **read**. Nothing in it is changed, moved or deleted. The index and your votes live in `~/.folder-qa/`.

```
Your folder ──► Index (text from PDF, Word, PowerPoint, Excel, txt, md…, split into passages)
                    │
Question ──► Hybrid search (keywords + meaning) ──► Rerank with your votes
                    │
             Answer with [1][2] citations ──► Like / Accept / Flag
                    │                                   │
             Verified Q&A bank ◄──── accepted ──────────┘
```

## Quick start (Mac)

1. Install Python 3.10 or newer from python.org, if it isn't installed already. Check with `python3 --version`.
2. Download this repo (green **Code** button → **Download ZIP**) and unzip it.
3. Open Terminal in the folder and run:

```bash
chmod +x start.command   # once
./start.command          # or double-click start.command in Finder
```

4. Your browser opens. The folder box is preset to `~/Desktop`. Change it if you want another folder, then press **Index / refresh folder** and ask a question.

The first time the app reads a folder, macOS may ask Terminal for permission to access it. Click **Allow**.

## Written answers (optional, recommended)

Without a language model, the app still finds and ranks the best passages ("search only" mode). To get written, cited answers, pick one option:

**A. Private and free: Ollama (runs on your Mac, nothing leaves it)**

```bash
brew install ollama        # or download from ollama.com
ollama serve &             # start it
ollama pull llama3.1       # answer model (~4.7 GB)
ollama pull nomic-embed-text   # adds meaning-based search
```

Re-index the folder after pulling `nomic-embed-text` so passages get embeddings.

**B. Anthropic API.** Use this only for files you're comfortable sending to an API.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./start.command
```

## How the feedback ranking works

| Signal | Effect |
|---|---|
| **Accept** | +2 to each source passage; the answer is saved to the verified Q&A bank |
| **Like** / **Helpful** | +1 |
| **Flag wrong** / **Not relevant** | −3, so the passage ranks lower |

- A vote counts **double** when it was cast on a similar question.
- Votes **decay** with a half-life of 90 days, so old opinions fade.
- The boost is capped with `tanh`, so votes nudge relevance but never override it. A popular passage can't outrank one that actually matches.
- If a new question closely matches an accepted one, the **verified answer** shows first. It drops out once flags outnumber accepts.

## Command line

```bash
.venv/bin/python -m folder_qa index ~/Desktop
.venv/bin/python -m folder_qa ask ~/Desktop "what is my notice period?"
```

## Settings (environment variables)

| Variable | Default |
|---|---|
| `FOLDER_QA_DEFAULT` | `~/Desktop` |
| `FOLDER_QA_MODEL` | `llama3.1` (Ollama) |
| `FOLDER_QA_EMBED_MODEL` | `nomic-embed-text` |
| `FOLDER_QA_HOME` | `~/.folder-qa` |

Hidden folders, `node_modules`, `.git` and `Library` are skipped, along with files over 25 MB.

## Project layout

```
app.py                 Streamlit web UI
folder_qa/extract.py   Text extraction and chunking
folder_qa/index.py     Incremental indexer (only changed files are re-read)
folder_qa/search.py    BM25 + embeddings, fused with RRF, then boosted by feedback
folder_qa/feedback.py  Votes and the verified Q&A bank
folder_qa/llm.py       Ollama / Anthropic / search-only backends
folder_qa/store.py     SQLite storage
```
