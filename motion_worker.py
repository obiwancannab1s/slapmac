#!/usr/bin/env python3
"""CoreMotion worker for SlapMac accelerometer impact detection."""

import argparse
import json
import math
import sys
import threading
import time

import numpy as np


def emit(event_type: str, **payload):
    payload["type"] = event_type
    print(json.dumps(payload), flush=True)


class CoreMotionWorker:
    def __init__(self, sample_rate: int, sensitivity: float, cooldown: float):
        from CoreMotion import CMMotionManager  # type: ignore

        self.sample_rate = sample_rate
        self.sensitivity = sensitivity
        self.cooldown = cooldown

        self.manager = CMMotionManager.alloc().init()
        if not self.manager.isAccelerometerAvailable():
            raise RuntimeError("Accelerometer unavailable on this Mac")

        self.manager.setAccelerometerUpdateInterval_(1.0 / self.sample_rate)

        self.baseline_magnitude = 1.0
        self.baseline_jerk = 0.02
        self.previous_vector = None
        self.last_impact_time = 0.0
        self.impact_active = False
        self.impact_low_counter = 0
        self.impact_low_chunks = 4
        self.release_threshold = 0.06
        self.running = True

        self.thresholds = {
            "weak": (0.08, 0.20),
            "medium": (0.20, 0.45),
            "strong": (0.45, 0.85),
            "brutal": (0.85, math.inf),
        }

    def calibrate(self, duration: float):
        magnitudes = []
        jerks = []
        previous = None
        self.manager.startAccelerometerUpdates()

        start = time.time()
        while time.time() - start < duration:
            vector = self._read_vector()
            if vector is not None:
                magnitudes.append(float(np.linalg.norm(vector)))
                if previous is not None:
                    jerks.append(float(np.linalg.norm(vector - previous)))
                previous = vector
            time.sleep(1.0 / self.sample_rate)

        if not magnitudes:
            raise RuntimeError("No accelerometer samples received")

        self.baseline_magnitude = float(np.mean(magnitudes))
        if jerks:
            self.baseline_jerk = max(0.01, float(np.percentile(jerks, 95)))
        self.previous_vector = previous
        emit(
            "status",
            message=f"Accelerometer ready: baseline {self.baseline_magnitude:.3f}g, jitter {self.baseline_jerk:.3f}g",
        )

    def run(self):
        self.manager.startAccelerometerUpdates()
        while self.running:
            vector = self._read_vector()
            if vector is not None:
                self._handle_vector(vector)
            time.sleep(1.0 / self.sample_rate)

        self.manager.stopAccelerometerUpdates()

    def stop(self):
        self.running = False

    def _read_vector(self):
        data = self.manager.accelerometerData()
        if data is None:
            return None
        acc = data.acceleration
        return np.array([acc.x, acc.y, acc.z], dtype=float)

    def _handle_vector(self, vector):
        current_time = time.time()
        magnitude = float(np.linalg.norm(vector))
        delta = abs(magnitude - self.baseline_magnitude)

        jerk = 0.0
        if self.previous_vector is not None:
            jerk = float(np.linalg.norm(vector - self.previous_vector))
        self.previous_vector = vector

        score = max(delta, jerk - self.baseline_jerk)

        if self.impact_active:
            if score < self.release_threshold:
                self.impact_low_counter += 1
            else:
                self.impact_low_counter = 0

            if self.impact_low_counter >= self.impact_low_chunks:
                self.impact_active = False
                self.impact_low_counter = 0
            return

        if current_time - self.last_impact_time < self.cooldown:
            return

        adjusted = score * self.sensitivity
        min_delta = max(0.045, self.baseline_jerk * 2.5)
        if adjusted < min_delta:
            return

        for category, (lower, upper) in self.thresholds.items():
            if lower <= adjusted < upper:
                self.impact_active = True
                self.impact_low_counter = 0
                self.last_impact_time = current_time
                emit(
                    "impact",
                    category=category,
                    delta=round(delta, 4),
                    jerk=round(jerk, 4),
                    adjusted=round(adjusted, 4),
                )
                return

    def set_sensitivity(self, value: float):
        self.sensitivity = max(0.5, min(3.0, value))

    def set_cooldown(self, value: float):
        self.cooldown = max(0.2, min(2.0, value))


def command_loop(worker: CoreMotionWorker):
    for line in sys.stdin:
        try:
            command = json.loads(line)
        except Exception:
            continue

        name = command.get("cmd")
        if name == "stop":
            worker.stop()
            return
        if name == "set_sensitivity":
            worker.set_sensitivity(float(command.get("value", worker.sensitivity)))
        elif name == "set_cooldown":
            worker.set_cooldown(float(command.get("value", worker.cooldown)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--sample-rate", type=int, default=100)
    parser.add_argument("--sensitivity", type=float, default=1.8)
    parser.add_argument("--cooldown", type=float, default=0.35)
    parser.add_argument("--calibrate", type=float, default=1.0)
    args = parser.parse_args()

    try:
        worker = CoreMotionWorker(args.sample_rate, args.sensitivity, args.cooldown)
        if args.probe:
            emit("status", message="Accelerometer CoreMotion probe succeeded")
            return
        worker.calibrate(args.calibrate)
        threading.Thread(target=command_loop, args=(worker,), daemon=True).start()
        worker.run()
    except Exception as e:
        emit("error", message=f"Accelerometer worker error: {e}")
        raise


if __name__ == "__main__":
    main()
