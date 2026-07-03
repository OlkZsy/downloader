#!/usr/bin/env bash
# Установка MediaGrab для Linux/macOS:
#   chmod +x install.sh && ./install.sh
set -e
cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "================================================"
echo "Установка завершена! Запуск: ./start.sh"
echo "Не забудьте установить ffmpeg (см. README.md)."
echo "================================================"
