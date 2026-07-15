#!/usr/bin/env bash
# MediaGrab updater: downloads fresh program files from GitHub and
# updates yt-dlp. Settings, history and cookies are NOT touched —
# they are stored separately in ~/.mediagrab
set -e
cd "$(dirname "$0")"
echo "=== Обновление MediaGrab ==="
echo

# --- 1) update the program files --------------------------------------
if [ -d .git ] && command -v git >/dev/null 2>&1; then
    echo "Обновление через git..."
    git pull --ff-only
else
    echo "Скачивание последней версии с GitHub..."
    tmp=$(mktemp -d)
    curl -fL -o "$tmp/update.zip" \
        https://github.com/OlkZsy/downloader/archive/refs/heads/main.zip
    unzip -q -o "$tmp/update.zip" -d "$tmp"
    cp -rf "$tmp"/downloader-main/* .
    rm -rf "$tmp"
fi

# --- 2) update dependencies (yt-dlp) -----------------------------------
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
    pip install -U -r requirements.txt
else
    echo "Виртуальное окружение не найдено — запустите ./install.sh"
fi

echo
echo "================================================"
echo "Обновление завершено! Настройки, история и cookies не тронуты"
echo "(они хранятся в ~/.mediagrab). Запуск: ./start.sh"
echo "================================================"
