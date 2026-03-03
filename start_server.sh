#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f index.html ]]; then
  echo "[ERROR] index.html not found. Run this script in score-viwer folder."
  exit 1
fi

echo "Open: http://127.0.0.1:8000"
python3 -m http.server 8000 --bind 127.0.0.1
