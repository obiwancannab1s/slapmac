import atexit
import os
import random
import numpy as np
from queue import Queue, Empty
from pathlib import Path
from typing import Optional
import threading
import wave
import subprocess
import platform
import logging
from dataclasses import dataclass

# Try to import sounddevice, pygame, and macOS afplay.
SOUNDDEVICE_AVAILABLE = False
PYGAME_AVAILABLE = False
PYGAME_IMPORT_ERROR = ""

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    pass

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
    import pygame.mixer  # noqa: F401
    PYGAME_AVAILABLE = True
except Exception as e:
    pygame = None
    PYGAME_AVAILABLE = False
    PYGAME_IMPORT_ERROR = str(e)

# macOS has built-in afplay
AFPLAY_AVAILABLE = platform.system() == "Darwin" and Path("/usr/bin/afplay").exists()

if not SOUNDDEVICE_AVAILABLE and not PYGAME_AVAILABLE and not AFPLAY_AVAILABLE:
    print("⚠️ Warning: No audio backend available (sounddevice, pygame, or afplay)")


@dataclass(frozen=True)
class CachedWav:
    data: np.ndarray
    samplerate: int
    duration: float


class AudioPlayer:
    """Audio player for impact sounds"""
    
    def __init__(self, sounds_dir: Path = Path("sounds"), volume: float = 0.8):
        """
        Initialize player
        
        Args:
            sounds_dir: Path to sounds directory
            volume: Volume level (0.0 to 1.0)
        """
        self.sounds_dir = Path(sounds_dir)
        self.volume = max(0.0, min(1.0, volume))
        self._current_playback = None
        self._afplay_process: Optional[subprocess.Popen] = None
        self._sounds_by_category = self._scan_sound_files()
        self._wav_cache = {}
        self._cache_wavs()
        # Playback queue and worker
        self._queue: Queue = Queue(maxsize=1)
        self._player_shutdown_event = threading.Event()
        self._player_thread = threading.Thread(target=self._player_loop, daemon=True)
        self._player_thread.start()
        # Deduplication: prevent multiple plays for a single impact
        self._last_play_time = 0.0
        self._min_play_interval = 0.12  # seconds
        atexit.register(self.shutdown)
    
    def play_random_sound(self, category: str):
        """
        Play random sound from category
        
        Args:
            category: Sound category (weak, medium, strong, brutal)
        """
        sound_file = self._get_random_sound(category)
        
        if sound_file:
            import time
            now = time.time()

            # If we recently played a sound, ignore duplicate request
            if now - self._last_play_time < self._min_play_interval:
                return

            # Keep the newest pending sound only. This avoids delayed stale
            # playback when several impacts happen while a longer sound plays.
            try:
                self._clear_pending()
                self._queue.put_nowait(sound_file)
                self._last_play_time = now
                return self._estimated_duration(sound_file)
            except Exception:
                return None
        else:
            print(f"No sound files found for category: {category}")
        return None
    
    def _get_random_sound(self, category: str) -> Optional[Path]:
        """Get random sound file from category"""
        sound_files = self._sounds_by_category.get(category, [])
        if not sound_files:
            print(f"No sound files in {self.sounds_dir / category}")
            return None
        
        return random.choice(sound_files)

    def _scan_sound_files(self) -> dict:
        """Build a stable category -> files map once at startup."""
        categories = ['weak', 'medium', 'strong', 'brutal']
        sounds = {}

        for category in categories:
            category_dir = self.sounds_dir / category
            files = []
            if category_dir.exists():
                for ext in ['*.wav', '*.mp3', '*.WAV', '*.MP3']:
                    files.extend(sorted(category_dir.glob(ext)))
            sounds[category] = files

        return sounds

    def _cache_wavs(self):
        """Pre-decode WAV files so impact playback does not wait on disk I/O."""
        for files in self._sounds_by_category.values():
            for file_path in files:
                if file_path.suffix.lower() != '.wav':
                    continue
                try:
                    self._wav_cache[file_path] = self._read_wav(file_path)
                except Exception as e:
                    print(f"Could not cache WAV {file_path}: {e}")
    
    def _play_file(self, file_path: Path):
        """Play audio file."""
        if file_path.suffix.lower() == '.wav':
            try:
                self._play_wav(file_path)
            except Exception as e:
                print(f"Error playing WAV: {e}")
        elif file_path.suffix.lower() == '.mp3':
            self._play_encoded_audio(file_path)
        else:
            print(f"Unsupported file format: {file_path.suffix}")
    
    def _play_wav(self, file_path: Path):
        """Play WAV file using afplay, pygame, or sounddevice fallback."""

        if AFPLAY_AVAILABLE:
            try:
                self._play_afplay(file_path)
                return
            except Exception as e:
                print(f"afplay failed, trying pygame or sounddevice: {e}")

        if PYGAME_AVAILABLE:
            try:
                self._play_pygame(file_path)
                return
            except Exception as e:
                print(f"pygame failed, trying sounddevice: {e}")

        if SOUNDDEVICE_AVAILABLE:
            try:
                self._play_wav_sounddevice(file_path)
                return
            except Exception as e:
                print(f"sounddevice failed as last resort: {e}")

        print(f"Could not play {file_path}: no audio backend available")

    def _play_wav_sounddevice(self, file_path: Path):
        """Play WAV file using sounddevice"""
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice not available")

        cached = self._wav_cache.get(file_path)
        if cached is None:
            cached = self._read_wav(file_path)
            self._wav_cache[file_path] = cached

        audio_np = np.clip(cached.data * self.volume, -1.0, 1.0)

        try:
            self._current_playback = sd.play(audio_np, samplerate=cached.samplerate)
            sd.wait()
        finally:
            self._current_playback = None

    def _play_encoded_audio(self, file_path: Path):
        """Play compressed audio formats through afplay or pygame."""
        if AFPLAY_AVAILABLE:
            try:
                self._play_afplay(file_path)
                return
            except Exception as e:
                print(f"afplay failed for {file_path.suffix}, trying pygame: {e}")

        if PYGAME_AVAILABLE:
            try:
                self._play_pygame(file_path)
                return
            except Exception as e:
                print(f"pygame failed for {file_path.suffix}: {e}")

        print(f"Could not play {file_path}: no decoder backend available")

    def _read_wav(self, file_path: Path) -> CachedWav:
        """Read WAV into normalized float32 data."""
        with wave.open(str(file_path), 'rb') as wav_file:
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()

            audio_data = wav_file.readframes(n_frames)

        # Convert to numpy array depending on sample width
        if sample_width == 1:
            audio_np = np.frombuffer(audio_data, dtype=np.uint8).astype(np.float32)
            audio_np = (audio_np - 128.0) / 128.0
        elif sample_width == 2:
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            audio_np = np.frombuffer(audio_data, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Reshape for multi-channel
        if n_channels > 1:
            frames = len(audio_np) // n_channels
            audio_np = audio_np[:frames * n_channels].reshape(-1, n_channels)

        duration = len(audio_np) / float(framerate)
        return CachedWav(audio_np, framerate, duration)

    def _estimated_duration(self, file_path: Path) -> float:
        """Best-effort duration for detector self-audio suppression."""
        cached = self._wav_cache.get(file_path)
        if cached is not None:
            return cached.duration

        if file_path.suffix.lower() == ".wav":
            try:
                cached = self._read_wav(file_path)
                self._wav_cache[file_path] = cached
                return cached.duration
            except Exception:
                pass

        return 1.5

    def _play_pygame(self, file_path: Path):
        """Play an audio file using pygame mixer."""
        if not PYGAME_AVAILABLE:
            raise RuntimeError(f"pygame mixer not available: {PYGAME_IMPORT_ERROR or 'unknown error'}")

        if pygame is None or not hasattr(pygame, 'mixer'):
            raise RuntimeError("pygame.mixer not available")

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(str(file_path))
            sound.set_volume(self.volume)
            self._current_playback = sound.play()

            # Wait for playback to finish
            while pygame.mixer.get_busy():
                import time
                time.sleep(0.01)
        finally:
            self._current_playback = None

    def _play_afplay(self, file_path: Path):
        """Play an audio file using macOS afplay."""
        if not AFPLAY_AVAILABLE:
            raise RuntimeError("afplay not available")

        vol = max(0.0, min(1.0, self.volume))
        proc = subprocess.Popen(["/usr/bin/afplay", "-v", str(vol), str(file_path)])
        self._afplay_process = proc
        try:
            proc.wait()
        finally:
            self._afplay_process = None

    def _player_loop(self):
        """Background worker that plays queued sounds sequentially."""
        while not self._player_shutdown_event.is_set():
            try:
                file_path = self._queue.get(timeout=0.2)
            except Empty:
                continue

            if file_path is None:
                # sentinel to exit
                break

            # Play the file (blocking inside _play_file)
            try:
                logger = logging.getLogger(__name__)
                logger.info(f"Playing sound file: {file_path}")
                self._play_file(file_path)
            except Exception as e:
                print(f"Playback worker error: {e}")
            finally:
                # Mark task done if using task_done semantics
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def set_volume(self, value: float):
        """Set playback volume"""
        self.volume = max(0.0, min(1.0, value))

    def _clear_pending(self):
        """Clear queued sounds without touching active playback."""
        while True:
            try:
                self._queue.get_nowait()
                try:
                    self._queue.task_done()
                except Exception:
                    pass
            except Empty:
                break

    def stop_current(self):
        """Stop current playback and clear pending sounds"""
        self._clear_pending()

        proc = self._afplay_process
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

        self._current_playback = None

    def shutdown(self):
        """Shutdown the playback worker and stop audio"""
        try:
            self._player_shutdown_event.set()
        except Exception:
            pass

        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

        if self._player_thread and self._player_thread.is_alive():
            self._player_thread.join(timeout=1.0)

        self._current_playback = None
