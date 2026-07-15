#!/usr/bin/env bash
# Launch MediaGrab (run ./install.sh first)
cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
    echo "Сначала запустите ./install.sh"
    exit 1
fi
source .venv/bin/activate
python run.py
