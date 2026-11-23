import ctypes
import json
import sys
import time
import winreg
from pathlib import Path

import emoji
import keyboard
import pyperclip
import uiautomation as auto
from PyQt6.QtCore import QEvent, QMimeData, QObject, QPoint, QEasingCurve, QPropertyAnimation, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QDrag, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Win32 constants/helpers
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

APP_VERSION = "1.39"
HISTORY_PATH = Path.home() / ".eptal_emoji_history.json"
STATE_PATH = Path.home() / ".eptal_emoji_state.json"
CUSTOM_PATH = Path.home() / ".eptal_emoji_custom.json"
MAX_HISTORY = 30

CATEGORY_MAP = {
    "Faces": {"Smileys & Emotion", "People & Body"},
    "Nature/Food": {"Animals & Nature", "Food & Drink", "Travel & Places"},
    "Symbols": {"Activities", "Objects", "Symbols"},
}


class SignalBridge(QObject):
    show_picker = pyqtSignal(int)
    hotkey_pressed = pyqtSignal()


class FocusWatcher(QThread):
    focus_text_input = pyqtSignal(int)

    def __init__(self, bridge: SignalBridge):
        super().__init__()
        self._running = True
        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def stop(self):
        self._running = False

    def run(self):
        try:
            ctypes.windll.ole32.CoInitialize(0)
        except Exception:
            pass
        last_key = None
        while self._running:
            try:
                if not self._enabled:
                    last_key = None
                    time.sleep(0.25)
                    continue
                control = auto.GetFocusedControl()
                if control and self._is_text_control(control):
                    try:
                        hwnd = int(getattr(control, "NativeWindowHandle", 0) or 0)
                    except Exception:
                        hwnd = 0
                    try:
                        key = (
                            control.ControlTypeName,
                            getattr(control, "ClassName", ""),
                            getattr(control, "AutomationId", ""),
                            hwnd,
                        )
                    except Exception:
                        key = (id(control),)
                    if key != last_key:
                        last_key = key
                        self.focus_text_input.emit(hwnd)
                else:
                    last_key = None
            except Exception:
                pass
            time.sleep(0.2)
        try:
            ctypes.windll.ole32.CoUninitialize()
        except Exception:
            pass

    @staticmethod
    def _is_text_control(control) -> bool:
        try:
            ctype = control.ControlTypeName
            if ctype in ("EditControl", "DocumentControl"):
                return True
            if ctype == "ComboBoxControl":
                try:
                    if control.GetValuePattern() is not None:
                        return True
                except Exception:
                    return False
            try:
                if control.GetTextPattern() is not None and ctype not in (
                    "ButtonControl",
                    "ListItemControl",
                    "TreeItemControl",
                    "HyperlinkControl",
                ):
                    return True
            except Exception:
                pass
            try:
                if control.GetValuePattern() is not None and ctype not in (
                    "ButtonControl",
                    "ListItemControl",
                    "TreeItemControl",
                    "HyperlinkControl",
                ):
                    return True
            except Exception:
                pass
        except Exception:
            return False
        return False


def load_history():
    try:
        if HISTORY_PATH.exists():
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [x for x in data if isinstance(x, str)][:MAX_HISTORY]
    except Exception:
        pass
    return []


def save_history(items):
    try:
        HISTORY_PATH.write_text(
            json.dumps(items[:MAX_HISTORY], ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def load_state():
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_state(data):
    try:
        STATE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_custom():
    # Загружает список своих смайликов
    try:
        if CUSTOM_PATH.exists():
            data = json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data if isinstance(x, str) and x]
    except Exception:
        pass
    return []


def save_custom(items):
    # Сохраняет список своих смайликов
    try:
        CUSTOM_PATH.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_category_overrides():
    # Загружает переопределения категорий для смайликов
    try:
        st = load_state()
        data = st.get("emoji_category_overrides", {})
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception:
        pass
    return {}


def save_category_overrides(overrides):
    # Сохраняет переопределения категорий для смайликов
    try:
        st = load_state()
        st["emoji_category_overrides"] = overrides
        save_state(st)
    except Exception:
        pass


def make_emoji_entry(ch: str, custom: bool = False):
    # Создаёт запись эмодзи для отображения в сетке
    data = emoji.EMOJI_DATA.get(ch, {}) if isinstance(ch, str) else {}
    en = (data.get("en") or "").strip(":")
    ru = (data.get("ru") or "").strip(":")
    aliases = data.get("alias") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    alias_text = " ".join(a.strip(":") for a in aliases)
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tag_text = " ".join(str(t) for t in tags)
    search_blob = " ".join([en, ru, alias_text, tag_text, ch]).lower()
    group = categorize_emoji(ch, en) if en else "Faces"
    if not en:
        # Для неизвестных эмодзи задаём базовые значения, чтобы они попадали в поиск/категории
        en = "custom emoji"
        ru = "свой смайлик"
        search_blob = " ".join([en, ru, ch]).lower()
        group = "Faces"
    entry = {
        "char": ch,
        "group": group,
        "en": en,
        "ru": ru,
        "search": search_blob,
    }
    if custom:
        entry["custom"] = True
    return entry


def extract_emojis_from_text(text: str):
    # Извлекает эмодзи из текста (вставленных пользователем)
    if not text:
        return []
    result = []
    try:
        # Предпочтительно: получить эмодзи через библиотеку emoji
        if hasattr(emoji, "emoji_list"):
            items = emoji.emoji_list(text)
            for it in items:
                ch = it.get("emoji")
                if ch:
                    result.append(ch)
            if result:
                return result
        if hasattr(emoji, "distinct_emoji_list"):
            result = list(emoji.distinct_emoji_list(text))
            if result:
                return result
    except Exception:
        pass
    # Запасной вариант: посимвольный разбор с учётом последовательностей
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # Пропускаем пробелы и управляющие символы
        if ch.isspace() or ord(ch) < 0x200:
            i += 1
            continue
        # Пытаемся собрать последовательность эмодзи (ZWJ/variation selectors/skin tones)
        seq = ch
        j = i + 1
        while j < n:
            c = text[j]
            o = ord(c)
            if c == "\u200d" or c == "\ufe0f" or c == "\ufe0e" or (0x1F3FB <= o <= 0x1F3FF):
                seq += c
                j += 1
                # Если был ZWJ, захватываем следующий символ как часть последовательности
                if c == "\u200d" and j < n:
                    seq += text[j]
                    j += 1
                continue
            # Региональные индикаторы (флаги)
            if 0x1F1E6 <= ord(seq[0]) <= 0x1F1FF and 0x1F1E6 <= o <= 0x1F1FF and len(seq) == 1:
                seq += c
                j += 1
                continue
            break
        # Добавляем, если похоже на эмодзи/символ вне ASCII
        if ord(seq[0]) >= 0x200 or seq in emoji.EMOJI_DATA:
            result.append(seq)
        i = j if j > i else i + 1
    return result


def merge_custom_entries(entries, custom_chars):
    # Добавляет свои смайлики в общий список записей
    if not custom_chars:
        return entries
    by_char = {e.get("char"): e for e in entries}
    for ch in custom_chars:
        if not ch:
            continue
        if ch in by_char:
            # Если смайлик уже есть во встроенном наборе, помечаем его как добавленный
            by_char[ch]["custom"] = True
            continue
        entry = make_emoji_entry(ch, custom=True)
        entries.append(entry)
        by_char[ch] = entry
    return entries

def categorize_emoji(ch: str, name: str) -> str:
    """Эвристическая категория для UI-вкладок."""
    cp = ord(ch[0]) if ch else 0
    n = name.lower()

    # Флаги (региональные индикаторы) — показываем в "Symbols"
    if 0x1F1E6 <= cp <= 0x1F1FF or "flag" in n:
        return "Symbols"

    # Смайлы и люди
    if 0x1F600 <= cp <= 0x1F64F or 0x1F900 <= cp <= 0x1F9FF or 0x1FAE0 <= cp <= 0x1FAFF:
        if any(k in n for k in ["animal", "bird", "bug", "cat", "dog", "monkey", "insect", "paw", "horse", "fish", "whale", "dolphin", "plant", "flower", "tree", "leaf"]):
            return "Nature/Food"
        if any(k in n for k in ["food", "drink", "fruit", "vegetable", "pizza", "burger", "cake", "coffee", "tea", "beer", "wine", "sushi", "bread", "meat"]):
            return "Nature/Food"
        if any(k in n for k in ["car", "bus", "train", "plane", "ship", "boat", "bike", "rocket", "building", "house", "mountain", "beach", "map", "travel"]):
            return "Nature/Food"
        return "Faces"
    if 0x2600 <= cp <= 0x27BF:
        if any(k in n for k in ["sun", "cloud", "rain", "snow", "star", "moon", "flower", "tree", "plant", "animal"]):
            return "Nature/Food"
        return "Symbols"
    if 0x1F300 <= cp <= 0x1F5FF:
        if any(k in n for k in ["food", "drink", "fruit", "vegetable", "pizza", "burger", "cake", "coffee", "tea", "beer", "wine", "sushi", "bread", "meat", "egg", "rice"]):
            return "Nature/Food"
        if any(k in n for k in ["animal", "dog", "cat", "monkey", "bird", "fish", "whale", "bug", "insect", "flower", "tree", "plant", "seedling", "leaves", "herb"]):
            return "Nature/Food"
        if any(k in n for k in ["car", "bus", "train", "plane", "ship", "boat", "bike", "taxi", "rocket", "building", "house", "hotel", "church", "mountain", "beach", "sunrise", "sunset", "city", "map", "globe"]):
            return "Nature/Food"
        return "Symbols"
    if 0x1F680 <= cp <= 0x1F6FF:
        return "Nature/Food"
    if 0x1F700 <= cp <= 0x1F77F or 0x1F780 <= cp <= 0x1F7FF or 0x1F800 <= cp <= 0x1F8FF:
        return "Symbols"
    if cp <= 0x2BFF:
        return "Symbols"
    return "Symbols"


def build_emoji_entries():
    entries = []
    for ch, data in emoji.EMOJI_DATA.items():
        status = data.get("status")
        if status and status != emoji.STATUS["fully_qualified"]:
            continue
        # Убираем варианты с модификаторами тона кожи (оставляем только жёлтые/базовые)
        if any("\U0001F3FB" <= c <= "\U0001F3FF" for c in ch):
            continue
        en = (data.get("en") or "").strip(":")
        # Убираем флаги и связанные с ними эмодзи
        cp0 = ord(ch[0]) if ch else 0
        if 0x1F1E6 <= cp0 <= 0x1F1FF or "flag" in en.lower():
            continue
        ru = (data.get("ru") or "").strip(":")
        aliases = data.get("alias") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        alias_text = " ".join(a.strip(":") for a in aliases)
        tags = data.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        tag_text = " ".join(str(t) for t in tags)
        search_blob = " ".join([en, ru, alias_text, tag_text, ch]).lower()
        group = categorize_emoji(ch, en)
        entries.append(
            {
                "char": ch,
                "group": group,
                "en": en,
                "ru": ru,
                "search": search_blob,
            }
        )
    # стабильный порядок
    entries.sort(key=lambda x: (x["group"], x["en"], x["char"]))
    return entries


class AddEmojiDialog(QDialog):
    def __init__(self, custom_chars, on_changed, parent=None):
        super().__init__(None)
        self.setWindowTitle("Добавить смайлики")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.resize(420, 360)
        self.custom_chars = custom_chars
        self.on_changed = on_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel("Вставьте сюда смайлики (один или несколько), затем нажмите \"Добавить\".\nКликните два раза левой кнопкой мыши по полю ввода, чтобы быстро выделить слово.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Например: 😀 😅 🙃")
        self.input_edit.setFixedHeight(70)
        layout.addWidget(self.input_edit)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_from_input)
        btn_row.addWidget(self.add_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        list_label = QLabel("Добавленные смайлики:")
        layout.addWidget(list_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        actions_row = QHBoxLayout()
        self.remove_btn = QPushButton("Удалить выбранные")
        self.remove_btn.clicked.connect(self.remove_selected)
        actions_row.addWidget(self.remove_btn)
        actions_row.addStretch(1)
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close)
        actions_row.addWidget(self.close_btn)
        layout.addLayout(actions_row)

        self.refresh_list()

    def refresh_list(self):
        # Обновляет список своих смайликов в диалоге
        self.list_widget.clear()
        for ch in self.custom_chars:
            self.list_widget.addItem(ch)

    def add_from_input(self):
        # Добавляет смайлики из поля ввода
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        chars = extract_emojis_from_text(text)
        if not chars:
            QMessageBox.information(self, "Смайлики", "Не удалось найти смайлики во вставленном тексте.")
            return
        existing = set(self.custom_chars)
        added = 0
        for ch in chars:
            if ch and ch not in existing:
                self.custom_chars.append(ch)
                existing.add(ch)
                added += 1
        if added:
            save_custom(self.custom_chars)
            self.refresh_list()
            if callable(self.on_changed):
                self.on_changed()
        self.input_edit.clear()

    def remove_selected(self):
        # Удаляет выбранные смайлики из списка
        items = self.list_widget.selectedItems()
        if not items:
            return
        to_remove = {it.text() for it in items}
        if not to_remove:
            return
        self.custom_chars[:] = [ch for ch in self.custom_chars if ch not in to_remove]
        save_custom(self.custom_chars)
        self.refresh_list()
        if callable(self.on_changed):
            self.on_changed()


class EptalEmojiWindow(QWidget):
    emoji_selected = pyqtSignal(str)

    def __init__(self, all_entries, history, custom_chars, initial_category="All"):
        super().__init__()
        self.all_entries = all_entries
        self.history = history
        self.custom_chars = custom_chars
        self.current_category = initial_category
        self.target_hwnd = 0
        self._drag_state = None
        self._emoji_drag = None
        self.on_delete_emoji = None
        self.on_move_emoji = None
        self.category_overrides = {}
        self.add_dialog = None
        self._suppress_search_collapse = False
        self._search_toggling = False
        self._save_size_timer = QTimer(self)
        self._save_size_timer.setSingleShot(True)
        self._save_size_timer.setInterval(400)
        self._save_size_timer.timeout.connect(self._save_window_size)
        self._save_pos_timer = QTimer(self)
        self._save_pos_timer.setSingleShot(True)
        self._save_pos_timer.setInterval(400)
        self._save_pos_timer.timeout.connect(self._save_window_pos)
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(120)
        self._reflow_timer.timeout.connect(self._reflow_grid_if_needed)
        self._last_grid_cols = None
        self._build_ui()
        self._apply_window_flags()
        self._update_no_activate_exstyle()
        self.refresh_grid()

    def _build_ui(self):
        self.setWindowTitle("Eptal emoji")
        state = load_state()
        w = int(state.get("window_width", 476) or 476)
        h = int(state.get("window_height", 480) or 480)
        self.resize(max(360, w), max(320, h))
        self.setMinimumSize(360, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame()
        self.container.setObjectName("container")
        self.container.setStyleSheet(
            """
            QFrame#container {
                background-color: rgba(22, 22, 22, 165);
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
            QLabel {
                color: #f3f3f3;
                font-family: 'Segoe UI';
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 3px 8px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QPushButton#catBtn {
                background-color: #2b2b2b;
                color: #eaeaea;
                border: none;
                border-radius: 8px;
                padding: 6px 8px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QPushButton#catBtn:checked {
                background-color: #3a3a3a;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QWidget#gridHost {
                background-color: rgba(18, 18, 18, 35);
                border-radius: 8px;
            }
            """
        )
        root.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Верхняя панель: кнопка перетаскивания, поиск и кнопка скрытия
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.drag_btn = QPushButton("⠿")
        self.drag_btn.setObjectName("dragHandle")
        self.drag_btn.setFixedSize(28, 28)
        self.drag_btn.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_btn.setToolTip("Перетащить окно")
        self.drag_btn.setStyleSheet(
            "QPushButton { background: #2b2b2b; color: #d0d0d0; border: none; border-radius: 8px; font-size: 14px; }"
            "QPushButton:hover { background: #3a3a3a; color: #ffffff; }"
        )
        self.drag_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.drag_btn.installEventFilter(self)
        top_row.addWidget(self.drag_btn)

        self.cat_buttons = {}
        self.added_btn = QPushButton("Добавл.")
        self.added_btn.setObjectName("catBtn")
        self.added_btn.setCheckable(True)
        self.added_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.added_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.added_btn.setFixedHeight(28)
        self.added_btn.setToolTip("Добавленные смайлики")
        self.added_btn.setStyleSheet(
            "QPushButton#catBtn { background-color: #2b2b2b; color: #eaeaea; border: none; border-radius: 8px; padding: 4px 7px; font-family: 'Segoe UI'; font-size: 12px; }"
            "QPushButton#catBtn:checked { background-color: #3a3a3a; color: #ffffff; }"
            "QPushButton#catBtn:hover { background-color: #343434; }"
        )
        self.added_btn.clicked.connect(lambda checked=False, n="Custom": self.set_category(n))
        self.added_btn.installEventFilter(self)
        self.added_btn.setAcceptDrops(True)
        self.cat_buttons["Custom"] = self.added_btn
        top_row.addWidget(self.added_btn)
        self.search_btn = QPushButton("🔍")
        self.search_btn.setFixedSize(28, 28)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setToolTip("Поиск")
        self.search_btn.setCheckable(True)
        self.search_btn.setStyleSheet(
            "QPushButton { background: #2b2b2b; color: #f3f3f3; border: none; border-radius: 8px; font-family: 'Segoe UI Emoji'; font-size: 14px; padding: 0px; }"
            "QPushButton:hover { background: #3a3a3a; }"
            "QPushButton:checked { background: #3a3a3a; }"
        )
        self.search_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_btn.installEventFilter(self)
        self.search_btn.clicked.connect(self.toggle_search)
        top_row.addWidget(self.search_btn)

        # Встроенный поисковик: скрыт по умолчанию, фокус включается только при открытии
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.refresh_grid)
        self.search.setMinimumWidth(0)
        self.search.setFixedHeight(24)
        self.search.setMaximumWidth(140)
        self.search.setVisible(False)
        self.search.setEnabled(False)
        top_row.addWidget(self.search, 1)
        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setToolTip("Добавить смайлики")
        self.add_btn.setStyleSheet(
            "QPushButton { background: #2b2b2b; color: #f3f3f3; border: none; border-radius: 8px; font-family: 'Segoe UI'; font-size: 16px; padding: 0px; padding-bottom: 1px; }"
            "QPushButton:hover { background: #3a3a3a; }"
        )
        self.add_btn.clicked.connect(self.open_add_emoji_dialog)
        self.add_btn.installEventFilter(self)
        self.add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        top_row.addWidget(self.add_btn)

        self.hide_btn = QPushButton("✕")
        self.hide_btn.setFixedSize(28, 28)
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.setToolTip("Скрыть")
        self.hide_btn.setStyleSheet(
            "QPushButton { background: #2b2b2b; color: #f3f3f3; border: none; border-radius: 8px; font-family: 'Segoe UI'; font-size: 14px; padding: 0px; }"
            "QPushButton:hover { background: #3a3a3a; }"
        )
        self.hide_btn.clicked.connect(self.hide)
        self.hide_btn.installEventFilter(self)
        top_row.addWidget(self.hide_btn)
        layout.addLayout(top_row)

        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        self.cat_labels = {
            "Recent": "Недавние",
            "BigSmiles": "Круглые",
            "Nature/Food": "Прир./Еда",
            "Symbols": "Символы",
        }
        for key in ["Recent", "BigSmiles", "Nature/Food", "Symbols"]:
            btn = QPushButton(self.cat_labels.get(key, key))
            btn.setObjectName("catBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, n=key: self.set_category(n))
            btn.installEventFilter(self)
            btn.setAcceptDrops(True)
            self.cat_buttons[key] = btn
            cat_row.addWidget(btn)
        layout.addLayout(cat_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid_host.setObjectName("gridHost")
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)
        self.grid_layout.setHorizontalSpacing(4)
        self.grid_layout.setVerticalSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        self.scroll.viewport().installEventFilter(self)
        self.grid_host.installEventFilter(self)
        self.container.installEventFilter(self)
        self._scroll_anim = None
        self._render_token = 0
        layout.addWidget(self.scroll, 1)

        # Подпись приложения и уголок для изменения размера окна
        grip_row = QHBoxLayout()
        self.app_label = QLabel(f"Eptal emoji v{APP_VERSION}")
        self.app_label.setStyleSheet("color: #bdbdbd; font-family: 'Segoe UI'; font-size: 11px;")
        grip_row.addWidget(self.app_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        grip_row.addStretch(1)
        self.size_grip = QSizeGrip(self.container)
        self.size_grip.setFixedSize(14, 14)
        grip_row.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(grip_row)

        self.set_category(self.current_category)

    def _apply_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _update_no_activate_exstyle(self):
        try:
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def toggle_search(self, checked=None):
        # Разворачивает/сворачивает встроенный поисковик
        if getattr(self, "_search_toggling", False):
            return
        self._search_toggling = True
        try:
            expand = not self.search.isVisible()
            try:
                with open(r"C:\Users\Sadiu\AppData\Local\Temp\opencode\eptal_debug2.log","a",encoding="utf-8") as f:
                    f.write(f"toggle expand={expand} checked={checked} visible={self.search.isVisible()}\n")
            except Exception:
                pass
            self.search_btn.setChecked(expand)
            if expand:
                self._suppress_search_collapse = True
                try:
                    self.search.setEnabled(True)
                    self.search.setVisible(True)
                    self._set_search_focus_mode(True)
                    self.search.setFocus()
                    self.search.selectAll()
                finally:
                    self._suppress_search_collapse = False
            else:
                self.search.clear()
                self.search.setVisible(False)
                self.search.setEnabled(False)
                self._set_search_focus_mode(False)
        except Exception:
            pass
        finally:
            self._search_toggling = False

    def _set_search_focus_mode(self, enabled, reshow=True):
        # Включает/выключает возможность фокуса для ввода в поиск
        try:
            self._suppress_search_collapse = True
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, not enabled)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not enabled)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if enabled else Qt.FocusPolicy.NoFocus)
            if self.isVisible():
                self.show()  # применить флаги окна
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enabled:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_NOACTIVATE)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
                self.activateWindow()
                try:
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                try:
                    self.search.setFocus()
                except Exception:
                    pass
            else:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE)
        except Exception:
            pass
        finally:
            self._suppress_search_collapse = False

    def showEvent(self, event):
        super().showEvent(event)
        # Поиск не сворачиваем автоматически: только по кнопке лупы
        if getattr(self, "_suppress_search_collapse", False):
            return
        try:
            if hasattr(self, "search") and self.search.isVisible() and self.search.isEnabled():
                self._set_search_focus_mode(True)
            else:
                self._update_no_activate_exstyle()
        except Exception:
            self._update_no_activate_exstyle()

    def hideEvent(self, event):
        try:
            with open(r"C:\Users\Sadiu\AppData\Local\Temp\opencode\eptal_debug2.log","a",encoding="utf-8") as f:
                f.write(f"hideEvent suppress={getattr(self,'_suppress_search_collapse',False)} search_vis={getattr(self,'search',None) and self.search.isVisible()}\n")
        except Exception:
            pass
        try:
            # Поиск не сворачиваем автоматически: только по кнопке лупы
            if not getattr(self, "_suppress_search_collapse", False):
                self._set_search_focus_mode(False, reshow=False)
        except Exception:
            pass
        super().hideEvent(event)
        # При внутреннем пересоздании окна (смена флагов) не оставляем его скрытым
        if getattr(self, "_suppress_search_collapse", False):
            QTimer.singleShot(0, lambda: (not self.isVisible()) and self.show())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Сохранение размера окна и перестройка сетки под ширину
        if hasattr(self, "_save_size_timer"):
            self._save_size_timer.start()
        if hasattr(self, "_reflow_timer"):
            self._reflow_timer.start()

    def _save_window_size(self):
        try:
            st = load_state()
            st["window_width"] = self.width()
            st["window_height"] = self.height()
            save_state(st)
        except Exception:
            pass

    def _save_window_pos(self):
        # Сохраняет позицию окна после перемещения
        try:
            st = load_state()
            st["window_x"] = self.x()
            st["window_y"] = self.y()
            save_state(st)
        except Exception:
            pass

    def open_add_emoji_dialog(self):
        # Открывает независимое окно добавления своих смайликов
        try:
            if self.add_dialog is not None and self.add_dialog.isVisible():
                self.add_dialog.refresh_list()
                self.add_dialog.showNormal()
                self.add_dialog.raise_()
                self.add_dialog.activateWindow()
                return
        except Exception:
            self.add_dialog = None
        dlg = AddEmojiDialog(self.custom_chars, self.reload_custom_entries, None)
        self.add_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def reload_custom_entries(self):
        # Пересобирает список эмодзи с учётом добавленных пользователем
        try:
            base = build_emoji_entries()
            merge_custom_entries(base, self.custom_chars)
            st = load_state()
            hidden = set(st.get("hidden_emojis", []))
            if hidden:
                base = [e for e in base if e.get("char") not in hidden]
            self.category_overrides = st.get("emoji_category_overrides", {}) or {}
            self.all_entries = base
            self.refresh_grid()
            if self.add_dialog is not None and self.add_dialog.isVisible():
                self.add_dialog.refresh_list()
        except Exception:
            pass

    def set_category(self, name):
        self.current_category = name
        for n, btn in self.cat_buttons.items():
            btn.setChecked(n == name)
        # Сохранение последней открытой вкладки
        state = load_state()
        state["last_category"] = name
        save_state(state)
        self.refresh_grid()

    def _is_round_smiley(self, entry):
        # Определяет, относится ли смайлик к вкладке "Круглые"
        ch = entry.get("char", "")
        if not ch:
            return False
        overrides = getattr(self, "category_overrides", {}) or {}
        ov = overrides.get(ch)
        if ov == "Custom":
            return False
        if ov in {"BigSmiles", "Nature/Food", "Symbols"}:
            return ov == "BigSmiles"
        if entry.get("custom"):
            return False
        cp = ord(ch[0])
        name = (entry.get("en") or "").lower()
        # Всё, что связано с котом, показываем во вкладке "Круглые"
        if "cat" in name:
            return True
        # Классические круглые смайлики-лица
        if 0x1F600 <= cp <= 0x1F636:
            return True
        if 0x1F641 <= cp <= 0x1F644:
            return True
        if 0x1F910 <= cp <= 0x1F917:
            return True
        if 0x1F920 <= cp <= 0x1F925:
            return True
        if 0x1F927 <= cp <= 0x1F92F:
            return True
        if 0x1F970 <= cp <= 0x1F976:
            return True
        if 0x1F978 <= cp <= 0x1F97A:
            return True
        if 0x1F9D0 <= cp <= 0x1F9D0:
            return True
        if any(k in name for k in ["smiling face", "grinning face", "face with", "winking face", "neutral face", "expressionless face"]):
            return True
        return False

    def _filtered_entries(self):
        q = self.search.text().strip().lower()
        overrides = getattr(self, "category_overrides", {}) or {}
        custom_chars = set(getattr(self, "custom_chars", []) or [])

        def is_custom(e):
            ch = e.get("char", "")
            ov = overrides.get(ch)
            if ov == "Custom":
                return True
            if ov in {"BigSmiles", "Nature/Food", "Symbols"}:
                return False
            return bool(e.get("custom")) or ch in custom_chars

        def in_bigsmiles(e):
            ch = e.get("char", "")
            if is_custom(e):
                return False
            ov = overrides.get(ch)
            if ov in {"BigSmiles", "Nature/Food", "Symbols"}:
                return ov == "BigSmiles"
            return self._is_round_smiley(e)

        def in_group(e, group):
            ch = e.get("char", "")
            if is_custom(e):
                return False
            ov = overrides.get(ch)
            if ov in {"BigSmiles", "Nature/Food", "Symbols"}:
                return ov == group
            return e.get("group") == group and not self._is_round_smiley(e)

        if self.current_category == "Recent":
            # Недавние: в порядке нажатий (последний сверху - первым)
            by_char = {e["char"]: e for e in self.all_entries}
            items = [by_char[c] for c in self.history if c in by_char]
        elif self.current_category == "BigSmiles":
            # Круглые смайлики и коты
            items = [e for e in self.all_entries if in_bigsmiles(e)]
        elif self.current_category == "Custom":
            # Добавленные пользователем смайлики
            items = [e for e in self.all_entries if is_custom(e)]
        elif self.current_category in {"Nature/Food", "Symbols"}:
            items = [e for e in self.all_entries if in_group(e, self.current_category)]
        else:
            items = [
                e for e in self.all_entries
                if e.get("group") == self.current_category
                and not in_bigsmiles(e)
                and not is_custom(e)
            ]
        if not q:
            return items if self.current_category == "Recent" else items[:2000]
        res = [e for e in items if q in e["search"] or q in e["char"]]
        return res[:2000] if self.current_category != "Recent" else res

    @staticmethod
    def _is_round_smiley(entry):
        if entry.get("custom"):
            return False
        ch = entry.get("char", "")
        if not ch:
            return False
        cp = ord(ch[0])
        name = (entry.get("en") or "").lower()
        # Всё, что связано с котом, показываем во вкладке "Круглые"
        if "cat" in name:
            return True
        # Классические круглые смайлики-лица
        if 0x1F600 <= cp <= 0x1F636:
            return True
        if 0x1F641 <= cp <= 0x1F644:
            return True
        if 0x1F910 <= cp <= 0x1F917:
            return True
        if 0x1F920 <= cp <= 0x1F925:
            return True
        if 0x1F927 <= cp <= 0x1F92F:
            return True
        if 0x1F970 <= cp <= 0x1F976:
            return True
        if 0x1F978 <= cp <= 0x1F97A:
            return True
        if 0x1F9D0 <= cp <= 0x1F9D0:
            return True
        if any(k in name for k in ["smiling face", "grinning face", "face with", "winking face", "neutral face", "expressionless face"]):
            return True
        return False


    def _show_emoji_menu(self, btn, ch):
        # Показывает меню действий для смайлика
        menu = QMenu(self)
        delete_action = menu.addAction("Удалить")
        action = menu.exec(btn.mapToGlobal(btn.rect().center()))
        if action == delete_action and callable(getattr(self, "on_delete_emoji", None)):
            self.on_delete_emoji(ch)

    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _calc_cols(self, btn_size):
        # Число столбцов по доступной ширине области со смайликами
        try:
            viewport_w = self.scroll.viewport().width()
        except Exception:
            viewport_w = 0
        margins = self.grid_layout.contentsMargins()
        spacing = self.grid_layout.horizontalSpacing() or 4
        avail = viewport_w - margins.left() - margins.right()
        if avail <= 0:
            return 7 if btn_size >= 56 else 9
        cols = max(1, (avail + spacing) // (btn_size + spacing))
        return int(cols)

    def _reflow_grid_if_needed(self):
        # Перестроить сетку при изменении числа столбцов
        try:
            is_big = True
            btn_size = 56
            cols = self._calc_cols(btn_size)
            if cols != self._last_grid_cols:
                self.refresh_grid()
        except Exception:
            pass

    def refresh_grid(self):
        # Плавное/отзывчивое обновление сетки: порционная отрисовка
        self._render_token += 1
        token = self._render_token
        self.clear_grid()
        self.scroll.verticalScrollBar().setValue(0)
        entries = self._filtered_entries()
        is_big = True
        emoji_font = QFont("Segoe UI Emoji")
        emoji_font.setPixelSize(34)
        btn_size = 56
        cols = self._calc_cols(btn_size)
        self._last_grid_cols = cols
        batch = 80
        index = 0

        def render_chunk():
            nonlocal index
            if token != self._render_token:
                return
            end = min(index + batch, len(entries))
            while index < end:
                entry = entries[index]
                ch = entry["char"]
                btn = QPushButton(ch)
                btn.setProperty("emoji_char", ch)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedSize(btn_size, btn_size)
                btn.setFont(emoji_font)
                font_size = 34
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; border: none; color: #ffffff; font-family: 'Segoe UI Emoji'; font-size: {font_size}px; }}"
                    "QPushButton:hover { background: #333333; border-radius: 8px; }"
                )
                btn.clicked.connect(lambda checked=False, c=ch: self.emoji_selected.emit(c))
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, c=ch, b=btn: self._show_emoji_menu(b, c)
                )
                btn.installEventFilter(self)
                self.grid_layout.addWidget(btn, index // cols, index % cols)
                index += 1
            self.grid_layout.setRowStretch((index // cols) + 1, 1)
            if index < len(entries):
                QTimer.singleShot(0, render_chunk)

        render_chunk()

    def show_at_bottom_right(self, target_hwnd=0):
        if target_hwnd:
            self.target_hwnd = target_hwnd

        was_visible = self.isVisible()

        # Выбор монитора: по курсору/целевому окну, чтобы окно появлялось на активном экране
        screen = None
        try:
            cursor_pos = QCursor.pos()
            screen = QApplication.screenAt(cursor_pos)
            if screen is None and self.target_hwnd:
                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                r = RECT()
                if user32.GetWindowRect(int(self.target_hwnd), ctypes.byref(r)):
                    cx = (r.left + r.right) // 2
                    cy = (r.top + r.bottom) // 2
                    screen = QApplication.screenAt(QPoint(cx, cy))
        except Exception:
            screen = None
        if screen is None:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()

        current_screen = QApplication.screenAt(self.frameGeometry().center()) if was_visible else None
        need_reposition = (not was_visible) or (screen is not None and current_screen is not None and screen != current_screen) or (screen is not None and current_screen is None)
        if need_reposition:
            moved = False
            try:
                st = load_state()
                sx = st.get("window_x")
                sy = st.get("window_y")
                if sx is not None and sy is not None and screen is not None:
                    sp = QPoint(int(sx), int(sy))
                    ss = QApplication.screenAt(sp)
                    if ss is screen:
                        self.move(sp)
                        moved = True
            except Exception:
                moved = False
            if not moved:
                geo = screen.availableGeometry() if screen else None
                if geo:
                    x = geo.x() + geo.width() - self.width() - 12
                    y = geo.y() + geo.height() - self.height() - 12
                    self.move(x, y)

        # Гарантируем, что окно видно на каком-либо экране
        try:
            center = self.frameGeometry().center()
            vis_screen = QApplication.screenAt(center)
            if vis_screen is None:
                geo = (screen or QApplication.primaryScreen() or QApplication.screens()[0]).availableGeometry()
                x = min(max(self.x(), geo.x()), geo.x() + max(0, geo.width() - self.width()))
                y = min(max(self.y(), geo.y()), geo.y() + max(0, geo.height() - self.height()))
                self.move(x, y)
        except Exception:
            pass

        # Показываем окно; если активен поиск, не ломаем режим ввода
        search_active = hasattr(self, "search") and self.search.isVisible() and self.search.isEnabled()
        if search_active:
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.show()
            self._set_search_focus_mode(True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            self.show()
            self._update_no_activate_exstyle()
            try:
                hwnd = int(self.winId())
                SW_SHOWNOACTIVATE = 4
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                SWP_SHOWWINDOW = 0x0040
                user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            except Exception:
                pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def smooth_scroll_by(self, delta):
        # Плавная прокрутка сетки эмодзи
        bar = self.scroll.verticalScrollBar()
        start = bar.value()
        end = max(bar.minimum(), min(bar.maximum(), start - delta))
        if self._scroll_anim and self._scroll_anim.state() == QPropertyAnimation.State.Running:
            self._scroll_anim.stop()
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(180)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._scroll_anim = anim

    def _category_key_for_button(self, obj):
        # Возвращает ключ категории для кнопки-вкладки
        try:
            for key, btn in self.cat_buttons.items():
                if obj is btn:
                    return key
        except Exception:
            pass
        return None

    def eventFilter(self, obj, event):
        # Плавная прокрутка, перетаскивание окна, перенос смайликов во вкладки
        try:
            et = event.type()
            if obj is self.scroll.viewport() and et == QEvent.Type.Wheel:
                delta = event.angleDelta().y()
                if delta != 0:
                    self.smooth_scroll_by(delta)
                    return True

            # Перенос смайлика на кнопку категории (drag-and-drop)
            cat_key = self._category_key_for_button(obj)
            if cat_key and cat_key != "Recent":
                if et in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                    md = event.mimeData()
                    if md and md.hasFormat("application/x-eptal-emoji"):
                        event.acceptProposedAction()
                        return True
                elif et == QEvent.Type.Drop:
                    md = event.mimeData()
                    if md and md.hasFormat("application/x-eptal-emoji"):
                        ch = bytes(md.data("application/x-eptal-emoji")).decode("utf-8", errors="ignore")
                        if ch and callable(getattr(self, "on_move_emoji", None)):
                            self.on_move_emoji(ch, cat_key)
                        event.acceptProposedAction()
                        return True

            # Начало перетаскивания смайлика из сетки
            emoji_char = None
            try:
                emoji_char = obj.property("emoji_char")
            except Exception:
                emoji_char = None
            if emoji_char and et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._emoji_drag = {"char": str(emoji_char), "pos": event.globalPosition().toPoint(), "started": False}
                self._drag_state = None
                return super().eventFilter(obj, event)

            if self._emoji_drag is not None and emoji_char == self._emoji_drag.get("char"):
                if et == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                    if not self._emoji_drag.get("started"):
                        if (event.globalPosition().toPoint() - self._emoji_drag["pos"]).manhattanLength() >= QApplication.startDragDistance():
                            self._emoji_drag["started"] = True
                            drag = QDrag(obj)
                            mime = QMimeData()
                            mime.setData("application/x-eptal-emoji", str(self._emoji_drag["char"]).encode("utf-8"))
                            mime.setText(str(self._emoji_drag["char"]))
                            drag.setMimeData(mime)
                            drag.exec(Qt.DropAction.MoveAction)
                            self._emoji_drag = None
                            return True
                    return super().eventFilter(obj, event)
                if et == QEvent.Type.MouseButtonRelease:
                    self._emoji_drag = None
                    return super().eventFilter(obj, event)

            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                w = QApplication.widgetAt(event.globalPosition().toPoint())
                can_drag = False
                if w is not None:
                    w_char = None
                    try:
                        w_char = w.property("emoji_char")
                    except Exception:
                        w_char = None
                    if w_char:
                        can_drag = False
                    elif getattr(w, "objectName", lambda: "")() == "dragHandle":
                        can_drag = True
                    elif not isinstance(w, QLineEdit) and w.__class__.__name__ != "QScrollBar":
                        # Перетаскивание за пустую зону окна, кроме поля ввода, прокрутки и смайликов
                        can_drag = True
                if can_drag:
                    self._drag_state = {
                        "offset": event.globalPosition().toPoint() - self.frameGeometry().topLeft(),
                        "pos": event.globalPosition().toPoint(),
                        "dragging": False,
                    }
                else:
                    self._drag_state = None
                return super().eventFilter(obj, event)

            if et == QEvent.Type.MouseMove and self._drag_state is not None:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    cur = event.globalPosition().toPoint()
                    if not self._drag_state["dragging"]:
                        if (cur - self._drag_state["pos"]).manhattanLength() >= 5:
                            self._drag_state["dragging"] = True
                    if self._drag_state["dragging"]:
                        self.move(cur - self._drag_state["offset"])
                        return True
                    return super().eventFilter(obj, event)
                self._drag_state = None
                return super().eventFilter(obj, event)

            if et == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                was_dragging = self._drag_state is not None and self._drag_state.get("dragging")
                self._drag_state = None
                self._emoji_drag = None
                if was_dragging and hasattr(self, "_save_pos_timer"):
                    self._save_pos_timer.start()
                return super().eventFilter(obj, event)
        except Exception:
            pass
        return super().eventFilter(obj, event)

class AppController(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.last_target_hwnd = 0
        self.entries = build_emoji_entries()
        self.history = load_history()
        self.custom_chars = load_custom()
        merge_custom_entries(self.entries, self.custom_chars)
        state = load_state()
        hidden = set(state.get("hidden_emojis", []))
        if hidden:
            self.entries = [e for e in self.entries if e.get("char") not in hidden]
            self.history = [ch for ch in self.history if ch not in hidden]
        self.auto_popup_enabled = bool(state.get("auto_popup_enabled", True))
        initial_category = state.get("last_category") or "BigSmiles"
        if initial_category in {"All", "Faces", "Flags"}:
            initial_category = "BigSmiles"
        if initial_category not in {"Recent", "BigSmiles", "Nature/Food", "Symbols", "Custom"}:
            initial_category = "BigSmiles"

        self.bridge = SignalBridge()
        self.bridge.hotkey_pressed.connect(self.on_hotkey)

        self.category_overrides = load_category_overrides()
        self.window = EptalEmojiWindow(self.entries, self.history, self.custom_chars, initial_category)
        self.window.category_overrides = self.category_overrides
        self.window.emoji_selected.connect(self.on_emoji_selected)
        self.window.on_delete_emoji = self.delete_emoji
        self.window.on_move_emoji = self.move_emoji

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._load_tray_icon())
        self.tray.setToolTip("Eptal emoji")
        self._build_tray_menu()
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        self.watcher = FocusWatcher(self.bridge)
        self.watcher.focus_text_input.connect(self.on_text_focus)
        self.watcher.start()
        self.watcher.set_enabled(self.auto_popup_enabled)

        self._register_hotkey()
        self._start_target_tracker()
        self.app.installEventFilter(self)

    def _load_tray_icon(self):
        # Иконка трея: эмодзи
        from PyQt6.QtGui import QPixmap, QPainter, QColor
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI Emoji")
        font.setPixelSize(48)
        p.setFont(font)
        p.setPen(QColor("#ffffff"))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "😈")
        p.end()
        return QIcon(pm)

    def _build_tray_menu(self):
        menu = QMenu()
        open_action = QAction("Открыть", menu)
        open_action.triggered.connect(lambda: self.show_picker(self._current_foreground()))
        menu.addAction(open_action)

        self.toggle_auto_action = QAction("Авто-показ при фокусе на поле ввода", menu)
        self.toggle_auto_action.setCheckable(True)
        self.toggle_auto_action.setChecked(self.auto_popup_enabled)
        self.toggle_auto_action.toggled.connect(self.on_toggle_auto)
        menu.addAction(self.toggle_auto_action)

        self.autostart_action = QAction("Запускать вместе с Windows", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self._is_autostart_enabled())
        self.autostart_action.toggled.connect(self.on_toggle_autostart)
        menu.addAction(self.autostart_action)

        clear_recent_action = QAction("Очистить недавние", menu)
        clear_recent_action.triggered.connect(self.clear_recent)
        menu.addAction(clear_recent_action)

        menu.addSeparator()
        exit_action = QAction("Выход", menu)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)

    def on_toggle_auto(self, checked):
        self.auto_popup_enabled = checked
        self.watcher.set_enabled(checked)
        try:
            st = load_state()
            st["auto_popup_enabled"] = bool(checked)
            save_state(st)
        except Exception:
            pass

    def _autostart_key(self):
        return r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _autostart_name(self):
        return "EptalEmoji"

    def _autostart_command(self):
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        py = str(pythonw) if pythonw.exists() else sys.executable
        script = str(Path(__file__).resolve())
        return f'"{py}" "{script}"'

    def _is_autostart_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._autostart_key(), 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, self._autostart_name())
                return bool(val)
        except Exception:
            return False

    def _set_autostart(self, enabled):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._autostart_key(), 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, self._autostart_name(), 0, winreg.REG_SZ, self._autostart_command())
                else:
                    try:
                        winreg.DeleteValue(key, self._autostart_name())
                    except FileNotFoundError:
                        pass
            return True
        except Exception:
            return False

    def on_toggle_autostart(self, checked):
        # Включение/выключение автозапуска при входе в Windows
        ok = self._set_autostart(checked)
        if not ok:
            self.autostart_action.setChecked(self._is_autostart_enabled())


    def _reload_entries(self):
        # Пересобирает записи с учётом своих, скрытых и переопределений категорий
        base = build_emoji_entries()
        merge_custom_entries(base, self.custom_chars)
        st = load_state()
        hidden = set(st.get("hidden_emojis", []))
        if hidden:
            base = [e for e in base if e.get("char") not in hidden]
        self.entries = base
        self.window.all_entries = base
        self.window.custom_chars = self.custom_chars
        self.window.history = self.history
        self.window.category_overrides = self.category_overrides
        self.window.refresh_grid()

    def delete_emoji(self, ch):
        # Удаляет смайлик: из своих или скрывает встроенный
        if not ch:
            return
        try:
            if ch in self.custom_chars:
                self.custom_chars[:] = [x for x in self.custom_chars if x != ch]
                save_custom(self.custom_chars)
            else:
                st = load_state()
                hidden = st.get("hidden_emojis", [])
                if not isinstance(hidden, list):
                    hidden = []
                if ch not in hidden:
                    hidden.append(ch)
                st["hidden_emojis"] = hidden
                save_state(st)

            if ch in self.category_overrides:
                self.category_overrides.pop(ch, None)
                save_category_overrides(self.category_overrides)

            self.history = [x for x in self.history if x != ch]
            save_history(self.history)
            self._reload_entries()
        except Exception:
            pass

    def move_emoji(self, ch, target_category):
        # Переносит смайлик в указанную категорию
        if not ch or not target_category or target_category == "Recent":
            return
        if target_category not in {"BigSmiles", "Nature/Food", "Symbols", "Custom"}:
            return
        try:
            if target_category == "Custom":
                if ch not in self.custom_chars:
                    self.custom_chars.append(ch)
                    save_custom(self.custom_chars)
                if ch in self.category_overrides:
                    self.category_overrides.pop(ch, None)
                    save_category_overrides(self.category_overrides)
            else:
                if ch in self.custom_chars:
                    self.custom_chars[:] = [x for x in self.custom_chars if x != ch]
                    save_custom(self.custom_chars)
                self.category_overrides[ch] = target_category
                save_category_overrides(self.category_overrides)
            self._reload_entries()
        except Exception:
            pass

    def clear_recent(self):
        # Очистка истории недавних эмодзи
        self.history = []
        self.window.history = self.history
        save_history(self.history)
        if self.window.current_category == "Recent":
            self.window.refresh_grid()

    def on_tray_activated(self, reason):
        # Открытие/закрытие окна по двойному клику по иконке в трее
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show_picker(self._current_foreground())

    def _current_foreground(self):
        try:
            return int(user32.GetForegroundWindow() or 0)
        except Exception:
            return 0

    def _start_target_tracker(self):
        def loop():
            while True:
                try:
                    hwnd = self._current_foreground()
                    my = int(self.window.winId()) if self.window.isVisible() else 0
                    if hwnd and hwnd != my:
                        self.last_target_hwnd = hwnd
                except Exception:
                    pass
                time.sleep(0.2)

        import threading

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _register_hotkey(self):
        def hook():
            try:
                keyboard.add_hotkey("ctrl+alt+e", lambda: self.bridge.hotkey_pressed.emit(), suppress=False)
                keyboard.wait()
            except Exception:
                pass

        import threading

        t = threading.Thread(target=hook, daemon=True)
        t.start()

    def on_hotkey(self):
        self.show_picker(self._current_foreground())

    def on_text_focus(self, hwnd):
        if not self.auto_popup_enabled:
            return
        self.show_picker(hwnd or self._current_foreground())

    def show_picker(self, target_hwnd=0):
        if target_hwnd:
            self.last_target_hwnd = target_hwnd
        self.window.show_at_bottom_right(self.last_target_hwnd)

    def on_emoji_selected(self, ch):
        # update history
        self.history = [x for x in self.history if x != ch]
        self.history.insert(0, ch)
        self.history = self.history[:MAX_HISTORY]
        save_history(self.history)
        self.window.history = self.history
        if self.window.current_category == "Recent":
            self.window.refresh_grid()
        # copy
        try:
            pyperclip.copy(ch)
        except Exception:
            try:
                QApplication.clipboard().setText(ch)
            except Exception:
                pass
        # restore focus to target and paste shortly after
        target = self.last_target_hwnd or self._current_foreground()
        self._activate_target(target)
        QTimer.singleShot(80, lambda: self._send_paste())

    def _activate_target(self, hwnd):
        if not hwnd:
            return
        try:
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        except Exception:
            pass

    def _send_paste(self):
        try:
            keyboard.press_and_release("ctrl+v")
        except Exception:
            pass

    def eventFilter(self, obj, event):
        # Auto-hide when clicking outside picker and active text field
        try:
            if event.type() == event.Type.MouseButtonPress and self.window.isVisible():
                gpos = QCursor.pos()
                wpos = self.window.mapFromGlobal(gpos)
                inside_picker = self.window.rect().contains(wpos)
                if not inside_picker:
                    # Не скрываем окно во время активного поиска
                    try:
                        if hasattr(self.window, "search") and self.window.search.isVisible():
                            return super().eventFilter(obj, event)
                    except Exception:
                        pass
                    # if click went to target text field, keep open? spec says hide when clicking outside both picker and active text field
                    # best-effort: if click is inside target window area, we can't easily know "text field" bounds globally; hide on outside picker clicks except keep behavior simple
                    target = self.last_target_hwnd
                    if target:
                        # check if cursor is within target window rect
                        class RECT(ctypes.Structure):
                            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                        r = RECT()
                        if user32.GetWindowRect(target, ctypes.byref(r)):
                            if r.left <= gpos.x() <= r.right and r.top <= gpos.y() <= r.bottom:
                                # inside target window (possibly text field) -> do not hide
                                return super().eventFilter(obj, event)
                    try:
                        with open(r"C:\Users\Sadiu\AppData\Local\Temp\opencode\eptal_debug2.log","a",encoding="utf-8") as f:
                            f.write("appFilter hide\n")
                    except Exception:
                        pass
                    self.window.hide()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def exit_app(self):
        try:
            self.watcher.stop()
            self.watcher.wait(1000)
        except Exception:
            pass
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.tray.hide()
        self.app.quit()


def main():
    # Запуск только одного экземпляра приложения
    mutex = kernel32.CreateMutexW(None, False, "Local\\EptalEmoji_SingleInstance")
    if kernel32.GetLastError() == 183:
        return

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = AppController(app)
    # keep reference
    app._controller = controller
    app._instance_mutex = mutex
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
