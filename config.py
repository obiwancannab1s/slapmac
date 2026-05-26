import json
from pathlib import Path
from dataclasses import dataclass, asdict

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
SOUNDS_DIR = BASE_DIR / "sounds"


@dataclass
class Config:
    """Application configuration"""
    sensitivity: float = 1.3  # 0.5 to 3.0
    cooldown: float = 1.0  # 0.2 to 2.0 seconds
    output_volume: float = 0.8  # 0.0 to 1.0
    input_device: int = -1  # -1 for default
    sensor_mode: str = "microphone"  # microphone, accelerometer
    language: str = "en"  # en, ru, ja
    theme: str = "pink"   # pink, dark, mint
    enabled: bool = False
    
    def save(self):
        """Save config to JSON file"""
        tmp_file = CONFIG_FILE.with_suffix(".json.tmp")
        with open(tmp_file, 'w') as f:
            json.dump(asdict(self), f, indent=2)
        tmp_file.replace(CONFIG_FILE)

    def normalize(self):
        """Clamp user-editable values and repair stale config files."""
        self.sensitivity = max(0.5, min(3.0, float(self.sensitivity)))
        self.cooldown = max(0.2, min(2.0, float(self.cooldown)))
        self.output_volume = max(0.0, min(1.0, float(self.output_volume)))
        self.input_device = int(self.input_device)
        if self.sensor_mode not in ("microphone", "accelerometer"):
            self.sensor_mode = "microphone"
        if self.language not in ("en", "ru", "ja"):
            self.language = "en"
        if self.theme not in ("pink", "dark", "mint"):
            self.theme = "pink"
        self.enabled = bool(self.enabled)
        return self
    
    @classmethod
    def load(cls):
        """Load config from JSON file or create default"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                allowed = {field: data[field] for field in cls.__dataclass_fields__ if field in data}
                return cls(**allowed).normalize()
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
                return cls()
        return cls().normalize()


def get_sound_files(category: str) -> list:
    """Get list of sound files for a category (weak, medium, strong, brutal)"""
    category_dir = SOUNDS_DIR / category
    if not category_dir.exists():
        return []
    
    sound_files = []
    for ext in ['*.wav', '*.mp3', '*.WAV', '*.MP3']:
        sound_files.extend(sorted(category_dir.glob(ext)))
    
    return sound_files


def validate_sounds_structure() -> dict:
    """Validate that sounds directories have at least one file"""
    categories = ['weak', 'medium', 'strong', 'brutal']
    status = {}
    
    for cat in categories:
        files = get_sound_files(cat)
        status[cat] = len(files)
    
    return status
