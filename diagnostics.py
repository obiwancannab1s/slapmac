#!/usr/bin/env python3
"""SlapMac diagnostics that can run without starting the GUI."""

from pathlib import Path
import os
import platform
import sys

from config import Config, SOUNDS_DIR, validate_sounds_structure
import motion_detector


def print_header(title: str):
    print(f"\n{title}")
    print("-" * len(title))


def check_dependencies():
    print_header("Dependencies")
    modules = ["PyQt6", "sounddevice", "numpy", "CoreMotion"]
    for name in modules:
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "ok")
            print(f"✓ {name}: {version}")
        except Exception as e:
            print(f"✗ {name}: {e}")

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        import pygame
        version = getattr(pygame, "version", pygame).ver
        try:
            import pygame.mixer  # noqa: F401
            mixer_status = "mixer ok"
        except Exception as e:
            mixer_status = f"mixer unavailable ({e}); afplay fallback will be used on macOS"
        print(f"✓ pygame: {version}, {mixer_status}")
    except Exception as e:
        print(f"⚠ pygame optional: {e}")


def check_audio_devices():
    print_header("Audio Input Devices")
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        if isinstance(devices, dict):
            devices = [devices]

        inputs = [
            (idx, device)
            for idx, device in enumerate(devices)
            if device.get("max_input_channels", 0) > 0
        ]
        print(f"Default device: {sd.default.device}")
        if not inputs:
            print("✗ No input devices visible to Python.")
            print("  Check macOS Privacy & Security -> Microphone for Terminal.")
            return

        for idx, device in inputs:
            print(
                f"✓ [{idx}] {device.get('name', 'Unknown')} "
                f"channels={device.get('max_input_channels')} "
                f"rate={int(device.get('default_samplerate', 0))}"
            )
    except Exception as e:
        print(f"✗ Could not query audio devices: {e}")


def check_sounds():
    print_header("Sound Library")
    status = validate_sounds_structure()
    for category, count in status.items():
        marker = "✓" if count else "✗"
        print(f"{marker} {category}: {count} file(s)")
    print(f"Sounds dir: {SOUNDS_DIR}")


def check_motion():
    print_header("Accelerometer")
    available = motion_detector.load_motion_detection()
    marker = "✓" if available else "✗"
    print(f"{marker} CoreMotion available: {available}")
    print(f"Status: {motion_detector.MOTION_ERROR}")


def check_config():
    print_header("Config")
    config = Config.load()
    print(config)


def main():
    root = Path(__file__).parent
    print("SlapMac Diagnostics")
    print("===================")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.platform()}")
    print(f"Project: {root}")

    check_config()
    check_dependencies()
    check_audio_devices()
    check_sounds()
    check_motion()

    print("\nDone.")


if __name__ == "__main__":
    main()
