#!/bin/bash
# Double-click this file in Finder to start Folder Q&A.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: setting up (about a minute)..."
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi
./.venv/bin/streamlit run app.py
