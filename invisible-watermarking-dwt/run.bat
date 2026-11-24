@echo off
rem Menjalankan dashboard (Windows): klik dua kali atau jalankan run.bat
cd /d %~dp0
if not exist venv ( python -m venv venv )
call venv\Scripts\activate
pip install -q -r requirements.txt
python app.py
pause
