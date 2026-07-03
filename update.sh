#!/usr/bin/env bash
# Обновление yt-dlp — запускайте, если загрузки перестали работать
cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
    echo "Сначала запустите ./install.sh"
    exit 1
fi
source .venv/bin/activate
pip install -U yt-dlp
echo
echo "Готово! Перезапустите приложение (./start.sh)."
