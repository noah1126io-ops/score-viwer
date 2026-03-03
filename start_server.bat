@echo off
setlocal
cd /d "%~dp0"

echo [Score Viewer] project dir: %CD%
if not exist index.html (
  echo [ERROR] index.html not found. Please open this BAT inside score-viwer folder.
  pause
  exit /b 1
)

start "" http://127.0.0.1:8000
python -m http.server 8000 --bind 127.0.0.1
