# Phase 4 — Command Management (Windows/Linux)

**Ngày tạo**: 2026-04-19  
**Reference**: macOS `Views/Commands/`, `Services/CommandManager.swift`, `Views/Settings/Panes/GeneralSettingsPane.swift`  
**Target**: `Windows_and_Linux/`  
**Priority**: Critical — foundation cho per-command features sau này

---

## Mục tiêu

1. Thêm mục **Commands** trong General Settings (giống macOS):
   - Button "Manage Commands" → mở dialog quản lý toàn bộ commands
   - Checkbox "Open custom prompts in response window"
   - Button "Edit Custom Response Prompt" → chỉnh system prompt khi không có text được chọn
2. CRUD đầy đủ cho commands (built-in + custom)
3. Tương thích ngược với `options.json` hiện tại

---

## Hiện trạng cần biết

| Điểm | Windows/Linux hiện tại |
|---|---|
| Command fields | `prefix`, `instruction`, `icon`, `open_in_window` |
| Lưu trữ | `options.json` (built-in) — không có custom commands |
| Custom instruction (no text) | System prompt hardcode trong `WritingToolApp.py` |
| Settings | Flat layout, không có Commands section |

---

## Các file cần tạo mới

| File | Mô tả |
|---|---|
| `models/__init__.py` | Package init |
| `models/command.py` | Command dataclass |
| `models/command_manager.py` | CRUD + persistence |
| `ui/CommandEditorDialog.py` | Dialog edit 1 command |
| `ui/CommandsManagerDialog.py` | Dialog quản lý tất cả commands |

## Các file cần sửa

| File | Thay đổi |
|---|---|
| `ui/SettingsWindow.py` | Thêm Commands section vào General tab |
| `WritingToolApp.py` | Load commands từ CommandManager thay vì options.json |
| `ui/CustomPopupWindow.py` | Load commands từ CommandManager |

---

## 1. Data Model — `models/command.py`

```python
from dataclasses import dataclass, field
import uuid

@dataclass
class Command:
    name: str
    prompt: str          # system instruction cho AI
    prefix: str          # tiền tố thêm trước user text (VD: "Proofread this:\n\n")
    icon: str            # tên icon hoặc emoji
    use_response_window: bool = False
    is_built_in: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "prefix": self.prefix,
            "icon": self.icon,
            "use_response_window": self.use_response_window,
            "is_built_in": self.is_built_in,
        }

    @staticmethod
    def from_dict(d: dict) -> "Command":
        return Command(
            id=d.get("id", str(uuid.uuid4())),
            name=d["name"],
            prompt=d.get("prompt", d.get("instruction", "")),  # backward compat
            prefix=d.get("prefix", ""),
            icon=d.get("icon", ""),
            use_response_window=d.get("use_response_window", d.get("open_in_window", False)),
            is_built_in=d.get("is_built_in", False),
        )
```

**Lưu ý:** Giữ `prefix` vì logic hiện tại của `WritingToolApp` ghép `prefix + selected_text`. Đây là tương đương với `prompt` field trong macOS (macOS dùng 1 field còn Windows dùng 2).

**Phase 5 sẽ thêm:** `keyboard_shortcut`, `provider_override`, `model_override`.

---

## 2. Command Manager — `models/command_manager.py`

### Persistence strategy

- **Source of truth duy nhất**: `commands.json` (cùng thư mục với `config.json`)
- **First-run migration**: Nếu `commands.json` chưa tồn tại → đọc `options.json` → convert → lưu vào `commands.json`. Sau đó `options.json` không bao giờ được đọc lại
- **Custom instruction prompt** (no-text case): Lưu trong `config.json` key `"custom_instruction_prompt"`

### commands.json format

```json
{
  "version": 1,
  "commands": [
    {
      "id": "uuid-...",
      "name": "Proofread",
      "prompt": "You are a grammar assistant...",
      "prefix": "Proofread this:\n\n",
      "icon": "icons/magnifying-glass",
      "use_response_window": false,
      "is_built_in": true
    }
  ],
  "deleted_built_in_ids": []
}
```

### Class interface

```python
class CommandManager:
    def __init__(self, config_dir: str): ...

    # Queries
    @property
    def commands(self) -> list[Command]: ...          # all (built-in + custom)
    @property
    def built_in_commands(self) -> list[Command]: ...
    @property
    def custom_commands(self) -> list[Command]: ...

    # CRUD
    def add_command(self, command: Command) -> None: ...
    def update_command(self, command: Command) -> None: ...
    def delete_command(self, command_id: str) -> None: ...  # built-in → thêm vào deleted list, ẩn đi
    def reorder_custom_commands(self, new_order: list[str]) -> None: ...  # list of IDs

    # Reset
    def reset_built_ins_to_defaults(self) -> None: ...  # restore các built-in bị ẩn

    # Import / Export
    def export_command(self, command_id: str) -> dict: ...
    def import_command(self, data: dict) -> Command: ...  # tạo copy với UUID mới nếu trùng ID

    # Persistence
    def load(self) -> None: ...   # nếu commands.json chưa có → tự migrate từ options.json rồi save
    def save(self) -> None: ...
```

### Migration logic (chạy đúng 1 lần)

```python
def load(self):
    if not os.path.exists(self.commands_path):
        self._migrate_from_options_json()  # đọc options.json → tạo commands.json
        return
    # đọc commands.json bình thường

def _migrate_from_options_json(self):
    options_path = os.path.join(os.path.dirname(sys.argv[0]), "options.json")
    with open(options_path) as f:
        raw = json.load(f)
    commands = []
    for entry in raw:
        cmd = Command(
            id=_stable_uuid(entry["name"]),  # hash từ name để idempotent
            name=entry["name"],
            prompt=entry.get("instruction", ""),
            prefix=entry.get("prefix", ""),
            icon=entry.get("icon", ""),
            use_response_window=entry.get("open_in_window", False),
            is_built_in=True,
        )
        commands.append(cmd)
    self._commands = commands
    self.save()  # tạo commands.json, sau đó options.json không được đọc lại
```

`_stable_uuid(name)` dùng `uuid.uuid5(uuid.NAMESPACE_DNS, name)` để UUID giống nhau qua mọi lần chạy.

---

## 3. Command Editor Dialog — `ui/CommandEditorDialog.py`

### Layout

```
CommandEditorDialog (QDialog, min 520x480)
├── Name: [QLineEdit]
├── Icon: [QLineEdit, width 80] + [Preview label]
├── ─────────────────────────────────
├── System Prompt (instruction):
│   [QTextEdit, min height 120px]
├── Prefix (prepended before user text):
│   [QLineEdit]  ← tooltip giải thích
├── ─────────────────────────────────
├── [✓] Open response in window
├── ─────────────────────────────────
└── [Cancel]  [Save]
```

**Lưu ý:**
- `prefix` field có tooltip: "Text added before the selected text when sending to AI. Example: 'Proofread this:\n\n'"
- Icon field: nhận emoji hoặc path đến icon file; nếu là path thì hiện preview
- Validate: Name không được trống, không trùng với command khác (case-insensitive)

### Signals

```python
command_saved = Signal(Command)  # emit khi Save được click và validate pass
```

---

## 4. Commands Manager Dialog — `ui/CommandsManagerDialog.py`

### Layout

```
CommandsManagerDialog (QDialog, min 600x500)
├── [Built-in] [Custom]  ← QTabWidget
│
├── Tab: Built-in
│   ├── QListWidget (không reorder được)
│   │   └── Mỗi item: [icon] [name]  [Edit ✏] [Hide 🚫]
│   └── [Restore Hidden Commands]  ← chỉ enable nếu có deleted built-ins
│
├── Tab: Custom
│   ├── QListWidget (drag-to-reorder)
│   │   └── Mỗi item: [icon] [name]  [Edit ✏] [Export ↑] [Delete 🗑]
│   └── [Add Command]  [Import Command]
│
└── [Close]
```

### Per-item widget (custom `QWidget` cho mỗi row)

```
[Icon 24x24] [Name, bold]                    [Edit btn] [Export btn] [Delete btn]
```

Dùng `QListWidgetItem` + `setItemWidget()` thay vì custom delegate.

### Drag-to-reorder (Custom tab only)

```python
list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
# Kết nối model().rowsMoved signal → gọi command_manager.reorder_custom_commands()
```

### Import/Export format

```json
{
  "version": 1,
  "app": "WritingTools",
  "command": {
    "name": "...",
    "prompt": "...",
    "prefix": "...",
    "icon": "...",
    "use_response_window": false
  }
}
```

Export: `QFileDialog.getSaveFileName()` → save `.wtcmd` hoặc `.json`  
Import: `QFileDialog.getOpenFileName()` → validate `app == "WritingTools"` → tạo Command mới với UUID mới

---

## 5. Settings Window — `ui/SettingsWindow.py`

### Thêm vào General tab (sau phần Appearance, trước Save button)

```
Commands
────────────────────────────────────────
  Manage your writing commands.
  [  Manage Commands  ]

  [✓] Open custom prompts in response window
      When unchecked, custom prompts replace selected text inline.

Custom AI Response
────────────────────────────────────────
  Customize the system instruction used when you enter a manual
  description in the popup (no text selected).
  [  Edit Custom Response Prompt  ]
```

### Wiring

```python
# Manage Commands button
manage_btn.clicked.connect(self._open_commands_manager)

def _open_commands_manager(self):
    dialog = CommandsManagerDialog(self.app.command_manager, parent=self)
    dialog.exec()

# Checkbox
open_in_window_cb.setChecked(self.app.config.get("custom_open_in_window", True))
open_in_window_cb.stateChanged.connect(
    lambda state: self.app.config.update({"custom_open_in_window": state == Qt.CheckState.Checked})
)

# Edit Custom Response Prompt
edit_prompt_btn.clicked.connect(self._edit_custom_prompt)

def _edit_custom_prompt(self):
    current_prompt = self.app.config.get(
        "custom_instruction_prompt",
        DEFAULT_CUSTOM_INSTRUCTION_PROMPT  # constant từ WritingToolApp
    )
    dialog = CustomPromptEditorDialog(current_prompt, parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        self.app.config["custom_instruction_prompt"] = dialog.get_prompt()
        self.app.save_config(self.app.config)
```

### CustomPromptEditorDialog (inline trong SettingsWindow hoặc file riêng)

```
CustomPromptEditorDialog (QDialog, 500x400)
├── Label: "System instruction for AI when no text is selected:"
├── QTextEdit (editable, min 200px)
├── [Reset to Default]
└── [Cancel] [Save]
```

---

## 6. WritingToolApp — `WritingToolApp.py`

### Khởi tạo

```python
from models.command_manager import CommandManager

class WritingToolApp:
    def __init__(self):
        ...
        self.command_manager = CommandManager(config_dir=self.config_dir)
        self.command_manager.load()
        ...
```

### Thay thế load options.json

**Hiện tại:**
```python
with open("options.json") as f:
    self.options = json.load(f)
```

**Sau:**
```python
# options.json không còn được đọc trong app nữa
# CommandManager.load() tự migrate từ options.json vào commands.json ở lần chạy đầu tiên
# Từ lần 2 trở đi: chỉ đọc commands.json
self.command_manager = CommandManager(config_dir=self.config_dir)
self.command_manager.load()
```

### Thay thế hardcode custom instruction prompt

**Hiện tại (hardcode):**
```python
system_instruction = "You are a friendly, helpful, compassionate, and endearing AI conversational assistant..."
```

**Sau:**
```python
DEFAULT_CUSTOM_INSTRUCTION_PROMPT = "You are a friendly, helpful, compassionate, and endearing AI conversational assistant..."

system_instruction = self.config.get("custom_instruction_prompt", DEFAULT_CUSTOM_INSTRUCTION_PROMPT)
```

### process_option() update

```python
def process_option(self, option_name: str, ...):
    command = self.command_manager.get_by_name(option_name)
    if command is None:
        return  # unknown command
    
    use_window = command.use_response_window
    # ...rest of logic giống hiện tại, dùng command.prompt và command.prefix
```

---

## 7. CustomPopupWindow — `ui/CustomPopupWindow.py`

### Thay đổi

Thay vì đọc `options.json` trực tiếp, nhận `command_manager` từ app:

```python
class CustomPopupWindow(QWidget):
    def __init__(self, app, ...):
        ...
        self._build_command_buttons(app.command_manager.commands)

    def _build_command_buttons(self, commands: list[Command]):
        for cmd in commands:
            btn = self._make_button(cmd)
            self.buttons_layout.addWidget(btn)
```

---

## Thứ tự implement

```
1. models/command.py           ← foundation, không dependency
2. models/command_manager.py   ← depends on command.py + options.json migration
3. WritingToolApp.py           ← wire command_manager, replace hardcode prompt
4. ui/CustomPopupWindow.py     ← load from command_manager
5. ui/CommandEditorDialog.py   ← standalone dialog
6. ui/CommandsManagerDialog.py ← uses CommandEditorDialog
7. ui/SettingsWindow.py        ← wire everything together
```

---

## Edge cases cần xử lý

| Case | Handling |
|---|---|
| `commands.json` bị corrupt | Log warning, fallback về migrate từ `options.json` |
| Tên command trùng khi import | Append " (Imported)" + UUID mới |
| Built-in bị ẩn hết | "Restore Hidden Commands" luôn available |
| Thứ tự built-in commands | Giữ nguyên thứ tự từ `options.json` gốc |
| `options.json` bị xóa sau migration | Không ảnh hưởng — `commands.json` là source of truth duy nhất |
| User xóa `commands.json` thủ công | App migrate lại từ `options.json` → restore built-in defaults, mất custom commands |
| Icon path không tồn tại | Hiện emoji fallback hoặc generic icon |

---

## Out of scope (Phase 5+)

- Per-command keyboard shortcuts
- Per-command AI provider/model override
- iCloud / remote sync
- Advanced prompt editor (JSON structured mode)
- Drag-to-reorder trong popup window
