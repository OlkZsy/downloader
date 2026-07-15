@echo off
rem MediaGrab updater: downloads fresh program files from GitHub and
rem updates yt-dlp. Settings, history and cookies are NOT touched —
rem they are stored separately in %USERPROFILE%\.mediagrab
cd /d "%~dp0"
echo === Обновление MediaGrab ===
echo.

rem --- 1) update the program files -------------------------------------
where git >nul 2>nul
if %errorlevel%==0 if exist .git (
    echo Обновление через git...
    git pull --ff-only
    if errorlevel 1 (
        echo Не удалось обновиться через git. Проверьте интернет.
        pause
        exit /b 1
    )
    goto deps
)

echo Скачивание последней версии с GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $tmp=Join-Path $env:TEMP 'mediagrab_update'; Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue; Invoke-WebRequest 'https://github.com/OlkZsy/downloader/archive/refs/heads/main.zip' -OutFile ($tmp+'.zip'); Expand-Archive -Force ($tmp+'.zip') $tmp; Copy-Item -Recurse -Force (Join-Path $tmp 'downloader-main\*') '.'; Remove-Item -Recurse -Force $tmp,($tmp+'.zip')"
if errorlevel 1 (
    echo.
    echo Не удалось скачать обновление. Проверьте интернет-соединение.
    pause
    exit /b 1
)

:deps
rem --- 2) update dependencies (yt-dlp) ----------------------------------
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    pip install -U -r requirements.txt
) else (
    echo Виртуальное окружение не найдено — запустите install.bat
)

echo.
echo ================================================
echo Обновление завершено! Настройки, история и cookies не тронуты
echo (они хранятся в %USERPROFILE%\.mediagrab).
echo Запускайте приложение через start.bat
echo ================================================
pause
