@echo off
rem Launch MediaGrab (run install.bat first)
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
    echo Сначала запустите install.bat
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
start "" pythonw run.py
