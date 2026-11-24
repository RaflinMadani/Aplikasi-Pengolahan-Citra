#!/usr/bin/env bash
# Menjalankan dashboard (Linux/macOS):  bash run.sh
set -e
cd "$(dirname "$0")"
if [ ! -d venv ]; then python3 -m venv venv; fi
source venv/bin/activate
pip install -q -r requirements.txt
python app.py
