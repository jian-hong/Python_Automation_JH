#!/bin/bash
cd "$(dirname "$0")/.."
echo "Installing from requirements.txt..."
pip3 install -r requirements.txt
echo "Done."
