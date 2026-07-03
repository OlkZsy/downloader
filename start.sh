#!/usr/bin/env bash
# Запуск MediaGrab (сначала выполните ./install.sh)
cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
    echo "Сначала запустите ./install.sh"
    exit 1
fi
source .venv/bin/activate
python run.py
