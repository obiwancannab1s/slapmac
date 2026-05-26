#!/usr/bin/env python3
"""Hardware-independent regression tests for SlapMac core behavior."""

import os
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from config import Config
from detector import AudioDetector
from motion_detector import load_motion_detection
from player import AudioPlayer


class ConfigTests(unittest.TestCase):
    def test_normalize_repairs_out_of_range_values(self):
        config = Config(
            sensitivity=99,
            cooldown=-5,
            output_volume=8,
            input_device="3",
            sensor_mode="auto",
            language="xx",
            enabled=1,
        ).normalize()

        self.assertEqual(config.sensitivity, 3.0)
        self.assertEqual(config.cooldown, 0.2)
        self.assertEqual(config.output_volume, 1.0)
        self.assertEqual(config.input_device, 3)
        self.assertEqual(config.sensor_mode, "microphone")
        self.assertEqual(config.language, "en")
        self.assertTrue(config.enabled)


class DetectorTests(unittest.TestCase):
    def make_detector(self):
        detector = AudioDetector(chunk_size=512)
        detector.baseline_rms = 0.002
        detector.baseline_peak = 0.01
        detector.set_sensitivity(1.3)
        detector.set_cooldown(1.0)
        return detector

    def test_silence_is_not_an_impact(self):
        detector = self.make_detector()
        chunk = np.zeros(512, dtype=np.float32)

        self.assertIsNone(detector._detect_impact(chunk))

    def test_short_chassis_like_tap_detects(self):
        detector = self.make_detector()
        chunk = np.zeros(512, dtype=np.float32)
        pulse = 0.16 * np.sin(np.linspace(0, np.pi, 32)) * np.exp(-np.linspace(0, 2, 32))
        chunk[220:252] = pulse.astype(np.float32)

        self.assertIn(detector._detect_impact(chunk), {"weak", "medium", "strong", "brutal"})

    def test_noisy_calibration_still_allows_chassis_tap(self):
        detector = self.make_detector()
        detector.baseline_rms = 0.383806
        detector.baseline_peak = 1.044100
        chunk = np.zeros(512, dtype=np.float32)
        chunk[220:224] = np.array([0.8, 0.28, -0.14, 0.06], dtype=np.float32)
        pulse = 0.25 * np.sin(np.linspace(0, np.pi, 56)) * np.exp(-np.linspace(0, 2.2, 56))
        chunk[224:280] += pulse.astype(np.float32)

        self.assertIn(detector._detect_impact(chunk), {"weak", "medium", "strong", "brutal"})

    def test_cooldown_suppresses_duplicate_chunk(self):
        detector = self.make_detector()
        chunk = np.zeros(512, dtype=np.float32)
        pulse = 0.16 * np.sin(np.linspace(0, np.pi, 32)) * np.exp(-np.linspace(0, 2, 32))
        chunk[220:252] = pulse.astype(np.float32)

        self.assertIsNotNone(detector._detect_impact(chunk))
        self.assertIsNone(detector._detect_impact(chunk))

    def test_sustained_fan_like_noise_is_rejected(self):
        detector = self.make_detector()
        detector.baseline_rms = 0.063654
        detector.baseline_peak = 0.177054
        detector.set_sensitivity(1.8)
        x = np.linspace(0, np.pi * 12, 512)
        chunk = (0.42 * np.sin(x)).astype(np.float32)

        self.assertIsNone(detector._detect_impact(chunk))

    def test_loud_sustained_noise_after_bad_calibration_is_rejected(self):
        detector = self.make_detector()
        detector.baseline_rms = 0.383806
        detector.baseline_peak = 1.044100
        detector.set_sensitivity(1.8)
        x = np.linspace(0, np.pi * 18, 512)
        chunk = (0.58 * np.sin(x)).astype(np.float32)

        self.assertIsNone(detector._detect_impact(chunk))

    def test_high_frequency_keyboard_like_click_is_rejected(self):
        detector = self.make_detector()
        chunk = np.zeros(512, dtype=np.float32)
        burst = 0.12 * np.sin(np.linspace(0, np.pi * 30, 24))
        chunk[220:244] = burst.astype(np.float32)

        self.assertIsNone(detector._detect_impact(chunk))

    def test_manual_suppression_blocks_detection(self):
        detector = self.make_detector()
        detector.suppress_for(1.0)
        chunk = np.zeros(512, dtype=np.float32)
        pulse = 0.16 * np.sin(np.linspace(0, np.pi, 32)) * np.exp(-np.linspace(0, 2, 32))
        chunk[220:252] = pulse.astype(np.float32)

        self.assertIsNone(detector._detect_impact(chunk))


class PlayerTests(unittest.TestCase):
    def make_wav(self, path: Path):
        samples = (np.sin(np.linspace(0, np.pi * 4, 256)) * 12000).astype(np.int16)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            wav_file.writeframes(samples.tobytes())

    def test_player_scans_and_caches_wavs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for category in ["weak", "medium", "strong", "brutal"]:
                category_dir = root / category
                category_dir.mkdir()
                self.make_wav(category_dir / f"{category}.wav")

            player = AudioPlayer(root, volume=0.5)
            try:
                self.assertEqual({k: len(v) for k, v in player._sounds_by_category.items()}, {
                    "weak": 1,
                    "medium": 1,
                    "strong": 1,
                    "brutal": 1,
                })
                self.assertEqual(len(player._wav_cache), 4)
                duration = player._estimated_duration(player._sounds_by_category["weak"][0])
                self.assertIsNotNone(duration)
                self.assertGreater(duration, 0)
            finally:
                player.shutdown()


class MotionTests(unittest.TestCase):
    def test_motion_probe_is_safe(self):
        self.assertIsInstance(load_motion_detection(), bool)


class GuiTests(unittest.TestCase):
    def test_gui_starts_with_microphone_selector(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from gui import SlapMacGUI

        app = QApplication.instance() or QApplication([])
        window = SlapMacGUI()
        try:
            self.assertEqual(window.config.sensor_mode, "microphone")
            self.assertTrue(window.mic_button.isChecked())
            self.assertTrue(hasattr(window, "input_device_combo"))
            self.assertTrue(callable(window.on_test_sound_clicked))
            self.assertGreaterEqual(window.input_device_combo.count(), 1)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
