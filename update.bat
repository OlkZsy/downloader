@echo off
rem Обновление MediaGrab: скачивает свежие файлы программы с GitHub
rem и обновляет yt-dlp. Настройки, история и cookies НЕ затрагиваются —
rem они хранятся отдельно, в %USERPROFILE%\.mediagrab
cd /d "%~dp0"
echo === Обновление MediaGrab ===
echo.

rem --- 1) обновить файлы программы -----------------------------------
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
rem --- 2) обновить зависимости (yt-dlp) --------------------------------
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
