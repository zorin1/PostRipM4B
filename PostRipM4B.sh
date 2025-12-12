#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"

if [ -f "$VENV_PYTHON" ]; then
    exec "$VENV_PYTHON" "$SCRIPT_DIR/PostRipM4B.py" "$@"
else
    echo "Virtual environment not found at: $VENV_PYTHON"
    echo "Please run: python3 -m venv .venv"
    echo "Then install requirements: pip install -r requirements.txt"
    exit 1
fi
