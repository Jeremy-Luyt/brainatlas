@echo off
chcp 65001 >nul 2>&1
cd /d E:\workspace\brainatlas
set PYTHONPATH=.
E:\workspace\.venv\Scripts\python.exe scripts\diagnose_image.py
pause
