@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   BrainAtlas Server - Kill and Restart
echo ============================================
echo.

echo [1/4] Killing old processes on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
taskkill /F /IM python.exe >nul 2>&1
echo   Done.
timeout /t 3 /nobreak >nul

echo [2/4] Clearing __pycache__...
cd /d E:\workspace\brainatlas
for /d /r %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)
echo   Done.

echo [3/4] Starting uvicorn server...
set PYTHONPATH=.
start "BrainAtlas Server" cmd /k "E:\workspace\.venv\Scripts\python.exe -m uvicorn apps.brainatlas.backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [4/4] Waiting for server to start...
timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo   Server should be running now!
echo   Test:  http://127.0.0.1:8000/api/health
echo   Should show: "version": "v2-reloaded"
echo ============================================
echo.
pause
