# Phase 5 — Per-Command Keyboard Shortcuts (Windows/Linux)

**Ngày tạo**: 2026-04-19  
**Depends on**: Phase 4 (Command model + CommandManager phải xong trước)  
**Library**: `pynput` (đã có trong dependencies — dùng cho global hotkey hiện tại)

---

## Mục tiêu

- Mỗi command có thể gán 1 global keyboard shortcut riêng
- Shortcut kích hoạt command mà không cần mở popup
- Kiểm tra conflict: với global hotkey của app và với shortcuts của các command khác
- UI để gán/xóa shortcut trong CommandEditorDialog (Phase 4)

---

## Kiến trúc hiện tại cần hiểu

Hiện tại `WritingToolApp` dùng **1 `pynput.keyboard.Listener`** với **1 `HotKey` object**:

```python
hotkey = pykeyboard.HotKey(pykeyboard.HotKey.parse(shortcut), on_activate)

self.hotkey_listener = pykeyboard.Listener(
    on_press=for_canonical(hotkey.press),
    on_release=for_canonical(hotkey.release)
)
```

**Vấn đề**: Listener hiện tại chỉ xử lý 1 HotKey. Cần refactor để xử lý N hotkeys.

**pynput hỗ trợ sẵn**: Một Listener có thể dispatch event đến nhiều HotKey objects — chỉ cần loop qua tất cả trong `on_press`/`on_release`.

---

## 1. Cập nhật Command Model — `models/command.py`

Thêm 1 field:

```python
@dataclass
class Command:
    ...
    keyboard_shortcut: str | None = None  # VD: "ctrl+shift+p", None nếu không gán
```

`commands.json` tự động include field này vì dùng `to_dict()` / `from_dict()`.

---

## 2. ShortcutManager — `models/shortcut_manager.py`

Class trung tâm quản lý tất cả global hotkeys (app hotkey + per-command shortcuts).

### Trách nhiệm

- Duy trì **1 `pynput.Listener` duy nhất** dispatch event đến tất cả `HotKey` objects
- Khi commands thay đổi (add/update/delete): rebuild danh sách HotKey và restart listener
- Conflict detection trước khi register

### Interface

```python
from pynput import keyboard as pykeyboard
from typing import Callable

class ShortcutManager:
    def __init__(self):
        self._listener: pykeyboard.Listener | None = None
        self._hotkeys: dict[str, pykeyboard.HotKey] = {}  # key: shortcut string, value: HotKey
        self._callbacks: dict[str, Callable] = {}         # key: shortcut string, value: callback

    def register(self, shortcut: str, callback: Callable) -> None:
        """Thêm 1 shortcut. Gọi restart() sau để có hiệu lực."""

    def unregister(self, shortcut: str) -> None:
        """Xóa 1 shortcut. Gọi restart() sau để có hiệu lực."""

    def unregister_all_commands(self) -> None:
        """Xóa tất cả command shortcuts, giữ lại app hotkey."""

    def restart(self) -> None:
        """Stop listener cũ, build lại tất cả HotKey, start listener mới."""

    def stop(self) -> None:
        """Dừng hẳn — gọi khi exit app."""

    def registered_shortcuts(self) -> list[str]:
        """Trả về danh sách shortcuts đang active."""
```

### Implementation chi tiết

```python
def restart(self):
    if self._listener is not None:
        self._listener.stop()

    hotkeys = {}
    for shortcut_str, cb in self._callbacks.items():
        pynput_fmt = _to_pynput_format(shortcut_str)  # "ctrl+shift+p" → "<ctrl>+<shift>+p"
        hotkeys[shortcut_str] = pykeyboard.HotKey(
            pykeyboard.HotKey.parse(pynput_fmt), cb
        )
    self._hotkeys = hotkeys

    def on_press(key):
        for hk in self._hotkeys.values():
            hk.press(self._listener.canonical(key))

    def on_release(key):
        for hk in self._hotkeys.values():
            hk.release(self._listener.canonical(key))

    self._listener = pykeyboard.Listener(on_press=on_press, on_release=on_release)
    self._listener.daemon = True
    self._listener.start()
```

### Format conversion helpers

```python
def _to_pynput_format(shortcut: str) -> str:
    """
    "ctrl+shift+p" → "<ctrl>+<shift>+p"
    Các key 1 ký tự không bọc <>, modifier keys thì bọc.
    """
    parts = shortcut.lower().split("+")
    return "+".join(f"<{p}>" if len(p) > 1 else p for p in parts)

def _normalize(shortcut: str) -> str:
    """Lowercase, strip spaces — để compare conflict."""
    return shortcut.lower().replace(" ", "")
```

---

## 3. Conflict Detection — `models/shortcut_conflict.py`

Module nhỏ, pure functions, không dependency vào UI.

```python
from dataclasses import dataclass

@dataclass
class ConflictResult:
    has_conflict: bool
    conflict_type: str   # "app_hotkey" | "command" | "none"
    conflict_name: str   # tên command bị conflict, hoặc "App Hotkey"

def check_conflict(
    shortcut: str,
    app_hotkey: str,
    command_shortcuts: dict[str, str],   # {command_id: shortcut}
    exclude_command_id: str | None = None,  # dùng khi đang edit command, bỏ qua chính nó
) -> ConflictResult:
    normalized = _normalize(shortcut)

    # Check vs app hotkey
    if normalized == _normalize(app_hotkey):
        return ConflictResult(True, "app_hotkey", "App Hotkey")

    # Check vs other command shortcuts
    for cmd_id, cmd_shortcut in command_shortcuts.items():
        if cmd_id == exclude_command_id:
            continue
        if normalized == _normalize(cmd_shortcut):
            return ConflictResult(True, "command", cmd_id)

    return ConflictResult(False, "none", "")
```

`command_shortcuts` dict được lấy từ `CommandManager`:
```python
{cmd.id: cmd.keyboard_shortcut for cmd in manager.commands if cmd.keyboard_shortcut}
```

---

## 4. UI: ShortcutEdit Widget — `ui/ShortcutEditWidget.py`

Widget tùy chỉnh để capture và hiển thị keyboard shortcut.

### Tại sao không dùng `QKeySequenceEdit`?

`QKeySequenceEdit` của Qt dùng Qt key format (`"Ctrl+Shift+P"`) — không map 1-1 với pynput format cho một số special keys. Dùng custom widget để kiểm soát hoàn toàn.

### Behavior

- Click vào field: chuyển sang "recording mode" (placeholder: "Press keys...")
- User nhấn tổ hợp phím: capture, convert, hiển thị dạng human-readable
- Nhấn Escape: hủy recording
- Nhấn Backspace khi field có giá trị: xóa shortcut
- Click button "✕" bên cạnh: xóa shortcut
- Emit signal `shortcut_changed(str)` mỗi khi shortcut thay đổi

```python
class ShortcutEditWidget(QtWidgets.QWidget):
    shortcut_changed = Signal(str)  # emit shortcut string hoặc "" nếu xóa

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shortcut = ""      # "ctrl+shift+p" format
        self._recording = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.display = QtWidgets.QLineEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Click to set shortcut")
        self.display.mousePressEvent = self._start_recording
        self.display.keyPressEvent = self._on_key_press
        layout.addWidget(self.display)

        self.clear_btn = QtWidgets.QPushButton("✕")
        self.clear_btn.setFixedWidth(28)
        self.clear_btn.clicked.connect(self._clear)
        layout.addWidget(self.clear_btn)

    def _start_recording(self, event):
        self._recording = True
        self.display.setText("")
        self.display.setPlaceholderText("Press shortcut keys...")
        self.display.setFocus()

    def _on_key_press(self, event: QtGui.QKeyEvent):
        if not self._recording:
            return

        if event.key() == Qt.Key.Key_Escape:
            self._recording = False
            self._refresh_display()
            return

        if event.key() == Qt.Key.Key_Backspace and not self._shortcut:
            return

        shortcut = _qt_event_to_storage(event)
        if shortcut is None:
            return  # chỉ modifier key, chưa đủ tổ hợp

        self._recording = False
        self._shortcut = shortcut
        self._refresh_display()
        self.shortcut_changed.emit(self._shortcut)

    def _clear(self):
        self._shortcut = ""
        self._recording = False
        self._refresh_display()
        self.shortcut_changed.emit("")

    def _refresh_display(self):
        self.display.setPlaceholderText("Click to set shortcut")
        self.display.setText(_to_display_format(self._shortcut) if self._shortcut else "")

    def get_shortcut(self) -> str:
        return self._shortcut

    def set_shortcut(self, shortcut: str):
        self._shortcut = shortcut
        self._refresh_display()
```

### Qt key → storage format

```python
_MODIFIER_MAP = {
    Qt.KeyboardModifier.ControlModifier: "ctrl",
    Qt.KeyboardModifier.ShiftModifier:   "shift",
    Qt.KeyboardModifier.AltModifier:     "alt",
    Qt.KeyboardModifier.MetaModifier:    "super",
}

_SPECIAL_KEY_MAP = {
    Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", ..., Qt.Key.Key_F12: "f12",
    Qt.Key.Key_Tab: "tab", Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Space: "space", Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Home: "home", Qt.Key.Key_End: "end",
    Qt.Key.Key_PageUp: "page_up", Qt.Key.Key_PageDown: "page_down",
    Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
    Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
}

def _qt_event_to_storage(event: QtGui.QKeyEvent) -> str | None:
    """
    Convert Qt key event sang storage format "ctrl+shift+p".
    Trả về None nếu chỉ có modifier keys (chưa đủ tổ hợp).
    """
    key = event.key()
    mods = event.modifiers()

    # Bỏ qua nếu key chỉ là modifier
    if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return None

    parts = []
    for mod, name in _MODIFIER_MAP.items():
        if mods & mod:
            parts.append(name)

    # Special keys
    if key in _SPECIAL_KEY_MAP:
        parts.append(_SPECIAL_KEY_MAP[key])
    else:
        char = chr(key).lower()
        if char.isalnum() or char in ".,;'/\\[]`-=":
            parts.append(char)
        else:
            return None  # unsupported key

    if not parts or (len(parts) == 1 and parts[0] not in _MODIFIER_MAP.values()):
        # Cần ít nhất 1 modifier (tránh capture ký tự đơn)
        if len(parts) == 1:
            return None

    return "+".join(parts)

def _to_display_format(shortcut: str) -> str:
    """ctrl+shift+p → Ctrl+Shift+P"""
    return "+".join(p.upper() if len(p) == 1 else p.capitalize() for p in shortcut.split("+"))
```

---

## 5. CommandEditorDialog Update — `ui/CommandEditorDialog.py`

Thêm phần Keyboard Shortcut vào dialog (Phase 4):

```
CommandEditorDialog
├── Name: [QLineEdit]
├── Icon: [QLineEdit]
├── System Prompt: [QTextEdit]
├── Prefix: [QLineEdit]
├── [✓] Open response in window
├── ─────────────────────────────────
├── Keyboard Shortcut:
│   [ShortcutEditWidget          ✕]
│   ⚠ "Conflict: already used by 'Rewrite'" (QLabel, màu đỏ, ẩn nếu không conflict)
├── ─────────────────────────────────
└── [Cancel]  [Save]   ← Save bị disable nếu có conflict
```

### Wiring conflict check

```python
self.shortcut_widget.shortcut_changed.connect(self._on_shortcut_changed)

def _on_shortcut_changed(self, shortcut: str):
    self._pending_shortcut = shortcut
    if not shortcut:
        self.conflict_label.hide()
        self.save_btn.setEnabled(True)
        return

    result = check_conflict(
        shortcut=shortcut,
        app_hotkey=self.app.config.get("shortcut", ""),
        command_shortcuts={
            cmd.id: cmd.keyboard_shortcut
            for cmd in self.app.command_manager.commands
            if cmd.keyboard_shortcut
        },
        exclude_command_id=self.command.id if self.command else None,
    )

    if result.has_conflict:
        self.conflict_label.setText(f'⚠ Already used by "{result.conflict_name}"')
        self.conflict_label.show()
        self.save_btn.setEnabled(False)
    else:
        self.conflict_label.hide()
        self.save_btn.setEnabled(True)
```

---

## 6. WritingToolApp Integration — `WritingToolApp.py`

### Khởi tạo ShortcutManager

```python
from models.shortcut_manager import ShortcutManager

class WritingToolApp:
    def __init__(self):
        ...
        self.shortcut_manager = ShortcutManager()

    def register_hotkey(self):
        # App global hotkey
        app_shortcut = self.config.get("shortcut", "ctrl+space")
        self.shortcut_manager.register(app_shortcut, self._on_app_hotkey)
        self._register_command_shortcuts()
        self.shortcut_manager.restart()

    def _on_app_hotkey(self):
        if self.paused:
            return
        self.hotkey_triggered_signal.emit()

    def _register_command_shortcuts(self):
        self.shortcut_manager.unregister_all_commands()
        for cmd in self.command_manager.commands:
            if cmd.keyboard_shortcut:
                self.shortcut_manager.register(
                    cmd.keyboard_shortcut,
                    lambda c=cmd: self._trigger_command_shortcut(c)
                )

    def _trigger_command_shortcut(self, command: Command):
        if self.paused:
            return
        # Capture selected text rồi execute command — giống flow hotkey thông thường
        # nhưng skip popup, đi thẳng vào process_option
        QtCore.QTimer.singleShot(0, lambda: self._execute_command_from_shortcut(command))

    def refresh_command_shortcuts(self):
        """Gọi sau khi user save changes trong CommandsManagerDialog."""
        self._register_command_shortcuts()
        self.shortcut_manager.restart()

    def exit_app(self):
        self.shortcut_manager.stop()
        self.quit()
```

### Thay thế `start_hotkey_listener()`

`start_hotkey_listener()` hiện tại tự tạo Listener riêng → **xóa hàm này**, thay bằng `ShortcutManager.register()` + `restart()`.

`register_hotkey()` chỉ cần:
```python
def register_hotkey(self):
    app_shortcut = self.config.get("shortcut", "ctrl+space")
    self.shortcut_manager.register(app_shortcut, self._on_app_hotkey)
    self._register_command_shortcuts()
    self.shortcut_manager.restart()
```

### `_execute_command_from_shortcut()`

```python
def _execute_command_from_shortcut(self, command: Command):
    """Execute command trực tiếp từ keyboard shortcut (không qua popup)."""
    # Lấy selected text như bình thường (Ctrl+C capture)
    selected_text = self._get_selected_text()
    # Gọi thẳng process_option với command đã biết
    self.process_option(command, selected_text, custom_change=None)
```

---

## 7. CommandsManagerDialog Update — `ui/CommandsManagerDialog.py`

Sau khi user Save trong CommandEditorDialog:
```python
def _on_command_saved(self, command: Command):
    self.command_manager.update_command(command)
    self.app.refresh_command_shortcuts()  # re-register tất cả shortcuts
    self._refresh_list()
```

---

## 8. SettingsWindow — Cập nhật global hotkey

Khi user đổi global hotkey trong Settings:
```python
def save_settings(self):
    new_shortcut = self.shortcut_input.text()
    
    # Conflict check với command shortcuts
    from models.shortcut_conflict import check_conflict
    result = check_conflict(
        shortcut=new_shortcut,
        app_hotkey="",  # không check với chính nó
        command_shortcuts={
            cmd.id: cmd.keyboard_shortcut
            for cmd in self.app.command_manager.commands
            if cmd.keyboard_shortcut
        },
    )
    if result.has_conflict:
        self._show_conflict_error(result)
        return

    self.app.config["shortcut"] = new_shortcut
    self.app.save_config(self.app.config)
    self.app.register_hotkey()  # re-register tất cả
```

---

## Thứ tự implement

```
1. models/command.py           ← thêm field keyboard_shortcut (1 dòng)
2. models/shortcut_conflict.py ← pure functions, không dependency
3. models/shortcut_manager.py  ← refactor từ start_hotkey_listener()
4. ui/ShortcutEditWidget.py    ← standalone widget
5. ui/CommandEditorDialog.py   ← thêm shortcut section + conflict label
6. WritingToolApp.py           ← replace start_hotkey_listener với ShortcutManager
7. ui/CommandsManagerDialog.py ← gọi refresh_command_shortcuts sau save
8. ui/SettingsWindow.py        ← conflict check khi đổi global hotkey
```

---

## Edge cases

| Case | Handling |
|---|---|
| Hai command cùng shortcut trong file (data corrupt) | Load xong, log warning, chỉ register cái đầu tiên |
| Shortcut là ký tự đơn (VD: chỉ "p") | `ShortcutEditWidget` reject — yêu cầu ít nhất 1 modifier |
| Command shortcut = App hotkey | Conflict detection block trước khi save |
| Xóa command đang có shortcut | `ShortcutManager.unregister()` + `restart()` |
| Đổi global hotkey conflict với command | SettingsWindow check và báo lỗi |
| pynput parse lỗi (shortcut string invalid) | Wrap `HotKey.parse()` trong try/except, log + skip shortcut đó |
| App bị pause (`self.paused = True`) | `_on_app_hotkey` và `_trigger_command_shortcut` đều check `paused` |
| Linux không có permission cho global listener | Đã được handle bởi pynput (existing behavior), không thay đổi |

---

## Out of scope (Phase sau)

- Per-command API key / provider override (cần thêm vào CommandEditorDialog)
- Shortcut display trong popup button (tooltip hoặc badge)
- Disable/enable shortcut per command mà không xóa
