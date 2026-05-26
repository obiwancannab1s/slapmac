#!/usr/bin/env python3
"""
SlapMac - macOS Impact Detector Application
Listens for impacts on MacBook and plays sounds based on force
"""

import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def _set_launcher_icon(png_path: Path, launcher: Path) -> None:
    """Set Finder icon on SlapMac.command using system Python + AppKit (silent on failure)."""
    if not png_path.exists() or not launcher.exists():
        return
    try:
        script = (
            f'from AppKit import NSWorkspace, NSImage; '
            f'img = NSImage.alloc().initWithContentsOfFile_("{png_path}"); '
            f'NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, "{launcher}", 0)'
        )
        subprocess.run(['/usr/bin/python3', '-c', script],
                       capture_output=True, timeout=3.0)
    except Exception:
        pass


def main():
    """Main entry point"""
    try:
        logger.info("Starting SlapMac Application...")

        # Import here to catch errors early
        from gui import SlapMacGUI
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QIcon

        app = QApplication(sys.argv)
        icon_path = PROJECT_ROOT / 'slapapp.png'
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            _set_launcher_icon(icon_path, PROJECT_ROOT / 'SlapMac.command')
        window = SlapMacGUI()
        window.show()
        
        logger.info("GUI loaded successfully")
        sys.exit(app.exec())
    
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Run: pip install -r requirements.txt")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
