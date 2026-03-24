@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Recover Global Registration Results
echo ============================================
echo.

cd /d E:\workspace\brainatlas
set PYTHONPATH=.

E:\workspace\.venv\Scripts\python.exe scripts\recover_all_samples.py

echo.
echo ============================================
echo   Done! Refresh your browser to see Global.
echo ============================================
pause
