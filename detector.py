import sounddevice as sd
import numpy as np
from threading import Thread, Event
from typing import Callable, Optional, Protocol, runtime_checkable
import time


@runtime_checkable
class SlapDetector(Protocol):
    """Interface that all impact detectors must satisfy.

    To add a new detector type:
      1. Create a new module (e.g. detectors/my_sensor.py)
      2. Implement this Protocol — calibrate(), start(), stop(),
         set_sensitivity(), set_cooldown(), suppress_for()
      3. Register the mode in Config.sensor_mode choices
      4. Add the mode to SlapMacGUI._start_detector_with_mode()
    """

    def calibrate(self, duration: float = 1.0, **kwargs) -> None: ...
    def start(self, **kwargs) -> None: ...
    def stop(self) -> None: ...
    def set_sensitivity(self, value: float) -> None: ...
    def set_cooldown(self, value: float) -> None: ...
    def suppress_for(self, seconds: float) -> None: ...


class AudioDetector:
    """Real-time audio spike detector with noise calibration"""
    
    def __init__(self,
                 sample_rate: int = 44100,
                 chunk_size: int = 512,
                 on_impact: Optional[Callable[[str], None]] = None,
                 on_status: Optional[Callable[[str], None]] = None,
                 on_level: Optional[Callable[[float], None]] = None):
        """
        Initialize detector

        Args:
            sample_rate: Audio sample rate
            chunk_size: Samples per chunk
            on_impact: Callback(category) called when an impact is detected
            on_status: Callback(message) for status/error updates
            on_level:  Callback(peak) emitting raw peak amplitude each chunk
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.on_impact = on_impact
        self.on_status = on_status
        
        self.on_level = on_level

        # Noise baseline (will be calibrated)
        self.baseline_rms = 0.001
        self.baseline_peak = 0.001

        # Dynamic background tracking for onset detection (EMA)
        self._bg_rms = 0.01
        self._bg_peak = 0.02
        # Asymmetric EMA: fast downward (tracks drops/silence quickly),
        # very slow upward (prevents slap echoes or fan bursts from inflating background).
        # During warmup the fast rate is used for both directions so the fan level is seeded.
        self._bg_alpha = 0.15        # downward / warmup rate
        self._bg_alpha_up = 0.002    # upward rate (τ ≈ 5 s — slower than fan ramp, faster than minutes)
        self._warmup_until = 0.0     # suppress detection briefly after start to let EMA adapt

        # Detection parameters
        self.sensitivity = 1.0  # Will be set from GUI
        self.cooldown_time = 1.0
        self.last_impact_time = 0
        self._suppressed_until = 0.0
        self._impact_active = False
        self._impact_started_at = 0.0
        self._impact_low_counter = 0
        self._impact_low_chunks = 3
        self._max_impact_active_time = 0.45
        self._calibration_warning = ""

        # Thread control
        self._running = False
        self._stop_event = Event()
        self._stream = None
        self._thread = None

        # Onset-score thresholds (rms_jump or peak_jump × sensitivity)
        # Chassis slap produces crest ~2, so we use jump ratio not transient energy
        self.thresholds = {
            'weak': (2.2, 4.5),
            'medium': (4.5, 6.5),
            'strong': (6.5, 9.0),
            'brutal': (9.0, float('inf'))
        }
    
    def _is_virtual_device(self, device_info: dict) -> bool:
        """Detect common virtual input devices to prefer physical microphones."""
        name = device_info.get('name', '').lower()
        virtual_keywords = ['blackhole', 'obs', 'loopback', 'aggregate', 'multi', 'soundflower']
        return any(keyword in name for keyword in virtual_keywords)

    def _get_input_device(self, input_device: int = -1) -> Optional[int]:
        """Resolve an available input device index."""
        try:
            if input_device >= 0:
                return input_device

            default_device = sd.default.device
            if isinstance(default_device, (list, tuple)) and default_device[0] is not None:
                idx = int(default_device[0])
                try:
                    info = sd.query_devices(idx)
                    if info.get('max_input_channels', 0) > 0 and not self._is_virtual_device(info):
                        return idx
                except Exception:
                    pass

            devices = sd.query_devices()
            physical_devices = []
            virtual_devices = []
            for i, device in enumerate(devices):
                if device.get('max_input_channels', 0) > 0:
                    if self._is_virtual_device(device):
                        virtual_devices.append(i)
                    else:
                        physical_devices.append(i)

            if physical_devices:
                return physical_devices[0]
            if virtual_devices:
                return virtual_devices[0]
        except Exception:
            pass
        return None

    def _get_device_samplerate(self, device: Optional[int]) -> int:
        """Return a valid samplerate for the selected device."""
        try:
            if device is not None:
                info = sd.query_devices(device)
                rate = info.get('default_samplerate')
                if rate:
                    return int(rate)
        except Exception:
            pass
        return self.sample_rate

    def calibrate_noise(self, duration: float = 2.0, input_device: int = -1) -> tuple:
        """
        Calibrate baseline noise level
        Records ambient noise for specified duration
        
        Returns:
            (baseline_rms, baseline_peak)
        """
        print(f"Calibrating noise floor for {duration} seconds... Keep quiet!")
        
        try:
            device = self._get_input_device(input_device)
            samplerate = self._get_device_samplerate(device)
            self.sample_rate = samplerate  # sync to actual device rate

            chunks = []
            blocksize = self.chunk_size
            blocks = max(1, int((duration * samplerate) / blocksize))
            with sd.InputStream(
                channels=1,
                samplerate=samplerate,
                blocksize=blocksize,
                device=device,
                latency='low',
            ) as stream:
                for _ in range(blocks):
                    audio_data, _ = stream.read(blocksize)
                    chunks.append(audio_data.flatten())

            audio_data = np.concatenate(chunks) if chunks else np.zeros(blocksize, dtype=np.float32)
            audio_data = audio_data.astype(np.float32, copy=False)
            abs_audio = np.abs(audio_data)

            usable_len = (len(audio_data) // blocksize) * blocksize
            if usable_len >= blocksize:
                frames = audio_data[:usable_len].reshape(-1, blocksize)
                frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
                frame_peak = np.percentile(np.abs(frames), 90, axis=1)
                robust_rms = float(np.percentile(frame_rms, 35))
                robust_peak = float(np.percentile(frame_peak, 45))
            else:
                robust_rms = float(np.sqrt(np.mean(audio_data ** 2)))
                robust_peak = float(np.percentile(abs_audio, 90))

            raw_rms = float(np.sqrt(np.mean(audio_data ** 2)))
            raw_peak = float(np.percentile(abs_audio, 98))

            self.baseline_rms = robust_rms
            self.baseline_peak = robust_peak
            self._calibration_warning = ""
            if raw_rms > 0.08 or raw_peak > 0.35:
                self._calibration_warning = (
                    f"Noisy calibration input detected (raw RMS: {raw_rms:.3f}, "
                    f"raw peak: {raw_peak:.3f}); using capped impact baseline"
                )
        
        except Exception as e:
            print(f"Error during calibration: {e}")
            self.baseline_rms = 0.001
            self.baseline_peak = 0.001
            self._calibration_warning = ""
        
        # Keep the floor stable but prevent a noisy calibration from making
        # every real slap look smaller than the baseline.
        self.baseline_rms = min(max(float(self.baseline_rms), 0.002), 0.035)
        self.baseline_peak = min(max(float(self.baseline_peak), 0.01), 0.14)
        
        # Seed the dynamic background tracker from calibration
        self._bg_rms = self.baseline_rms
        self._bg_peak = self.baseline_peak

        print(f"Calibration complete. Baseline RMS: {self.baseline_rms:.6f}, Peak: {self.baseline_peak:.6f}")
        if self._calibration_warning:
            print(f"Calibration warning: {self._calibration_warning}")
        return self.baseline_rms, self.baseline_peak
    
    def calibrate(self, duration: float = 2.0, input_device: int = -1) -> tuple:
        """Alias for calibrate_noise to provide a common detector interface."""
        return self.calibrate_noise(duration, input_device)
    
    def _detect_impact(self, audio_chunk: np.ndarray) -> Optional[str]:
        """Onset-based impact detection.

        A MacBook chassis slap produces a low-crest burst (crest ~2) rather
        than a sharp spike, so we detect the sudden *jump* above the dynamic
        background level instead of relying on crest-factor or transient-ratio.
        """
        current_time = time.time()
        if current_time < self._suppressed_until:
            return None

        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        peak = float(np.max(np.abs(audio_chunk)))

        # --- Warm-up: fast uncapped EMA so bg fully adapts to actual ambient (fan, room) ---
        if current_time < self._warmup_until:
            self._bg_rms  = self._bg_alpha * rms  + (1 - self._bg_alpha) * self._bg_rms
            self._bg_peak = self._bg_alpha * peak + (1 - self._bg_alpha) * self._bg_peak
            # No cap here — let background reach real ambient level (even if fan is loud)
            return None

        # --- Impact sustain: wait for signal to drop back to background ---
        if self._impact_active:
            if current_time - self._impact_started_at > self._max_impact_active_time:
                self._impact_active = False
                self._impact_low_counter = 0
            else:
                release_rms = max(0.004, self._bg_rms * 1.6)
                release_peak = max(0.015, self._bg_peak * 1.6)
                if rms < release_rms and peak < release_peak:
                    self._impact_low_counter += 1
                else:
                    self._impact_low_counter = 0
                if self._impact_low_counter >= self._impact_low_chunks:
                    self._impact_active = False
                    self._impact_low_counter = 0
            return None

        # --- Update dynamic background (asymmetric EMA) ---
        # Drop quickly when signal falls; rise very slowly so transient spikes
        # (slap echoes, fan bursts) don't inflate the baseline.
        a_rms  = self._bg_alpha if rms  < self._bg_rms  else self._bg_alpha_up
        a_peak = self._bg_alpha if peak < self._bg_peak else self._bg_alpha_up
        new_rms  = a_rms  * rms  + (1 - a_rms)  * self._bg_rms
        new_peak = a_peak * peak + (1 - a_peak) * self._bg_peak
        self._bg_rms  = min(max(self.baseline_rms,  new_rms),  0.05)
        self._bg_peak = min(max(self.baseline_peak, new_peak), 0.18)

        if current_time - self.last_impact_time < self.cooldown_time:
            return None

        effective_bg_rms  = max(self._bg_rms,  0.004)
        effective_bg_peak = max(self._bg_peak, 0.010)

        # --- Onset detection: sudden jump above current background ---
        rms_jump  = rms  / effective_bg_rms
        peak_jump = peak / effective_bg_peak
        abs_delta = peak - effective_bg_peak

        # Floors scale inversely with sensitivity:
        #   0.5× (min) → peak_floor=0.30, delta=0.20 — только сильный шлепок
        #   1.0× (def) → peak_floor=0.15, delta=0.10 — средний шлепок
        #   3.0× (max) → peak_floor=0.05, delta=0.033 — лёгкое касание
        s = max(0.3, self.sensitivity)
        peak_floor  = max(0.04, 0.15 / s)
        delta_floor = max(0.025, 0.10 / s)

        onset_detected = (
            peak_jump >= 2.0
            and abs_delta >= delta_floor
            and peak >= peak_floor
        )

        if not onset_detected:
            return None

        # --- Frequency fingerprint of chassis resonance ---
        # При 512 семплах и 48kHz разрешение FFT = 93 Гц/бин — слишком грубо.
        # Zero-padding до 2048 даёт 23 Гц/бин → точный расчёт vlf_fraction.
        try:
            n_fft = len(audio_chunk) * 4
            padded = np.zeros(n_fft, dtype=np.float32)
            padded[:len(audio_chunk)] = audio_chunk * np.hanning(len(audio_chunk))
            spec  = np.abs(np.fft.rfft(padded))
            freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.sample_rate)
            total      = spec.sum() + 1e-12
            low_energy = spec[freqs <= 1200.0].sum()
            low_ratio    = low_energy / total
            vlf_fraction = spec[freqs <= 300.0].sum() / (low_energy + 1e-12)
            # Chassis slap: low_ratio ≥0.72, vlf_fraction ≥0.50
            # Fan / voice / cough fail one or both checks
            if low_ratio < 0.72 or vlf_fraction < 0.50:
                print(f"Freq filter: low_ratio={low_ratio:.3f} vlf={vlf_fraction:.3f} peak={peak:.4f} — rejected")
                return None
        except Exception:
            pass

        # --- Classify by peak_jump ratio (mic-gain-independent) ---
        # Thresholds tuned to observed range on M4 MacBook (bg_peak ≈ 0.14, max jump ~6-8×)
        if peak_jump >= 6.0:
            detected_category = 'brutal'
        elif peak_jump >= 4.0:
            detected_category = 'strong'
        elif peak_jump >= 2.8:
            detected_category = 'medium'
        elif peak >= peak_floor:
            detected_category = 'weak'
        else:
            detected_category = None

        if detected_category:
            self.last_impact_time = current_time
            self._impact_active = True
            self._impact_started_at = current_time
            self._impact_low_counter = 0
            print(
                f"Impact: {detected_category} | peak={peak:.4f} "
                f"rms_jump={rms_jump:.1f}x peak_jump={peak_jump:.1f}x "
                f"low_ratio={low_ratio:.2f} vlf={vlf_fraction:.2f}"
            )
            return detected_category

        return None
    
    def start(self, input_device: int = -1):
        """Start listening for impacts"""
        if self._running:
            return

        # Let the EMA fully adapt to actual ambient (fan, room) before detecting
        self._warmup_until = time.time() + 5.0
        self._running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._listen_loop, args=(input_device,), daemon=True)
        self._thread.start()
        print("Audio detector started")
    
    def stop(self):
        """Stop listening for impacts"""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        # Stream is owned by the with-block inside _listen_loop — let it clean up
        if self._thread:
            self._thread.join(timeout=2)
        self._stream = None
        print("Audio detector stopped")

    def _listen_loop(self, input_device: int = -1):
        """Main listening loop"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries and self._running:
            try:
                print(f"Opening audio stream on device {input_device if input_device >= 0 else 'default'}...")
                
                device = self._get_input_device(input_device)
                samplerate = self._get_device_samplerate(device)
                self.sample_rate = samplerate  # sync frequency analysis to actual device rate
                print(f"Trying device {device} at {samplerate} Hz")

                with sd.InputStream(channels=1,
                                   samplerate=samplerate,
                                   blocksize=self.chunk_size,
                                   device=device,
                                   latency='low') as stream:
                    self._stream = stream
                    print("✓ Audio stream opened successfully")
                    if self.on_status:
                        self.on_status("Microphone detector ready")
                    retry_count = 0  # Reset retry count on successful connection
                    
                    while self._running and not self._stop_event.is_set():
                        try:
                            # Read audio chunk
                            audio_data, overflow = stream.read(self.chunk_size)
                            
                            if overflow:
                                print(f"⚠️ Audio overflow detected")
                            
                            audio_chunk = audio_data.flatten()

                            # Emit raw peak level for GUI meter
                            if self.on_level:
                                try:
                                    self.on_level(float(np.max(np.abs(audio_chunk))))
                                except Exception:
                                    pass

                            # Detect impact
                            category = self._detect_impact(audio_chunk)
                            
                            if category and self.on_impact:
                                try:
                                    self.on_impact(category)
                                except Exception as e:
                                    print(f"Error in impact callback: {e}")
                        
                        except Exception as e:
                            print(f"Error reading audio: {e}")
                            time.sleep(0.01)
                
                # If we get here, stream closed normally
                self._stream = None
                break
            
            except Exception as e:
                print(f"Error opening audio stream: {e}")
                retry_count += 1
                
                if retry_count < max_retries:
                    print(f"Retrying... ({retry_count}/{max_retries})")
                    time.sleep(0.5)
                else:
                    print("Max retries reached. Stopping detector.")
                    self._running = False
                    if self.on_status:
                        self.on_status(
                            f"Microphone detector error: {e}. Check macOS Microphone permission and input device."
                        )
    
    def set_sensitivity(self, value: float):
        """Set sensitivity (0.5 to 3.0)"""
        self.sensitivity = max(0.5, min(3.0, value))
    
    def set_cooldown(self, value: float):
        """Set cooldown time (0.2 to 5.0 seconds)"""
        self.cooldown_time = max(0.2, min(5.0, value))

    def suppress_for(self, seconds: float):
        """Ignore microphone input while app audio is likely feeding back."""
        self._suppressed_until = max(self._suppressed_until, time.time() + max(0.0, seconds))
    
    def get_input_devices(self) -> list:
        """Get list of available input devices"""
        devices = sd.query_devices()
        input_devices = []
        
        if isinstance(devices, dict):
            devices = [devices]
        
        for i, device in enumerate(devices):
            if device.get('max_input_channels', 0) > 0:
                input_devices.append((i, device.get('name', f'Device {i}')))
        
        return input_devices
