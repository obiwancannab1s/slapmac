#!/usr/bin/env python3
"""
Crash-safe accelerometer detector wrapper.

CoreMotion can terminate the Python process on some macOS/PyObjC combinations.
Keep it in a child process so the GUI remains responsive and can report errors.
"""

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

MOTION_AVAILABLE = False
MOTION_ERROR = "Accelerometer support not checked"


def load_motion_detection() -> bool:
    """Check whether CoreMotion can open the accelerometer in a child process."""
    global MOTION_AVAILABLE, MOTION_ERROR

    try:
        worker = Path(__file__).with_name("motion_worker.py")
        if worker.exists():
            probe = subprocess.run(
                [sys.executable, str(worker), "--probe"],
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
            if probe.returncode == 0 and "probe succeeded" in probe.stdout:
                MOTION_AVAILABLE = True
                MOTION_ERROR = "CoreMotion accelerometer available"
                return True

            message = (probe.stdout + probe.stderr).strip()
            if message:
                MOTION_ERROR = message.splitlines()[-1]
            else:
                MOTION_ERROR = f"CoreMotion probe failed with exit {probe.returncode}"
            MOTION_AVAILABLE = False
            return False

        result = subprocess.run(
            ["hidutil", "list"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        output = result.stdout + result.stderr
        if "SPU" in output and ("65280     3" in output or "0x8104" in output):
            MOTION_AVAILABLE = True
            MOTION_ERROR = "Apple SPU accelerometer service detected"
            return True

        MOTION_AVAILABLE = False
        MOTION_ERROR = "Apple SPU accelerometer service not found"
        return False
    except Exception as e:
        MOTION_AVAILABLE = False
        MOTION_ERROR = f"Accelerometer check failed: {e}"
        return False


class MotionDetector:
    """Runs accelerometer impact detection in a separate Python process."""

    def __init__(
        self,
        sample_rate: int = 100,
        on_impact: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.on_impact = on_impact
        self.on_status = on_status

        self.sensitivity = 1.8
        self.cooldown_time = 0.35
        self._calibrate_duration = 1.0

        self._running = False
        self._process = None
        self._reader_thread = None

    def calibrate(self, duration: float = 1.0) -> float:
        """Store calibration duration; the worker calibrates immediately on start."""
        self._calibrate_duration = max(0.2, min(3.0, duration))
        return 1.0

    def start(self):
        """Start the CoreMotion worker."""
        if self._running:
            return

        worker = Path(__file__).with_name("motion_worker.py")
        if not worker.exists():
            raise RuntimeError("motion_worker.py not found")

        self._running = True
        cmd = [
            sys.executable,
            str(worker),
            "--sample-rate",
            str(self.sample_rate),
            "--sensitivity",
            str(self.sensitivity),
            "--cooldown",
            str(self.cooldown_time),
            "--calibrate",
            str(self._calibrate_duration),
        ]

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._reader_thread = threading.Thread(target=self._read_worker_output, daemon=True)
        self._reader_thread.start()
        print("Motion detector worker started")

    def stop(self):
        """Stop the worker process."""
        if not self._running:
            return

        self._running = False
        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.write(json.dumps({"cmd": "stop"}) + "\n")
                    self._process.stdin.flush()
            except Exception:
                pass

            try:
                self._process.terminate()
                self._process.wait(timeout=1.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass

        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)

        self._process = None
        self._reader_thread = None
        print("Motion detector stopped")

    def _read_worker_output(self):
        process = self._process
        if not process or not process.stdout:
            return

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except Exception:
                print(line)
                continue

            event_type = event.get("type")
            if event_type == "impact":
                category = event.get("category")
                if category and self.on_impact:
                    try:
                        self.on_impact(category)
                    except Exception as e:
                        print(f"Impact callback error: {e}")
            elif event_type == "status":
                message = event.get("message", "")
                print(message)
                if message and self.on_status:
                    try:
                        self.on_status(message)
                    except Exception:
                        pass
            elif event_type == "error":
                message = event.get("message", "Motion worker error")
                print(message)
                if self.on_status:
                    try:
                        self.on_status(message)
                    except Exception:
                        pass

        if self._running:
            code = process.poll()
            message = f"Motion worker stopped unexpectedly (exit {code})"
            print(message)
            if self.on_status:
                try:
                    self.on_status(message)
                except Exception:
                    pass
            self._running = False

    def _send_command(self, payload: dict):
        if not self._process or not self._process.stdin:
            return
        try:
            self._process.stdin.write(json.dumps(payload) + "\n")
            self._process.stdin.flush()
        except Exception:
            pass

    def set_sensitivity(self, value: float):
        self.sensitivity = max(0.5, min(3.0, value))
        self._send_command({"cmd": "set_sensitivity", "value": self.sensitivity})

    def set_cooldown(self, value: float):
        self.cooldown_time = max(0.2, min(2.0, value))
        self._send_command({"cmd": "set_cooldown", "value": self.cooldown_time})

    def suppress_for(self, seconds: float):
        """No-op for accelerometer — audio playback does not affect motion readings."""
        pass


if __name__ == "__main__":
    print("Accelerometer service:", load_motion_detection(), MOTION_ERROR)
