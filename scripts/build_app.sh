#!/bin/bash

# SlapMac - Build macOS .app script
# Builds a standalone SlapMac.app bundle using PyInstaller

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install PyInstaller if not present
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install PyInstaller
fi

# Install other requirements
echo "Ensuring all dependencies are installed..."
pip install -r requirements.txt

# Build the .app
echo "Building SlapMac.app..."
pyinstaller \
    --windowed \
    --name SlapMac \
    --add-data "sounds:sounds" \
    --add-data "assets:assets" \
    --osx-bundle-identifier com.slapmac.app \
    --collect-all PyQt6 \
    --collect-all pygame \
    app.py

# The built app will be in dist/SlapMac.app
if [ -d "dist/SlapMac.app" ]; then
    echo "✓ Build successful! App located at: dist/SlapMac.app"
    echo ""
    echo "To run the app:"
    echo "  open dist/SlapMac.app"
    echo ""
    echo "To install (optional):"
    echo "  cp -r dist/SlapMac.app /Applications/"
else
    echo "✗ Build failed"
    exit 1
fi

deactivate
