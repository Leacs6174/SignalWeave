@echo off
setlocal
cd /d "%~dp0"

if exist "dist\SignalWeave\SignalWeave.exe" (
    start "" "dist\SignalWeave\SignalWeave.exe"
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
    exit /b 0
)

echo 未找到 SignalWeave，请先运行 verify_and_build.ps1。
pause
exit /b 1
