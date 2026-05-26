# SlapMac — Impact Detector for MacBook

Slap your MacBook and let it respond. SlapMac listens via the internal microphone, detects chassis impacts, and plays sounds based on how hard you hit.

## Features

- Real-time microphone-based chassis impact detection
- Force classification: **weak / medium / strong / brutal**
- Custom sounds per category (WAV or MP3, drop-in replacement)
- Adjustable sensitivity, cooldown (up to 5 s), and output volume
- Three UI themes: Pink, Dark, Mint
- English / Russian / Japanese UI
- Impact log (last 20 hits)
- Test buttons for each sound category

## Requirements

- macOS 12 or later
- Python 3.11+
- Microphone permission granted to Terminal / the app

## Quick Start

**Double-click `SlapMac.command`** — it creates the virtual environment, installs dependencies, and launches the app automatically.

Or from the terminal:

```bash
cd slap_mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

## First Run on macOS (Gatekeeper)

macOS blocks unsigned scripts downloaded from the internet. Remove the quarantine flag once after cloning:

```bash
xattr -rd com.apple.quarantine slap_mac/
```

Then double-click `SlapMac.command` as usual. macOS will also ask for microphone permission on first launch — click **Allow**.

## Adding Your Own Sounds

Drop WAV or MP3 files into the matching folder:

```
sounds/
├── weak/      ← light tap sounds
├── medium/    ← medium hit sounds
├── strong/    ← hard hit sounds
└── brutal/    ← extreme sounds
```

Multiple files per category are supported — one is chosen at random on each hit.

## Settings

| Setting | Range | Default |
|---|---|---|
| Sensitivity | 0.5 – 3.0 | 1.0 |
| Cooldown | 0.2 – 5.0 s | 1.0 s |
| Output Volume | 0 – 100 % | 80 % |

Saved automatically to `config.json` (local, not tracked by git).

## Diagnostics

```bash
source venv/bin/activate
python3 diagnostics.py
```

Prints Python version, detected audio devices, sound library status, and accelerometer availability without opening the GUI.

## Running Tests

```bash
source venv/bin/activate
python3 -m unittest test_core -v
```

## Project Structure

```
slap_mac/
├── app.py               # Entry point
├── gui.py               # PyQt6 UI, themes, translations
├── detector.py          # Microphone onset detector
├── player.py            # Sound playback (afplay / pygame)
├── config.py            # Config load/save/validate
├── motion_detector.py   # CoreMotion accelerometer (optional)
├── motion_worker.py     # Subprocess wrapper for CoreMotion
├── diagnostics.py       # CLI environment checker
├── test_core.py         # Unit tests
├── requirements.txt
├── SlapMac.command      # Double-click launcher
├── SlapMac.app/         # macOS app bundle (launcher wrapper)
├── slapapp.png          # App icon source
└── sounds/              # Sound library
    ├── weak/
    ├── medium/
    ├── strong/
    └── brutal/
```

## Building a Standalone .app

```bash
chmod +x scripts/build_app.sh
./scripts/build_app.sh
# Result: dist/SlapMac.app
```

## Troubleshooting

**No sound playing**
- Confirm files exist in `sounds/<category>/`
- Use the test buttons in the UI to verify playback
- Check output volume is not at zero

**Not detecting hits**
- Click "Calibrate Sensor Baseline" in a quiet room
- Try increasing the sensitivity slider
- Hit the chassis (lower-left corner), not the keyboard

**Microphone access denied**
- System Settings → Privacy & Security → Microphone → allow Terminal or the app

## Dependencies

| Package | Purpose |
|---|---|
| PyQt6 | GUI |
| sounddevice | Microphone capture |
| numpy | Audio processing |
| pygame | Audio playback fallback |
| pyobjc-framework-CoreMotion | Accelerometer (optional) |

## License

MIT — see `LICENSE`.
