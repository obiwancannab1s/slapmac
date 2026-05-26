import sys
import shutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QTextEdit,
    QComboBox, QGroupBox, QGridLayout, QSystemTrayIcon, QMenu, QProgressBar,
    QDialog, QFileDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QAction

from config import Config, SOUNDS_DIR, validate_sounds_structure
from detector import AudioDetector
from motion_detector import MotionDetector, MOTION_ERROR, load_motion_detection
from player import AudioPlayer

TRANSLATIONS = {
    'en': {
        'app_title': 'SlapMac - Impact Detector',
        'settings': 'Settings',
        'sensitivity': 'Sensitivity:',
        'cooldown': 'Cooldown (sec):',
        'output_volume': 'Output Volume:',
        'sensor_mode': 'Sensor Mode:',
        'input_device': 'Input Device:',
        'default_input': 'Default Microphone',
        'active_sensor': 'Active Sensor:',
        'language': 'Language:',
        'controls': 'Controls',
        'start_listening': 'START LISTENING',
        'stop_listening': 'STOP LISTENING',
        'calibrate': '🧭 Calibrate Sensor Baseline',
        'test_sounds': 'Test Sounds',
        'impact_log': 'Impact Log (Last 20)',
        'clear_log': 'Clear Log',
        'ready': 'Ready',
        'auto': 'Auto',
        'accelerometer': 'Accelerometer',
        'microphone': 'Microphone',
        'accel_ready': '✓ Accelerometer detected and ready',
        'accel_unavailable': '⚠️ Accelerometer unavailable. Select Microphone or Auto mode.',
        'mic_selected': '✓ Microphone input selected',
        'auto_accel': '✓ Auto mode: accelerometer available',
        'auto_mic': '⚠️ Auto mode: accelerometer unavailable, microphone active.',
        'calibrating_baseline': 'Calibrating sensor baseline...',
        'listening': '✓ Listening for impacts...',
        'stopped': 'Stopped',
        'calibrating': 'Calibrating... Keep your MacBook quiet!',
        'calibration_complete': '✓ Calibration complete',
        'sensor_unavailable': '⚠️ Accelerometer unavailable; cannot calibrate',
        'color_theme': 'Color Theme',
        'custom_sounds': 'Custom Sounds',
        'add_sound': '＋ Add',
        'close': 'Close',
        'supported_formats': 'Supported formats: WAV, MP3\nNo file size limit',
        'category_weak': 'Weak',
        'category_medium': 'Medium',
        'category_strong': 'Strong',
        'category_brutal': 'Brutal',
    },
    'ru': {
        'app_title': 'SlapMac — Детектор удара',
        'settings': 'Настройки',
        'sensitivity': 'Чувствительность:',
        'cooldown': 'Откат (сек):',
        'output_volume': 'Громкость:',
        'sensor_mode': 'Режим датчика:',
        'input_device': 'Вход:',
        'default_input': 'Микрофон по умолчанию',
        'active_sensor': 'Активный датчик:',
        'language': 'Язык:',
        'controls': 'Управление',
        'start_listening': 'НАЧАТЬ СЛУШАТЬ',
        'stop_listening': 'ОСТАНОВИТЬ',
        'calibrate': '🧭 Калибровать датчик',
        'test_sounds': 'Тест звуков',
        'impact_log': 'Журнал ударов (последние 20)',
        'clear_log': 'Очистить журнал',
        'ready': 'Готово',
        'auto': 'Авто',
        'accelerometer': 'Акселерометр',
        'microphone': 'Микрофон',
        'accel_ready': '✓ Акселерометр доступен',
        'accel_unavailable': '⚠️ Акселерометр недоступен. Выберите Микрофон или Авто.',
        'mic_selected': '✓ Выбран микрофон',
        'auto_accel': '✓ Авто: акселерометр доступен',
        'auto_mic': '⚠️ Авто: акселерометр недоступен, активирован микрофон.',
        'calibrating_baseline': 'Калибруем датчик...',
        'listening': '✓ Слушаем удары...',
        'stopped': 'Остановлено',
        'calibrating': 'Калибруем... Держите MacBook в покое!',
        'calibration_complete': '✓ Калибровка завершена',
        'sensor_unavailable': '⚠️ Акселерометр недоступен; калибровка невозможна',
        'color_theme': 'Цветовая тема',
        'custom_sounds': 'Свои звуки',
        'add_sound': '＋ Добавить',
        'close': 'Закрыть',
        'supported_formats': 'Форматы: WAV, MP3\nОграничений по размеру нет',
        'category_weak': 'Слабый',
        'category_medium': 'Средний',
        'category_strong': 'Сильный',
        'category_brutal': 'Сокруш.',
    },
    'ja': {
        'app_title': 'SlapMac - 衝撃検出',
        'settings': '設定',
        'sensitivity': '感度:',
        'cooldown': 'クールダウン (秒):',
        'output_volume': '音量:',
        'sensor_mode': 'センサーモード:',
        'input_device': '入力デバイス:',
        'default_input': 'デフォルトマイク',
        'active_sensor': '使用中のセンサー:',
        'language': '言語:',
        'controls': 'コントロール',
        'start_listening': '再生開始',
        'stop_listening': '停止',
        'calibrate': '🧭 センサーをキャリブレーション',
        'test_sounds': 'サウンドテスト',
        'impact_log': '衝撃ログ（最新20件）',
        'clear_log': 'ログを消去',
        'ready': '準備完了',
        'auto': '自動',
        'accelerometer': '加速度計',
        'microphone': 'マイク',
        'accel_ready': '✓ 加速度計が使用可能です',
        'accel_unavailable': '⚠️ 加速度計が利用できません。マイクか自動を選択してください。',
        'mic_selected': '✓ マイク入力が選択されました',
        'auto_accel': '✓ 自動モード: 加速度計が使用可能',
        'auto_mic': '⚠️ 自動モード: 加速度計が利用できません。マイクを使用します。',
        'calibrating_baseline': 'センサー基準を調整しています...',
        'listening': '✓ 衝撃を検出中...',
        'stopped': '停止',
        'calibrating': 'キャリブレーション中... MacBookを静止させてください！',
        'calibration_complete': '✓ キャリブレーション完了',
        'sensor_unavailable': '⚠️ 加速度計が利用できません; キャリブレーションできません',
        'color_theme': 'カラーテーマ',
        'custom_sounds': 'カスタムサウンド',
        'add_sound': '＋ 追加',
        'close': '閉じる',
        'supported_formats': '対応形式: WAV, MP3\nサイズ制限なし',
        'category_weak': '弱',
        'category_medium': '中',
        'category_strong': '強',
        'category_brutal': '激烈',
    }
}

LANGUAGE_NAMES = {
    'en': 'English',
    'ru': 'Русский',
    'ja': '日本語'
}


def _theme(bg, card, accent, title_bg, title_color, label_color=None):
    """Return a complete Qt stylesheet string for the given theme colors."""
    if label_color is None:
        label_color = '#2a0815'
    return f"""
QWidget {{ background-color: {bg}; }}
QMainWindow {{ background-color: {bg}; }}
QDialog {{ background-color: {bg}; }}
QGroupBox {{
    background-color: {card};
    border: 1px solid rgba(100,10,40,0.14);
    border-bottom: 3px solid rgba(80,5,30,0.20);
    border-right: 2px solid rgba(90,8,35,0.14);
    border-radius: 16px;
    margin-top: 14px;
    padding: 8px 14px 14px 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 4px 12px;
    font-weight: 700;
    font-size: 10px;
    color: {title_color};
    letter-spacing: 0.8px;
    background: {title_bg};
    border-radius: 8px;
    border: 1px solid rgba(180,40,100,0.18);
}}
QPushButton {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {title_bg}, stop:1 {card});
    color: {title_color};
    padding: 9px 18px;
    border-radius: 22px;
    border: 1px solid rgba(160,30,85,0.28);
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {card}, stop:1 {title_bg});
    border: 1px solid rgba(200,50,110,0.45);
}}
QPushButton:checked {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {accent}, stop:1 {title_color});
    color: #ffffff;
    border: 1px solid {title_color};
}}
QPushButton:disabled {{
    background: #ede5e9;
    color: #b09098;
    border: 1px solid #d8cdd2;
}}
QLabel {{ color: {label_color}; font-size: 12px; font-weight: 600; }}
QSlider::groove:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {title_bg}, stop:1 {card});
    height: 8px;
    border-radius: 4px;
    border: 1px solid rgba(160,30,80,0.15);
}}
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {accent}, stop:1 {title_color});
    width: 22px;
    height: 22px;
    margin: -7px 0;
    border-radius: 11px;
    border: 2px solid rgba(255,255,255,0.88);
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {accent}, stop:1 {bg});
    border-radius: 4px;
}}
QTextEdit {{
    background: {card};
    border: 1px solid rgba(160,30,80,0.16);
    border-bottom: 2px solid rgba(120,15,55,0.16);
    color: {label_color};
    border-radius: 10px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 11px;
    padding: 6px 8px;
    selection-background-color: {title_bg};
}}
QComboBox {{
    background: {card};
    padding: 7px 12px;
    border: 1px solid rgba(160,30,80,0.22);
    border-bottom: 2px solid rgba(120,15,55,0.18);
    border-radius: 10px;
    color: {label_color};
    font-size: 12px;
}}
QComboBox:hover {{ border-color: rgba(200,50,110,0.45); }}
QComboBox::drop-down {{ border: none; padding-right: 10px; }}
QComboBox QAbstractItemView {{
    background: {card};
    color: {label_color};
    selection-background-color: {title_bg};
    border: 1px solid rgba(160,30,80,0.25);
    border-radius: 8px;
    padding: 4px;
}}
QProgressBar {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {title_bg}, stop:1 {card});
    border-radius: 6px;
    border: 1px solid rgba(160,30,80,0.16);
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #38d468, stop:0.55 #f09020, stop:1 #f02850);
    border-radius: 5px;
}}
QToolTip {{
    background: {card};
    color: {title_color};
    border: 1px solid rgba(160,30,80,0.28);
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 11px;
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: rgba(255,255,255,0.08);
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.28);
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
"""


THEMES = {
    'pink': _theme(
        bg='#b83262',
        card='#ffffff',
        accent='#e83880',
        title_bg='#fff0f6',
        title_color='#8c1040',
    ),
    'dark': _theme(
        bg='#0d0d1a',
        card='#1a1a2e',
        accent='#7c3aed',
        title_bg='#252545',
        title_color='#a080e0',
        label_color='#c8c0e8',
    ),
    'mint': _theme(
        bg='#0d7a8a',
        card='#f0fafc',
        accent='#00bfcc',
        title_bg='#b2edf2',
        title_color='#0a4858',
        label_color='#0a4858',
    ),
}

BADGE_STYLES = {
    'pink': 'background:#e0588a;color:#ffffff;border-radius:7px;padding:2px 10px;font-weight:700;font-size:11px;',
    'dark': 'background:rgba(100,80,180,0.40);color:#c8c0f8;border-radius:7px;padding:2px 10px;font-weight:700;font-size:11px;',
    'mint': 'background:#1a8fa0;color:#ffffff;border-radius:7px;padding:2px 10px;font-weight:700;font-size:11px;',
}


class DetectorSignals(QObject):
    """Signals for thread-safe communication from detector to GUI"""
    impact_detected = pyqtSignal(str)   # category name
    status_message = pyqtSignal(str)
    level_update = pyqtSignal(float)    # raw peak amplitude each audio chunk


detector_signals = DetectorSignals()


class SettingsDialog(QDialog):
    """Settings dialog for theme, language, and custom sounds."""

    def __init__(self, parent, config, player, sounds_dir):
        super().__init__(parent)
        self.config = config
        self.player = player
        self.sounds_dir = sounds_dir
        self._count_labels = {}
        self._parent = parent

        self.setWindowTitle("⚙  " + parent.tr('settings'))
        self.setModal(True)
        self.setMinimumWidth(440)

        badge_style = BADGE_STYLES.get(getattr(config, 'theme', 'pink'), BADGE_STYLES['pink'])

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Section 1 — Color Theme
        theme_group = QGroupBox(parent.tr('color_theme'))
        theme_layout = QHBoxLayout()
        for key, label in [('pink', '🌸 Pink'), ('dark', '🌑 Dark'), ('mint', '🌿 Mint')]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(getattr(self.config, 'theme', 'pink') == key)
            btn.clicked.connect(lambda checked, k=key: self._change_theme(k))
            theme_layout.addWidget(btn)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Section 2 — Language (close+reopen so dialog shows new language immediately)
        lang_group = QGroupBox(parent.tr('language'))
        lang_layout = QHBoxLayout()
        for code, label in [('en', 'English'), ('ru', 'Русский'), ('ja', '日本語')]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(self.config.language == code)
            btn.clicked.connect(lambda checked, c=code: self._change_lang(c))
            lang_layout.addWidget(btn)
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        # Section 3 — Custom Sounds
        sounds_group = QGroupBox(parent.tr('custom_sounds'))
        sounds_layout = QVBoxLayout()
        fmt_tip = parent.tr('supported_formats')
        for category in ['weak', 'medium', 'strong', 'brutal']:
            row = QHBoxLayout()

            cat_label = QLabel(parent.tr(f'category_{category}'))
            cat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cat_label.setStyleSheet(badge_style)
            cat_label.setFixedWidth(84)
            row.addWidget(cat_label)

            add_btn = QPushButton(parent.tr('add_sound'))
            add_btn.clicked.connect(lambda checked, cat=category: self._add_sound(cat))
            row.addWidget(add_btn)

            info_btn = QPushButton("?")
            info_btn.setFixedSize(22, 22)
            info_btn.setToolTip(fmt_tip)
            info_btn.setStyleSheet(
                "QPushButton { border-radius: 11px; font-size: 10px; padding: 0; font-weight: 700; }"
            )
            row.addWidget(info_btn)

            sounds_layout.addLayout(row)
        sounds_group.setLayout(sounds_layout)
        layout.addWidget(sounds_group)

        close_btn = QPushButton(parent.tr('close'))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def _change_theme(self, name: str):
        """Apply theme and reopen dialog so badge colours update immediately."""
        self._parent.apply_theme(name)
        self.reject()
        self._parent.open_settings()

    def _change_lang(self, code: str):
        """Change language and reopen dialog so all text is in the new language."""
        self._parent.set_language(code)
        self.reject()
        self._parent.open_settings()

    def _get_file_count(self, category: str) -> int:
        cat_dir = self.sounds_dir / category
        if not cat_dir.exists():
            return 0
        count = 0
        for ext in ['*.wav', '*.mp3', '*.WAV', '*.MP3']:
            count += len(list(cat_dir.glob(ext)))
        return count

    def _add_sound(self, category: str):
        cat_name = self._parent.tr(f'category_{category}')
        files, _ = QFileDialog.getOpenFileNames(
            self,
            f"{self._parent.tr('add_sound').replace('＋ ', '')} — {cat_name}",
            "",
            "Sound Files (*.wav *.mp3 *.WAV *.MP3)"
        )
        if not files:
            return
        cat_dir = self.sounds_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        for src in files:
            shutil.copy(src, cat_dir / Path(src).name)

        # Refresh player cache
        if hasattr(self.player, '_sounds_by_category'):
            self.player._sounds_by_category = None
        if hasattr(self.player, '_cache_wavs'):
            self.player._cache_wavs()


class SlapMacGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.config = Config.load()
        self.language = self.config.language if self.config.language in TRANSLATIONS else 'en'
        self.config.enabled = False
        self.detector = None
        self.active_detector_mode = None
        self._fallback_in_progress = False
        self._detector_generation = 0
        self._badge_labels = []
        self.motion_available = load_motion_detection()
        self.motion_error = MOTION_ERROR
        # Force microphone if accelerometer unavailable or mode is invalid
        if self.config.sensor_mode not in ('accelerometer', 'microphone'):
            self.config.sensor_mode = 'microphone'
            self.config.save()
        elif self.config.sensor_mode == 'accelerometer' and not self.motion_available:
            self.config.sensor_mode = 'microphone'
            self.config.save()
        self.player = AudioPlayer(SOUNDS_DIR, self.config.output_volume)
        self.impacts_log = []

        # Get current system mic gain before we change anything
        self._original_mic_gain = self._get_system_input_volume()

        detector_signals.impact_detected.connect(self.on_impact_detected)
        detector_signals.status_message.connect(self.on_detector_status)
        detector_signals.level_update.connect(self.on_level_update)

        self.init_ui()
        self.validate_sounds()

        self.check_sensor_access()
        # Create tray icon (if possible)
        try:
            self.create_tray_icon()
        except Exception:
            pass

    def tr(self, key: str) -> str:
        return TRANSLATIONS[self.language].get(key, key)

    def set_language(self, language_code: str):
        if language_code not in TRANSLATIONS:
            language_code = 'en'
        self.language = language_code
        self.config.language = language_code
        self.config.save()
        self.update_texts()

    def _badge(self, text: str) -> QLabel:
        """Create a badge-styled caption label and track it for theme updates."""
        lbl = QLabel(text)
        lbl.setStyleSheet(BADGE_STYLES.get(getattr(self.config, 'theme', 'pink'), BADGE_STYLES['pink']))
        self._badge_labels.append(lbl)
        return lbl

    def apply_theme(self, name: str):
        self.config.theme = name
        self.config.save()
        self.setStyleSheet(THEMES.get(name, THEMES['pink']))
        badge_style = BADGE_STYLES.get(name, BADGE_STYLES['pink'])
        for lbl in self._badge_labels:
            lbl.setStyleSheet(badge_style)

    def open_settings(self):
        dlg = SettingsDialog(self, self.config, self.player, SOUNDS_DIR)
        dlg.exec()

    def _get_system_input_volume(self) -> int:
        try:
            r = subprocess.run(
                ['osascript', '-e', 'input volume of (get volume settings)'],
                capture_output=True, text=True, timeout=1.0
            )
            return int(r.stdout.strip()) if r.returncode == 0 else 60
        except Exception:
            return 60

    def _set_system_input_volume(self, sensitivity: float):
        # sensitivity 0.5→3.0 maps to gain 15→100
        gain = min(100, max(5, int((sensitivity - 0.5) / 2.5 * 85 + 15)))
        try:
            subprocess.run(
                ['osascript', '-e', f'set volume input volume {gain}'],
                check=False, timeout=1.0, capture_output=True
            )
        except Exception:
            pass

    def update_texts(self):
        self.setWindowTitle(self.tr('app_title'))
        self.open_settings_btn.setText("⚙  " + self.tr('settings'))
        self.sensitivity_label_caption.setText(self.tr('sensitivity'))
        self.cooldown_label_caption.setText(self.tr('cooldown'))
        self.volume_label_caption.setText(self.tr('output_volume'))
        self.sensor_mode_caption.setText(self.tr('sensor_mode'))
        self.input_device_caption.setText(self.tr('input_device'))
        self.enable_button.setText(self.tr('stop_listening') if self.enable_button.isChecked() else self.tr('start_listening'))
        self.calibrate_button.setText(self.tr('calibrate'))
        self.log_group.setTitle(self.tr('impact_log'))
        self.clear_log_button.setText(self.tr('clear_log'))
        self.mic_button.setText(self.tr('microphone'))
        self.accel_button.setText(self.tr('accelerometer'))
        self.populate_input_devices()
        self.check_sensor_access()
        self.update_status()

    def create_tray_icon(self):
        """Create a system tray icon with show/quit menu."""
        app_icon = None
        try:
            root = Path(__file__).parent
            icns_path = root / 'SlapMac.app' / 'Contents' / 'Resources' / 'slapapp.icns'
            if icns_path.exists():
                app_icon = QIcon(str(icns_path))
        except Exception:
            app_icon = None

        if not app_icon or app_icon.isNull():
            return

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(app_icon)
        self.tray.setToolTip(self.tr('app_title'))

        menu = QMenu()
        show_action = QAction('Show')
        quit_action = QAction('Quit')
        show_action.triggered.connect(lambda: self.showNormal())
        quit_action.triggered.connect(lambda: QApplication.quit())
        menu.addAction(show_action)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle(self.tr('app_title'))
        icon_path = Path(__file__).parent / 'slapapp.png'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumWidth(480)
        self.setMinimumHeight(520)
        self.resize(540, 660)

        # Apply initial theme from config
        current_theme = getattr(self.config, 'theme', 'pink')
        self.setStyleSheet(THEMES.get(current_theme, THEMES['pink']))

        # Scroll area wrapping all content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setCentralWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        # ===== SETTINGS GROUP =====
        self.settings_group = QGroupBox("")
        settings_layout = QGridLayout()

        # Settings dialog opener — embossed full-width button at the top
        self.open_settings_btn = QPushButton("⚙  " + self.tr('settings'))
        self.open_settings_btn.clicked.connect(self.open_settings)
        settings_layout.addWidget(self.open_settings_btn, 0, 0, 1, 3)

        # Sensitivity
        self.sensitivity_label_caption = self._badge(self.tr('sensitivity'))
        settings_layout.addWidget(self.sensitivity_label_caption, 1, 0)
        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(50, 300)
        self.sensitivity_slider.setValue(int(self.config.sensitivity * 100))
        self.sensitivity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.sensitivity_slider.setTickInterval(10)
        self.sensitivity_slider.valueChanged.connect(self.on_sensitivity_changed)
        settings_layout.addWidget(self.sensitivity_slider, 1, 1)
        self.sensitivity_label = QLabel(f"{self.config.sensitivity:.1f}x")
        settings_layout.addWidget(self.sensitivity_label, 1, 2)

        # Cooldown
        self.cooldown_label_caption = self._badge(self.tr('cooldown'))
        settings_layout.addWidget(self.cooldown_label_caption, 2, 0)
        self.cooldown_slider = QSlider(Qt.Orientation.Horizontal)
        self.cooldown_slider.setRange(20, 500)
        self.cooldown_slider.setValue(int(self.config.cooldown * 100))
        self.cooldown_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.cooldown_slider.setTickInterval(10)
        self.cooldown_slider.valueChanged.connect(self.on_cooldown_changed)
        settings_layout.addWidget(self.cooldown_slider, 2, 1)
        self.cooldown_label = QLabel(f"{self.config.cooldown:.1f}s")
        settings_layout.addWidget(self.cooldown_label, 2, 2)

        # Output Volume
        self.volume_label_caption = self._badge(self.tr('output_volume'))
        settings_layout.addWidget(self.volume_label_caption, 3, 0)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.config.output_volume * 100))
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setTickInterval(10)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        settings_layout.addWidget(self.volume_slider, 3, 1)
        self.volume_label = QLabel(f"{self.config.output_volume:.0%}")
        settings_layout.addWidget(self.volume_label, 3, 2)

        # Sensor toggles
        self.sensor_mode_caption = self._badge(self.tr('sensor_mode'))
        settings_layout.addWidget(self.sensor_mode_caption, 4, 0)
        self.mic_button = QPushButton(self.tr('microphone'))
        self.mic_button.setCheckable(True)
        self.mic_button.clicked.connect(self.on_select_microphone)
        self.accel_button = QPushButton(self.tr('accelerometer'))
        self.accel_button.setCheckable(True)
        self.accel_button.clicked.connect(self.on_select_accelerometer)
        sensor_toggle_layout = QHBoxLayout()
        sensor_toggle_layout.addWidget(self.mic_button)
        sensor_toggle_layout.addWidget(self.accel_button)
        settings_layout.addLayout(sensor_toggle_layout, 4, 1, 1, 2)

        self.input_device_caption = self._badge(self.tr('input_device'))
        settings_layout.addWidget(self.input_device_caption, 5, 0)
        self.input_device_combo = QComboBox()
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)
        settings_layout.addWidget(self.input_device_combo, 5, 1, 1, 2)

        self.mic_button.setChecked(self.config.sensor_mode != 'accelerometer')
        self.accel_button.setChecked(self.config.sensor_mode == 'accelerometer')
        self.accel_button.setEnabled(True)

        settings_layout.setContentsMargins(8, 4, 8, 6)
        settings_layout.setSpacing(4)
        self.settings_group.setLayout(settings_layout)
        main_layout.addWidget(self.settings_group)

        # ===== CONTROLS GROUP =====
        self.controls_group = QGroupBox("")
        controls_layout = QVBoxLayout()

        self.enable_button = QPushButton(self.tr('start_listening'))
        self.enable_button.setCheckable(True)
        self.enable_button.setChecked(False)
        self.enable_button.clicked.connect(self.on_enable_toggle)
        self.enable_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #48d860, stop:1 #2ea848);
                color: white; font-weight: 800; font-size: 13px;
                padding: 9px; border-radius: 22px;
                border: 1px solid #1e8030; letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #5ef078, stop:1 #3abc58);
            }
            QPushButton:checked {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #f04040, stop:1 #c01818);
                border: 1px solid #900808;
            }
            QPushButton:checked:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #f86060, stop:1 #d02828);
            }
        """)
        controls_layout.addWidget(self.enable_button)

        self.calibrate_button = QPushButton(self.tr('calibrate'))
        self.calibrate_button.clicked.connect(self.on_calibrate)
        self.calibrate_button.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 11px; border-radius: 16px; }"
        )
        controls_layout.addWidget(self.calibrate_button)

        controls_layout.setSpacing(5)
        controls_layout.setContentsMargins(8, 4, 8, 6)
        self.controls_group.setLayout(controls_layout)
        main_layout.addWidget(self.controls_group)

        # ===== TEST BUTTONS =====
        self.test_group = QGroupBox("")
        test_layout = QHBoxLayout()
        test_layout.setContentsMargins(8, 4, 8, 6)
        test_layout.setSpacing(5)

        for category in ['weak', 'medium', 'strong', 'brutal']:
            btn = QPushButton(f"▶ {category.capitalize()}")
            btn.setStyleSheet(
                "QPushButton { padding: 4px 6px; font-size: 11px; border-radius: 14px; }"
            )
            btn.clicked.connect(lambda checked, cat=category: self.on_test_sound_clicked(cat))
            test_layout.addWidget(btn)

        self.test_group.setLayout(test_layout)
        main_layout.addWidget(self.test_group)

        # ===== MIC LEVEL METER =====
        level_row = QHBoxLayout()
        level_row.setContentsMargins(4, 0, 4, 0)
        self.level_label = QLabel("MIC")
        self.level_label.setFixedWidth(34)
        self.level_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        level_row.addWidget(self.level_label)
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(10)
        self.level_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(0,0,0,0.28);
                border-radius: 5px;
                border: 1px solid rgba(255,255,255,0.12);
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #38d468, stop:0.55 #f09020, stop:1 #f02850);
                border-radius: 4px;
            }
        """)
        level_row.addWidget(self.level_bar)

        # Impact flash — lights up in category color on each detection
        self.impact_flash = QLabel("●")
        self.impact_flash.setFixedWidth(22)
        self.impact_flash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.impact_flash.setStyleSheet("color: rgba(255,255,255,0.18); font-size: 15px;")
        level_row.addWidget(self.impact_flash)

        main_layout.addLayout(level_row)

        # ===== LOG GROUP =====
        self.log_group = QGroupBox(self.tr('impact_log'))
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        self.log_text.setMaximumHeight(300)
        self.log_text.setStyleSheet("")
        log_layout.addWidget(self.log_text)

        self.clear_log_button = QPushButton(self.tr('clear_log'))
        self.clear_log_button.clicked.connect(self.clear_log)
        log_layout.addWidget(self.clear_log_button)

        self.log_group.setLayout(log_layout)
        main_layout.addWidget(self.log_group)

        # ===== STATUS =====
        self.status_label = QLabel(self.tr('ready'))
        self.status_label.setStyleSheet(
            "color: rgba(255,255,255,0.92); font-size: 11px; font-weight: 700;"
        )
        main_layout.addWidget(self.status_label)

        # ===== VERSION LABEL =====
        version_label = QLabel("v1.0")
        version_label.setStyleSheet(
            "color: rgba(255,255,255,0.28); font-size: 9px; qproperty-alignment: AlignCenter;"
        )
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(version_label)

        content_widget.setLayout(main_layout)

        # Update status periodically
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

        self.update_texts()

    def populate_input_devices(self):
        """Refresh the microphone input device selector."""
        if not hasattr(self, 'input_device_combo'):
            return

        self.input_device_combo.blockSignals(True)
        self.input_device_combo.clear()
        self.input_device_combo.addItem(self.tr('default_input'), -1)

        try:
            for device_id, name in AudioDetector().get_input_devices():
                self.input_device_combo.addItem(f"[{device_id}] {name}", device_id)
        except Exception as e:
            self.input_device_combo.addItem(f"No devices visible ({e})", -1)

        current_index = 0
        for idx in range(self.input_device_combo.count()):
            if self.input_device_combo.itemData(idx) == self.config.input_device:
                current_index = idx
                break
        self.input_device_combo.setCurrentIndex(current_index)
        self.input_device_combo.blockSignals(False)

    def validate_sounds(self):
        """Check if sound files exist"""
        status = validate_sounds_structure()

        missing = [cat for cat, count in status.items() if count == 0]
        if missing:
            msg = f"⚠️ No sounds found in: {', '.join(missing)}\nPlace WAV/MP3 files in sounds/<category>/"
            self.update_status(msg)

    def check_sensor_access(self):
        """Check whether motion detection is available and update buttons."""
        if self.motion_available:
            self.accel_button.setEnabled(True)
            self.accel_button.setToolTip("")
        else:
            self.accel_button.setEnabled(False)
            self.accel_button.setToolTip(self.tr('accel_unavailable'))

        if self.config.sensor_mode == 'accelerometer' and self.motion_available:
            self.mic_button.setChecked(False)
            self.accel_button.setChecked(True)
            self.input_device_combo.setEnabled(False)
            self.update_status(self.tr('accel_ready'))
        else:
            self.mic_button.setChecked(True)
            self.accel_button.setChecked(False)
            self.input_device_combo.setEnabled(True)
            self.update_status(self.tr('mic_selected'))

    @pyqtSlot()
    def on_enable_toggle(self):
        """Toggle detector on/off"""
        if self.enable_button.isChecked():
            self.start_detector()
        else:
            self.stop_detector()

        self.config.enabled = self.enable_button.isChecked()
        self.config.save()

    def start_detector(self):
        """Start the impact detector"""
        self._start_detector_with_mode(self.config.sensor_mode)

    def _start_detector_with_mode(self, mode: str):
        """Start the impact detector with an explicit backend mode."""
        self._detector_generation += 1
        gen = self._detector_generation

        def _start():
            try:
                use_motion = mode == 'accelerometer'

                if use_motion:
                    detector = MotionDetector(
                        on_impact=lambda category: detector_signals.impact_detected.emit(category),
                        on_status=lambda message: detector_signals.status_message.emit(message),
                    )
                else:
                    detector = AudioDetector(
                        on_impact=lambda category: detector_signals.impact_detected.emit(category),
                        on_status=lambda message: detector_signals.status_message.emit(message),
                        on_level=lambda v: detector_signals.level_update.emit(v),
                    )

                detector.set_sensitivity(self.config.sensitivity)
                detector.set_cooldown(self.config.cooldown)

                detector_signals.status_message.emit(self.tr('calibrating_baseline'))
                if use_motion:
                    detector.calibrate(duration=1.0)
                else:
                    detector.calibrate(duration=0.6, input_device=self.config.input_device)

                # Stop if superseded by a newer start/stop call
                if gen != self._detector_generation:
                    detector.stop()
                    return

                self.detector = detector
                self.active_detector_mode = mode

                if use_motion:
                    detector.start()
                else:
                    detector.start(input_device=self.config.input_device)

                detector_signals.status_message.emit(self.tr('listening'))

            except Exception as e:
                detector_signals.status_message.emit(f"Error starting detector: {e}")

        t = threading.Thread(target=_start, daemon=True)
        t.start()

    def stop_detector(self):
        """Stop the impact detector"""
        self._detector_generation += 1
        self._fallback_in_progress = False
        if self.detector:
            self.detector.stop()
            self.detector = None
        self.active_detector_mode = None

        self.player.stop_current()
        self.level_bar.setValue(0)
        self.enable_button.setText(self.tr('start_listening'))
        self.update_status(self.tr('stopped'))

    _CATEGORY_COLORS = {
        'weak':   '#38d468',
        'medium': '#f09020',
        'strong': '#f04840',
        'brutal': '#c820f0',
    }

    @pyqtSlot(str)
    def on_impact_detected(self, category: str):
        """Handle detected impact - play sound for any detection"""
        if category not in ('weak', 'medium', 'strong', 'brutal'):
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.impacts_log.append((timestamp, category))
        if len(self.impacts_log) > 20:
            self.impacts_log.pop(0)

        self.update_log()

        # Flash the indicator dot in category color, then fade back
        color = self._CATEGORY_COLORS.get(category, '#ffffff')
        self.impact_flash.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;"
        )
        QTimer.singleShot(700, lambda: self.impact_flash.setStyleSheet(
            "color: rgba(255,255,255,0.18); font-size: 15px;"
        ))

        duration = self.player.play_random_sound(category) or 1.0
        if self.detector and hasattr(self.detector, 'suppress_for'):
            self.detector.suppress_for(min(2.5, duration + 0.35))

    def on_test_sound_clicked(self, category: str):
        """Play a manual test sound without letting it retrigger the microphone detector."""
        duration = self.player.play_random_sound(category) or 1.0
        if self.detector and hasattr(self.detector, 'suppress_for'):
            self.detector.suppress_for(min(2.5, duration + 0.35))

    @pyqtSlot(str)
    def on_detector_status(self, message: str):
        """Handle status/error messages from background detectors."""
        self.update_status(message)
        failed = "stopped unexpectedly" in message or "error" in message.lower() or "unavailable" in message.lower()
        if not failed:
            if message == self.tr('listening') or "ready" in message.lower():
                self.enable_button.setText(self.tr('stop_listening'))
            return

        if self.active_detector_mode == 'accelerometer' and not self._fallback_in_progress:
            self._fallback_in_progress = True
            self.update_status(f"{message}; falling back to microphone")
            if self.detector:
                self.detector.stop()
                self.detector = None
            self.active_detector_mode = None
            # Update sensor toggle buttons to reflect microphone is now active
            self.mic_button.setChecked(True)
            self.accel_button.setChecked(False)
            self.input_device_combo.setEnabled(True)
            self.enable_button.setChecked(True)
            self.enable_button.setText(self.tr('stop_listening'))
            self._start_detector_with_mode('microphone')
            return

        self.enable_button.setChecked(False)
        self.enable_button.setText(self.tr('start_listening'))
        self.active_detector_mode = None
        self.detector = None
        self.config.enabled = False
        self.config.save()

    @pyqtSlot(float)
    def on_level_update(self, peak: float):
        """Update mic level bar (called ~86 times/sec from audio thread via signal)."""
        self.level_bar.setValue(min(100, int(peak * 450)))

    def update_log(self):
        lines = []
        for ts, cat in self.impacts_log:
            color = self._CATEGORY_COLORS.get(cat, '#350d1e')
            lines.append(
                f'<span style="color:#c090a8;font-size:10px">{ts}</span>'
                f'&nbsp;→&nbsp;'
                f'<span style="color:{color};font-weight:700;font-size:12px">{cat.upper()}</span>'
            )
        self.log_text.setHtml('<br>'.join(lines))

    def clear_log(self):
        """Clear impact log"""
        self.impacts_log.clear()
        self.log_text.setText("")

    @pyqtSlot(int)
    def on_sensitivity_changed(self, val):
        """Handle sensitivity slider change"""
        value = val / 100.0
        self.config.sensitivity = value
        self.sensitivity_label.setText(f"{value:.1f}x")

        if self.detector:
            self.detector.set_sensitivity(value)

        self._set_system_input_volume(value)
        self.config.save()

    @pyqtSlot(int)
    def on_cooldown_changed(self, val):
        """Handle cooldown slider change"""
        value = val / 100.0
        self.config.cooldown = value
        self.cooldown_label.setText(f"{value:.1f}s")

        if self.detector:
            self.detector.set_cooldown(value)

        self.config.save()

    @pyqtSlot(int)
    def on_volume_changed(self, val):
        """Handle volume slider change"""
        value = val / 100.0
        self.config.output_volume = value
        self.volume_label.setText(f"{value:.0%}")
        self.player.set_volume(value)
        self.config.save()

    @pyqtSlot(int)
    def on_input_device_changed(self, index):
        """Persist selected microphone input device."""
        if not hasattr(self, 'input_device_combo') or index < 0:
            return

        device_id = self.input_device_combo.itemData(index)
        if device_id is None:
            return

        self.config.input_device = int(device_id)
        self.config.save()
        if self.config.sensor_mode == 'microphone':
            self.update_status(self.tr('mic_selected'))
            if self.enable_button.isChecked():
                self.stop_detector()
                self.enable_button.setChecked(True)
                self._start_detector_with_mode('microphone')

    def on_select_microphone(self):
        """Select microphone sensor mode"""
        self.config.sensor_mode = 'microphone'
        self.config.save()
        self.mic_button.setChecked(True)
        self.accel_button.setChecked(False)
        self.accel_button.setEnabled(self.motion_available)
        self.update_status(self.tr('mic_selected'))
        if self.enable_button.isChecked():
            self.stop_detector()
            self.enable_button.setChecked(True)
            self._start_detector_with_mode('microphone')

    def on_select_accelerometer(self):
        """Select accelerometer sensor mode if available"""
        if not self.motion_available:
            self.accel_button.setChecked(False)
            self.update_status(self.tr('accel_unavailable'))
            return

        self.config.sensor_mode = 'accelerometer'
        self.config.save()
        self.mic_button.setChecked(False)
        self.accel_button.setChecked(True)
        self.input_device_combo.setEnabled(False)
        self.update_status(self.tr('accel_ready'))
        if self.enable_button.isChecked():
            self.stop_detector()
            self.enable_button.setChecked(True)
            self._start_detector_with_mode('accelerometer')

    @pyqtSlot()
    def on_calibrate(self):
        """Manually calibrate sensor baseline"""
        import threading
        self.update_status(self.tr('calibrating'))

        def _do_calibrate():
            try:
                if self.config.sensor_mode == 'accelerometer':
                    if not load_motion_detection():
                        raise RuntimeError(MOTION_ERROR)
                    detector = MotionDetector()
                    detector.calibrate(duration=1.0)
                    self.motion_available = True
                else:
                    detector = AudioDetector()
                    detector.calibrate(duration=0.6, input_device=self.config.input_device)
                msg = self.tr('calibration_complete')
            except Exception:
                msg = self.tr('sensor_unavailable')

            detector_signals.status_message.emit(msg)

        t = threading.Thread(target=_do_calibrate, daemon=True)
        t.start()

    @pyqtSlot()
    def on_detect_motion(self):
        """Re-check CoreMotion availability and update UI."""
        self.update_status('Checking accelerometer...')
        has = load_motion_detection()
        self.motion_available = has
        if has:
            self.update_status(self.tr('accel_ready'))
        else:
            self.update_status(self.tr('accel_unavailable'))
        self.update_texts()

    def update_status(self, message: str = ""):
        """Update status label"""
        if message:
            self.status_label.setText(message)
        else:
            current = self.status_label.text()
            if not self.enable_button.isChecked() and (
                "unexpectedly" in current or "Error" in current or "unavailable" in current
            ):
                return
            if self.enable_button.isChecked():
                impacts = len(self.impacts_log)
                mode = self.active_detector_mode or self.config.sensor_mode
                icon = "🎤" if mode == 'microphone' else "📡"
                self.status_label.setText(f"✓ {icon} Listening | Detections: {impacts}")
            else:
                self.status_label.setText("")

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_initially_centered'):
            self._initially_centered = True
            screen_geo = QApplication.primaryScreen().availableGeometry()
            frame = self.frameGeometry()
            frame.moveCenter(screen_geo.center())
            top_left = frame.topLeft()
            if top_left.y() < screen_geo.y() + 4:
                top_left.setY(screen_geo.y() + 4)
            self.move(top_left)

    def closeEvent(self, event):
        """Handle window close"""
        try:
            subprocess.run(
                ['osascript', '-e', f'set volume input volume {self._original_mic_gain}'],
                check=False, timeout=1.0, capture_output=True
            )
        except Exception:
            pass
        self.stop_detector()
        try:
            self.player.shutdown()
        except Exception:
            pass
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SlapMacGUI()
    window.show()
    sys.exit(app.exec())
