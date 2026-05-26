#!/bin/bash

# SlapMac - Run script
# Run the application with Python

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
export PYGAME_HIDE_SUPPORT_PROMPT=1

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if requirements are installed
if ! python3 -c "import PyQt6, sounddevice, numpy, pygame, CoreMotion" 2>/dev/null; then
    echo "Installing requirements..."
    pip install -r requirements.txt
fi

# Run the app
echo "Starting SlapMac..."
python3 app.py

deactivate
