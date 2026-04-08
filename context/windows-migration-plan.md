# Windows Migration Plan: macOS → Windows/Linux Feature Parity

**Ngày tạo**: 2026-04-08  
**Mục tiêu**: Nâng cấp Windows/Linux version lên ngang tầm macOS version  
**Reference codebase**: `macOS/WritingTools/`  
**Target codebase**: `Windows_and_Linux/`

---

## Tính năng hiện tại của macOS

### AI Providers (7 providers)
- Gemini (với vision support)
- OpenAI + compatible endpoints
- Anthropic (Claude)
- Mistral
- Ollama (local, với vision)
- OpenRouter (multi-model aggregator)
- LocalModelProvider (generic local LLM)
- CustomProvider (user-configurable endpoint)
- Per-command provider/model/API key override
- Streaming support cho tất cả providers

### Commands
- 8 built-in commands: Proofread, Rewrite, Friendly, Professional, Concise, Summary, Key Points, Table
- Custom Instruction command
- Full CRUD UI cho custom commands
- Icon picker (SF Symbols)
- Per-command keyboard shortcut
- Per-command provider/model override
- Toggle inline replacement vs response window
- Advanced prompt editor
- Export/import commands (JSON)
- iCloud sync

### Input / Attachments
- Text selection (via Accessibility API, không dùng clipboard)
- Image selection (screenshots, selected images)
- File attachments: ảnh (PNG, JPG, JPEG, GIF, WebP, HEIC, TIFF, BMP) + text files (UTF-8)
- Paste từ clipboard: text, ảnh, file URLs
- OCR fallback khi input là ảnh
- Attachment thumbnails UI với scroll ngang

### Popup Window
- Custom text input (TextEditor, min 36px → max 300px, scroll dọc)
- Grid 2 cột cho command buttons
- Edit mode để manage commands inline
- Attachment panel với drag-to-scroll ngang
- File importer
- Enter để gửi, Alt/Shift+Enter xuống dòng

### Response Window
- Streaming display
- Follow-up chat với history
- Markdown rendering
- Copy button
- Font size controls (Cmd+/-/0)
- Follow-up attachments (ảnh + file)

### Settings
- 5+ panes: General, AI Provider, Appearance
- Per-provider settings panel (7 providers)
- Keychain-backed API key storage
- iCloud command sync toggle
- Hotkey configuration
- Language/theme selection
- Reset/recovery tools

### Onboarding
- 5 bước: Welcome → Permissions → Provider Setup → Customization → Finish
- Permission status indicators
- Provider-specific setup guidance

### Keyboard Shortcuts
- 1 global hotkey
- Tối đa 10 per-command shortcuts
- Hotkey pause toggle

### Security
- API keys lưu trong macOS Keychain
- Security-scoped resource access cho file picker

### Sync
- iCloud KV store cho commands (opt-in)
- Conflict resolution + quota monitoring

---

## Tình trạng Windows/Linux hiện tại

### AI Providers (3 providers)
- Gemini
- OpenAI-compatible (generic)
- Ollama
- Không có per-command override
- Không có streaming
- Không có vision/image support

### Commands
- 8 built-in commands (JSON-defined trong `options.json`)
- Có UI edit cơ bản (ButtonEditDialog)
- Không có keyboard shortcuts per command
- Không có provider override per command
- Không có export/import
- Không có cloud sync

### Input
- Text selection via clipboard simulation (Ctrl+C)
- Không có image/file attachment
- Không có paste handler cho ảnh

### UI
- Popup window đơn giản (buttons + custom text field)
- Response window với Markdown rendering
- Follow-up chat (không có attachments)
- Settings window flat layout

### Settings
- JSON-based config (`config.json`)
- API keys lưu plaintext (XOR obfuscation từ v8)
- Provider selection global
- Hotkey config

### Điểm mạnh của Windows/Linux (không có trên macOS)
- Localization: gettext-based i18n (EN + IT)
- Zoom controls trong response window (Ctrl+Wheel)
- Autostart manager
- Spam detection cho hotkey

---

## Migration Plan

---

### Phase 1 — AI Provider Expansion (Critical)
**Mục tiêu**: Thêm Anthropic, Mistral, OpenRouter; thêm vision support cho Gemini + Ollama

#### 1.1 Thêm Anthropic Provider
**File cần tạo**: `Windows_and_Linux/aiprovider.py` (thêm class mới)

```python
class AnthropicProvider(AIProvider):
    # API: https://api.anthropic.com/v1/messages
    # Header: x-api-key, anthropic-version: 2023-06-01
    # Models: claude-3-5-sonnet-latest, claude-3-5-haiku-latest, claude-3-opus-latest
    # Vision: base64 image trong content array
```

**Settings cần thêm** trong `config.json`:
```json
"anthropic_api_key": "",
"anthropic_model": "claude-3-5-sonnet-latest"
```

**UI cần thêm** trong `SettingsWindow.py`:
- Dropdown model selector
- API key input

#### 1.2 Thêm Mistral Provider
**File**: `aiprovider.py`

```python
class MistralProvider(AIProvider):
    # API: https://api.mistral.ai/v1/chat/completions (OpenAI-compatible)
    # Models: mistral-large-latest, mistral-small-latest, open-mistral-nemo
```

#### 1.3 Thêm OpenRouter Provider
**File**: `aiprovider.py`

```python
class OpenRouterProvider(AIProvider):
    # API: https://openrouter.ai/api/v1/chat/completions
    # Header: HTTP-Referer, X-Title
    # Free tier: nhiều models miễn phí
```

#### 1.4 Vision Support cho Gemini
**File**: `aiprovider.py` — class `GeminiProvider`

```python
# Thêm image base64 vào parts:
{
    "inline_data": {
        "mime_type": "image/png",
        "data": "<base64>"
    }
}
```

#### 1.5 Vision Support cho OpenAI-compatible
**File**: `aiprovider.py` — class `OpenAICompatibleProvider`

```python
# Thêm image_url part vào content:
{
    "type": "image_url",
    "image_url": {"url": f"data:{mime};base64,{base64}"}
}
```

#### 1.6 Streaming Support
**File**: `aiprovider.py` — thêm method `process_text_streaming()` cho tất cả providers

```python
def process_text_streaming(self, system_prompt, user_prompt, images=None, callback=None):
    # Stream chunks, gọi callback(chunk) cho mỗi token
```

**File**: `ResponseWindow.py` — cập nhật để handle streaming

---

### Phase 2 — Attachment System (High)
**Mục tiêu**: Cho phép đính kèm ảnh và text file vào custom instruction

#### 2.1 Attachment Model
**File cần tạo**: `Windows_and_Linux/models/attachment.py`

```python
from dataclasses import dataclass
from enum import Enum

class AttachmentType(Enum):
    IMAGE = "image"
    TEXT = "text"
    FILE = "file"

@dataclass
class Attachment:
    type: AttachmentType
    data: bytes | None = None
    text: str | None = None
    label: str | None = None
    file_path: str | None = None
    
    @property
    def display_name(self): ...
    @property
    def icon_name(self): ...
```

#### 2.2 Attachment UI trong Popup
**File**: `ui/CustomPopupWindow.py`

Cần thêm:
- Attachment thumbnails row (horizontal scroll) — dùng `QScrollArea` + `QHBoxLayout`
- Paperclip button để open file dialog
- Remove button trên mỗi thumbnail
- Paste handler cho ảnh từ clipboard

```python
# File dialog hỗ trợ:
# - Images: *.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff
# - Text files: *.txt *.md *.csv *.json *.xml *.py *.js *.ts ...

def open_file_dialog(self):
    files, _ = QFileDialog.getOpenFileNames(
        self, "Attach File", "",
        "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;Text Files (*.txt *.md *.csv *.json);;All Files (*)"
    )
    for f in files:
        self.add_attachment(f)
```

#### 2.3 Paste Handler
**File**: `ui/CustomPopupWindow.py`

```python
def keyPressEvent(self, event):
    if event.matches(QKeySequence.StandardKey.Paste):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            # Convert QImage to PNG bytes, add as image attachment
            ...
        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    self.add_attachment(url.toLocalFile())
        # else: let default paste handle text
        return
    super().keyPressEvent(event)
```

#### 2.4 CommandExecutionEngine update
**File**: `WritingToolApp.py`

```python
def execute_custom_instruction(self, instruction, attachments):
    combined_images = []
    attachment_context = ""
    
    for att in attachments:
        if att.type == AttachmentType.IMAGE:
            combined_images.append(att.data)
        elif att.type in (AttachmentType.TEXT, AttachmentType.FILE):
            label = att.label or att.file_path or "Context"
            attachment_context += f"\n[{label}]:\n{att.text}\n"
    
    user_prompt = instruction
    if selected_text:
        user_prompt = f"User's instruction: {instruction}\n\nText:\n{selected_text}"
    if attachment_context:
        user_prompt += f"\n\nAdditional Context:\n{attachment_context}"
    
    return provider.process_text(system_prompt, user_prompt, images=combined_images)
```

---

### Phase 3 — Provider Expansion Settings UI (High)
**Mục tiêu**: Settings UI cho các provider mới

#### 3.1 Refactor SettingsWindow
**File**: `ui/SettingsWindow.py`

Cấu trúc hiện tại: flat layout  
Cấu trúc mới: tabbed/sidebar layout với panels per provider

```
Settings Window
├── General
│   ├── Hotkey
│   ├── Language
│   ├── Theme
│   └── Autostart
├── AI Provider
│   ├── Provider selector dropdown
│   └── [Dynamic panel per provider]
│       ├── Gemini Panel (API key, model)
│       ├── OpenAI Panel (API key, model, base URL, org, project)
│       ├── Anthropic Panel (API key, model)
│       ├── Mistral Panel (API key, model)
│       ├── Ollama Panel (base URL, model, image mode)
│       └── OpenRouter Panel (API key, model)
└── About
```

#### 3.2 Secure Storage
**Thay thế**: XOR obfuscation  
**Windows**: `keyring` library → Windows Credential Manager  
**Linux**: `keyring` library → libsecret / KWallet  

```python
import keyring

def save_api_key(provider_name, key):
    keyring.set_password("WritingTools", provider_name, key)

def get_api_key(provider_name):
    return keyring.get_password("WritingTools", provider_name) or ""
```

**Package**: thêm `keyring` vào `requirements.txt`

---

### Phase 4 — Custom Command UI (Critical)
**Mục tiêu**: Full CRUD UI cho commands, ngang tầm macOS

#### 4.1 Command Model
**File cần tạo**: `Windows_and_Linux/models/command.py`

```python
@dataclass
class Command:
    id: str  # UUID
    name: str
    prompt: str
    icon: str  # emoji hoặc icon name
    use_response_window: bool = False
    keyboard_shortcut: str | None = None
    provider_override: str | None = None
    model_override: str | None = None
    is_built_in: bool = False
```

#### 4.2 CommandManager
**File cần tạo**: `Windows_and_Linux/models/command_manager.py`

```python
class CommandManager:
    def load_commands(self) -> list[Command]: ...   # từ options.json
    def save_commands(self, commands): ...
    def add_command(self, command): ...
    def update_command(self, command): ...
    def delete_command(self, id): ...
    def export_commands(self, path): ...
    def import_commands(self, path): ...
```

#### 4.3 Command Editor Dialog
**File cần tạo**: `Windows_and_Linux/ui/CommandEditorDialog.py`

```
CommandEditorDialog (QDialog)
├── Name input (QLineEdit)
├── System prompt (QTextEdit)
├── Icon selector (emoji input hoặc simple picker)
├── Use response window (QCheckBox)
├── Keyboard shortcut (QKeySequenceEdit)
├── Provider override (QComboBox, optional)
├── Model override (QLineEdit, optional)
└── Save / Cancel buttons
```

#### 4.4 Commands Manager View
**File cần tạo**: `Windows_and_Linux/ui/CommandsManagerDialog.py`

```
CommandsManagerDialog (QDialog)
├── Command list (QListWidget)
│   └── [each item: icon + name + edit + delete buttons]
├── Add Command button
├── Import / Export buttons
└── Close button
```

#### 4.5 Popup cập nhật
**File**: `ui/CustomPopupWindow.py`

- Thêm edit mode toggle (pencil icon)
- Khi edit mode: hiện edit/delete button trên mỗi command button
- Thêm "Manage Commands" button ở cuối khi ở edit mode

---

### Phase 5 — Per-Command Keyboard Shortcuts (High)
**Mục tiêu**: Đăng ký global hotkey per command

#### 5.1 Shortcut Registration
**File**: `WritingToolApp.py`

```python
from pynput import keyboard

def register_command_shortcuts(self):
    shortcuts = {}
    for cmd in self.command_manager.commands:
        if cmd.keyboard_shortcut:
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse(cmd.keyboard_shortcut),
                lambda c=cmd: self.execute_command(c)
            )
            shortcuts[cmd.id] = hotkey
    self.command_shortcuts = shortcuts
```

---

### Phase 6 — Follow-up Attachments (High)
**Mục tiêu**: Cho phép đính kèm file trong follow-up questions

#### 6.1 ResponseWindow update
**File**: `ui/ResponseWindow.py`

- Thêm attachment bar giống popup (horizontal scroll thumbnails)
- Paperclip button trong input area
- Paste handler cho ảnh
- Truyền `images` + `attachment_context` vào follow-up call

---

### Phase 7 — Streaming Support (Medium)
**Mục tiêu**: Response window hiển thị streaming chunks

#### 7.1 Provider Streaming
**File**: `aiprovider.py`

Thêm `process_text_streaming()` cho:
- GeminiProvider: `response.stream_generate_content()`
- OpenAI-compatible: `stream=True` + `for chunk in response`
- AnthropicProvider: `with client.messages.stream() as stream`
- OllamaProvider: `ollama.chat(stream=True)`

#### 7.2 ResponseWindow Streaming
**File**: `ui/ResponseWindow.py`

```python
def start_streaming(self, system_prompt, user_prompt, images):
    self.response_text = ""
    
    def stream_worker():
        for chunk in provider.process_text_streaming(system_prompt, user_prompt, images):
            # Use Qt signal to update UI on main thread
            self.chunk_received.emit(chunk)
    
    threading.Thread(target=stream_worker, daemon=True).start()

# Qt Signal
chunk_received = pyqtSignal(str)

@Slot(str)
def on_chunk_received(self, chunk):
    self.response_text += chunk
    self.update_display(self.response_text)
```

---

### Phase 8 — Input Method Update (Medium)
**Mục tiêu**: Popup input field nâng cấp giống macOS

#### 8.1 CustomPopupWindow Input
**File**: `ui/CustomPopupWindow.py`

Hiện tại: `QTextEdit` đơn giản  
Cập nhật:
- Min height 36px, max height 300px — tự co giãn
- Enter gửi, Shift+Enter / Alt+Enter xuống dòng
- Scroll dọc khi quá max height
- Placeholder text

```python
class AutoResizeTextEdit(QTextEdit):
    submit_requested = pyqtSignal()
    
    def __init__(self, *args):
        super().__init__(*args)
        self.setMinimumHeight(36)
        self.setMaximumHeight(300)
        self.document().contentsChanged.connect(self.adjust_height)
    
    def adjust_height(self):
        doc_height = self.document().size().height()
        self.setFixedHeight(min(max(36, int(doc_height) + 10), 300))
    
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                # Insert newline
                cursor = self.textCursor()
                cursor.insertText("\n")
                return
            else:
                self.submit_requested.emit()
                return
        super().keyPressEvent(event)
```

---

### Phase 9 — Onboarding Improvement (Low)
**Mục tiêu**: 5-step onboarding giống macOS

#### 9.1 Multi-step Onboarding
**File**: `ui/OnboardingWindow.py` — refactor thành wizard

```
Step 1: Welcome (app description + logo)
Step 2: Permissions (accessibility check trên Linux/Windows)
Step 3: Provider Setup (chọn provider + nhập API key)
Step 4: Customization (xem/chỉnh commands)
Step 5: Finish (recap + hotkey reminder)
```

---

### Phase 10 — Localization mở rộng (Medium)
**Mục tiêu**: Thêm các ngôn ngữ (macOS hiện chưa có)

Windows/Linux đã có infrastructure gettext tốt — chỉ cần thêm ngôn ngữ:
- Vietnamese (vi) — target cho project này
- German (de)
- French (fr)
- Spanish (es)

---

## Files cần tạo mới

| File | Mô tả | Phase |
|------|-------|-------|
| `models/attachment.py` | Attachment model | 2 |
| `models/command.py` | Command model | 4 |
| `models/command_manager.py` | Command CRUD + persistence | 4 |
| `ui/CommandEditorDialog.py` | Dialog edit 1 command | 4 |
| `ui/CommandsManagerDialog.py` | Quản lý tất cả commands | 4 |
| `ui/AttachmentBar.py` | Reusable attachment UI widget | 2 |

## Files cần sửa

| File | Thay đổi chính | Phase |
|------|----------------|-------|
| `aiprovider.py` | Thêm Anthropic, Mistral, OpenRouter; vision; streaming | 1 |
| `WritingToolApp.py` | Attachment handling, command shortcuts, streaming dispatch | 1,2,5 |
| `ui/CustomPopupWindow.py` | Attachment bar, paste handler, auto-resize input, edit mode | 2,4,8 |
| `ui/ResponseWindow.py` | Streaming display, follow-up attachments | 6,7 |
| `ui/SettingsWindow.py` | Multi-provider panels, keyring integration | 3 |
| `ui/OnboardingWindow.py` | Multi-step wizard | 9 |
| `options.json` | Không đổi format, CommandManager đọc từ đây | 4 |
| `requirements.txt` | Thêm: `keyring`, `anthropic`, `openai` (update), `mistralai` | 1,3 |

## Files không cần thay đổi

- `main.py` — entry point không đổi
- `locales/` — giữ nguyên, thêm ngôn ngữ sau
- `ui/AboutWindow.py` — không cần thay đổi lớn

---

## Thứ tự implementation đề xuất

```
Phase 1 → Phase 3 → Phase 2 → Phase 8 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 9 → Phase 10
```

Lý do:
1. Provider expansion (Ph1) + settings UI (Ph3) trước — foundation cho mọi thứ
2. Attachment system (Ph2) + input UX (Ph8) — user-facing, high impact
3. Command management (Ph4) + shortcuts (Ph5) — power user features
4. Follow-up attachments (Ph6) + streaming (Ph7) — enhanced response window
5. Onboarding (Ph9) + i18n (Ph10) — polish

---

## Constraints & Notes

- **Không dùng iCloud trên Windows/Linux** — thay bằng local file sync hoặc bỏ qua
- **Keyring trên Linux** cần libsecret-1-dev hoặc KWallet → fallback về plaintext nếu không có
- **SF Symbols không có trên Windows** → dùng emoji cho icons hoặc Unicode symbols
- **Accessibility API text capture** trên Windows cần `pywin32` + `UIAutomation` thay cho Accessibility API của macOS; trên Linux cần AT-SPI — đây là refactor lớn, kiểm tra xem Windows/Linux đã handle chưa (hiện đang dùng clipboard Ctrl+C thay thế)
- **Giữ nguyên cấu trúc file hiện tại** — không di chuyển hay đổi tên module lớn để tránh break existing installs
