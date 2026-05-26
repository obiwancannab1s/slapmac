#!/bin/bash

# SlapMac - Double-click launcher for macOS
# Navigate to project directory and run the app

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR"
export PYGAME_HIDE_SUPPORT_PROMPT=1

# Set custom Finder icon on this launcher file (runs once, silent on failure)
/usr/bin/python3 -c "
import sys
try:
    from AppKit import NSWorkspace, NSImage
    img = NSImage.alloc().initWithContentsOfFile_(sys.argv[1])
    if img and not img.isNull():
        NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, sys.argv[2], 0)
except Exception:
    pass
" "$SCRIPT_DIR/slapapp.png" "$SCRIPT_DIR/SlapMac.command" 2>/dev/null || true

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if requirements are installed
if ! python3 -c "import PyQt6, sounddevice, numpy, pygame, CoreMotion" 2>/dev/null; then
    echo "📦 Installing requirements..."
    pip install -r requirements.txt --quiet
fi

# Run the app
echo "🎵 Starting SlapMac..."
python3 app.py

# Keep terminal open on error
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error starting SlapMac"
    echo "Press Enter to close..."
    read
fi

deactivate
