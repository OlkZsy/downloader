#!/usr/bin/env python3
"""Запуск MediaGrab: python run.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mediagrab.app import main  # noqa: E402

if __name__ == "__main__":
    main()
