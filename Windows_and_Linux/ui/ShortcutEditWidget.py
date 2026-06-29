from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Signal
from ui.UIUtils import colorMode

_VALID_MODIFIERS = {"ctrl", "shift", "alt", "super", "win", "meta"}
_MODIFIER_ORDER = ["ctrl", "shift", "alt", "super"]
_MODIFIER_ALIASES = {"win": "super", "meta": "super"}

_VALID_SPECIAL_KEYS = {
    "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "f10", "f11", "f12",
    "tab", "enter", "space", "delete", "backspace",
    "escape", "home", "end", "page_up", "page_down",
    "up", "down", "left", "right",
}

_VALID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789.,;'/\\[]`-=")


def parse_and_validate(text: str) -> str | None:
    """
    Parse user-typed shortcut (e.g. 'Ctrl+Shift+P').
    Returns normalized storage format 'ctrl+shift+p', or None if invalid.
    """
    parts = [p.strip().lower() for p in text.strip().split("+") if p.strip()]
    if not parts:
        return None

    modifiers = []
    key = None

    for part in parts:
        if part in _VALID_MODIFIERS:
            normalized = _MODIFIER_ALIASES.get(part, part)
            if normalized not in modifiers:
                modifiers.append(normalized)
        elif part in _VALID_SPECIAL_KEYS or (len(part) == 1 and part in _VALID_CHARS):
            if key is not None:
                return None  # duplicate key
            key = part
        else:
            return None  # unknown token

    if not modifiers:
        return None
    if key is None:
        return None

    sorted_mods = sorted(modifiers, key=lambda m: _MODIFIER_ORDER.index(m) if m in _MODIFIER_ORDER else 99)
    return "+".join(sorted_mods + [key])


def to_display_format(shortcut: str) -> str:
    """'ctrl+shift+p' → 'Ctrl+Shift+P'"""
    if not shortcut:
        return ""
    return "+".join(p.upper() if len(p) == 1 else p.capitalize() for p in shortcut.split("+"))


class ShortcutEditWidget(QtWidgets.QWidget):
    """
    Widget nhập tay keyboard shortcut (vd: Ctrl+Shift+P).
    Emit shortcut_changed(str) mỗi khi shortcut thay đổi ('' nếu xóa).
    """
    shortcut_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shortcut = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._line = QtWidgets.QLineEdit()
        self._line.setPlaceholderText("e.g. Ctrl+Shift+P")
        self._line.setCursor(QtCore.Qt.CursorShape.IBeamCursor)
        self._apply_style(error=False)
        self._line.editingFinished.connect(self._on_editing_finished)
        self._line.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._line)

        self._clear_btn = QtWidgets.QPushButton("✕")
        self._clear_btn.setFixedSize(28, 28)
        self._clear_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setToolTip("Clear shortcut")
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'#444' if colorMode == 'dark' else '#eee'};
                color: {'#888' if colorMode == 'dark' else '#666'};
                border: 1px solid {'#555' if colorMode == 'dark' else '#ddd'};
                border-radius: 4px; font-size: 12px;
            }}
            QPushButton:hover {{
                background: {'#c0392b' if colorMode == 'dark' else '#e74c3c'};
                color: white; border-color: #c0392b;
            }}
        """)
        self._clear_btn.clicked.connect(self._clear)
        layout.addWidget(self._clear_btn)

    def _apply_style(self, error: bool):
        border_color = "#e74c3c" if error else ('555' if colorMode == 'dark' else '#ccc')
        focus_color = "#e74c3c" if error else "#4CAF50"
        self._line.setStyleSheet(f"""
            QLineEdit {{
                background: {'#333' if colorMode == 'dark' else '#fff'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {focus_color};
            }}
        """)

    def _on_text_changed(self):
        # Reset error state khi user đang gõ
        self._apply_style(error=False)
        self._line.setToolTip("")

    def _on_editing_finished(self):
        text = self._line.text().strip()

        if not text:
            self._shortcut = ""
            self._apply_style(error=False)
            self.shortcut_changed.emit("")
            return

        result = parse_and_validate(text)
        if result is None:
            self._apply_style(error=True)
            self._line.setToolTip(
                "Invalid shortcut format.\n"
                "Use: Modifier+Key (e.g. Ctrl+Shift+P)\n"
                "Modifiers: Ctrl, Shift, Alt, Super/Win\n"
                "Keys: letters, digits, F1–F12, or special keys"
            )
            return

        self._shortcut = result
        self._apply_style(error=False)
        self._line.setToolTip("")
        self._line.setText(to_display_format(result))
        self.shortcut_changed.emit(self._shortcut)

    def _clear(self):
        self._shortcut = ""
        self._line.clear()
        self._apply_style(error=False)
        self._line.setToolTip("")
        self.shortcut_changed.emit("")

    def get_shortcut(self) -> str:
        return self._shortcut

    def set_shortcut(self, shortcut: str):
        self._shortcut = shortcut or ""
        self._line.setText(to_display_format(self._shortcut))
        self._apply_style(error=False)
