#!/bin/bash
cd "$(dirname "$0")"

VENV="../venv/bin/activate"
PIP="../venv/bin/pip"
PYTHON="../venv/bin/python"

if [ ! -f "$VENV" ]; then
    echo ""
    echo "ERROR: Virtual environment not found."
    echo "Please run install.py first:"
    echo "  python3 install.py"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

source "$VENV"
echo "Checking automation dependencies..."
$PIP install requests python-dotenv --quiet --disable-pip-version-check

echo ""
$PYTHON git_helper.py
echo ""
read -p "Press Enter to close..."
