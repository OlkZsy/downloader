@echo off
rem Установка MediaGrab для Windows: создаёт виртуальное окружение
rem и ставит зависимости. Запускать двойным кликом.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if not exist .venv\Scripts\activate.bat (
    echo.
    echo ОШИБКА: Python не найден. Установите Python 3.10+ с python.org
    echo и при установке отметьте галочку "Add Python to PATH".
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ================================================
echo Установка завершена! Запускайте приложение через start.bat
echo Не забудьте установить ffmpeg (см. README.md, раздел Windows).
echo ================================================
pause
