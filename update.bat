@echo off
rem Обновление yt-dlp — запускайте, если загрузки перестали работать
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
    echo Сначала запустите install.bat
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
pip install -U yt-dlp
echo.
echo Готово! Перезапустите приложение (start.bat).
pause
