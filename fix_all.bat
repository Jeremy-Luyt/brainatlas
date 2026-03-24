@echo off
chcp 65001 >nul 2>&1
echo.
echo ============================================================
echo   BrainAtlas - 一键修复 (Kill + Recover + Restart)
echo ============================================================
echo.

cd /d E:\workspace\brainatlas
set PYTHONPATH=.

echo [1/4] 杀掉旧进程...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
taskkill /F /IM python.exe >nul 2>&1
echo   OK
echo.

echo [2/4] 清理 __pycache__...
for /d /r %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)
echo   OK
echo.

echo [3/4] 恢复所有样本的 Global 配准数据...
E:\workspace\.venv\Scripts\python.exe scripts\recover_all_samples.py
echo.

echo [4/4] 启动新服务器 (新窗口)...
start "BrainAtlas Server" cmd /k "cd /d E:\workspace\brainatlas && set PYTHONPATH=. && E:\workspace\.venv\Scripts\python.exe -m uvicorn apps.brainatlas.backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo 等待服务器启动...
timeout /t 6 /nobreak >nul

echo.
echo ============================================================
echo   全部完成！
echo.
echo   验证步骤：
echo   1. 打开浏览器访问 http://127.0.0.1:8000/api/health
echo      应显示 "version": "v2-reloaded"
echo.
echo   2. 打开 Viewer，选择任意样本，Global 应该可以查看了
echo ============================================================
echo.
pause
