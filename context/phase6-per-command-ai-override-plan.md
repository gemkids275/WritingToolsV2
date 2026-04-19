# Phase 6: Per-Command AI Provider, Model & API Key Override

**Ngày tạo**: 2026-04-19
**Mục tiêu**: Mỗi command có thể chọn provider riêng, override model, và dùng API key riêng — thay vì luôn dùng `self.current_provider` global
**Reference**: macOS `CommandModel` + `AppState.getProvider(for:)` + `KeychainManager`

---

## Tổng quan thiết kế

- `commands.json` **KHÔNG BAO GIỜ** chứa API key (dù plaintext hay mã hóa)
- API key per-command lưu trong **keyring** (Windows Credential Manager / libsecret), keyed by `command.id`
- Fallback khi không có keyring: XOR+Base64 obfuscation lưu trong `~/.config/writingtools/cmd_keys.enc.json` với permissions `0600`
- `_resolve_provider()` tạo **provider instance tạm** (không mutate `self.current_provider`) → thread-safe
- Hai chế độ override:
  1. **Standard**: chọn provider đã cấu hình + optional model + optional API key riêng
  2. **Custom**: base URL + model + API key (OpenAI-compatible endpoint tự cấu hình)

---

## Step 0 — Verify model/key attribute names trong `aiprovider.py`

Trước khi implement bất cứ thứ gì, grep để xác nhận tên attribute:

```bash
grep -n "self\.model\|self\.model_name\|self\.api_key\|self\.base_url" Windows_and_Linux/aiprovider.py
```

Điền bảng này dựa trên kết quả thực tế:

| Provider class | attr: model | attr: api_key | attr: base_url |
|---|---|---|---|
| `GeminiProvider` | ? | ? | — |
| `OpenAICompatibleProvider` | ? | ? | ? |
| `AnthropicProvider` | ? | ? | — |
| `MistralProvider` | ? | ? | — |
| `OpenRouterProvider` | ? | ? | — |
| `OllamaProvider` | ? | — | ? |

Bảng này được dùng để xây `_PROVIDER_ATTR_MAP` ở Step 4.

---

## Step 1 — Tạo `secure_storage.py`

**File cần tạo**: `Windows_and_Linux/models/secure_storage.py`

```python
"""
Secure storage cho per-command API keys.
Primary: keyring (Windows Credential Manager / libsecret).
Fallback: XOR+Base64 obfuscation lưu trong ~/.config/writingtools/cmd_keys.enc.json
"""
import json, os, base64, logging

_SERVICE = "WritingTools"
_FALLBACK_PATH = os.path.join(os.path.expanduser("~"), ".config", "writingtools", "cmd_keys.enc.json")
_XOR_KEY = 0x5A  # phải khớp với _XOR_KEY trong aiprovider.py

try:
    import keyring as _keyring
    # Kiểm tra runtime — headless Linux có thể không có backend
    _keyring.get_password("__probe__", "__probe__")
    _KEYRING_AVAILABLE = True
except Exception:
    _KEYRING_AVAILABLE = False
    logging.warning("keyring backend not available, using obfuscated local fallback")


def _obfuscate(key: str) -> str:
    xored = bytes([b ^ _XOR_KEY for b in key.encode()])
    return "enc:" + base64.b64encode(xored).decode()


def _deobfuscate(obfuscated: str) -> str:
    if not obfuscated.startswith("enc:"):
        return obfuscated
    xored = base64.b64decode(obfuscated[4:])
    return bytes([b ^ _XOR_KEY for b in xored]).decode()


def _load_fallback() -> dict:
    if not os.path.exists(_FALLBACK_PATH):
        return {}
    try:
        with open(_FALLBACK_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_fallback(data: dict):
    os.makedirs(os.path.dirname(_FALLBACK_PATH), exist_ok=True)
    with open(_FALLBACK_PATH, "w") as f:
        json.dump(data, f)
    try:
        os.chmod(_FALLBACK_PATH, 0o600)  # chỉ owner đọc được, quan trọng trên Linux
    except Exception:
        pass


def save_command_api_key(command_id: str, api_key: str):
    if not api_key:
        delete_command_api_key(command_id)
        return
    if _KEYRING_AVAILABLE:
        _keyring.set_password(_SERVICE, f"cmd_{command_id}", api_key)
    else:
        data = _load_fallback()
        data[command_id] = _obfuscate(api_key)
        _save_fallback(data)


def get_command_api_key(command_id: str) -> str:
    if _KEYRING_AVAILABLE:
        return _keyring.get_password(_SERVICE, f"cmd_{command_id}") or ""
    data = _load_fallback()
    raw = data.get(command_id, "")
    return _deobfuscate(raw) if raw else ""


def delete_command_api_key(command_id: str):
    if _KEYRING_AVAILABLE:
        try:
            _keyring.delete_password(_SERVICE, f"cmd_{command_id}")
        except Exception:
            pass
    else:
        data = _load_fallback()
        data.pop(command_id, None)
        _save_fallback(data)
```

Thêm `keyring` vào `Windows_and_Linux/requirements.txt`.

---

## Step 2 — Mở rộng `Command` model

**File**: `Windows_and_Linux/models/command.py`

### Thêm 4 field mới vào dataclass

```python
provider_override: str | None = None           # vd: "Gemini (Recommended)", hoặc "custom"
model_override: str | None = None              # vd: "gemini-2.0-flash"
custom_provider_base_url: str | None = None    # chỉ dùng khi provider_override == "custom"
custom_provider_model: str | None = None       # chỉ dùng khi provider_override == "custom"
# API key KHÔNG lưu trong dataclass — dùng secure_storage.get_command_api_key(self.id)
```

### Cập nhật `to_dict()`

```python
"provider_override": self.provider_override,
"model_override": self.model_override,
"custom_provider_base_url": self.custom_provider_base_url,
"custom_provider_model": self.custom_provider_model,
# KHÔNG thêm api_key — không bao giờ lưu key vào JSON
```

### Cập nhật `from_dict()`

```python
provider_override=d.get("provider_override") or None,
model_override=d.get("model_override") or None,
custom_provider_base_url=d.get("custom_provider_base_url") or None,
custom_provider_model=d.get("custom_provider_model") or None,
```

### Export/Import behavior

**Export** (ghi ra file để share): nếu có key trong secure_storage → thêm placeholder `"api_key": "YOUR_API_KEY_HERE"` để user biết phải nhập lại. Không bao giờ export key thật.

**Import** (đọc từ file): nếu field `api_key` tồn tại và không phải placeholder → lưu vào secure_storage, rồi xóa khỏi dict trước khi parse Command.

---

## Step 3 — Cập nhật `CommandManager`

**File**: `Windows_and_Linux/models/command_manager.py`

Import và expose 3 method để các layer khác không cần import `secure_storage` trực tiếp:

```python
from models.secure_storage import save_command_api_key, get_command_api_key, delete_command_api_key

def save_command_api_key(self, command_id: str, api_key: str):
    save_command_api_key(command_id, api_key)

def get_command_api_key(self, command_id: str) -> str:
    return get_command_api_key(command_id)
```

Trong `delete_command()`: gọi `delete_command_api_key(command.id)` để cleanup key khi xóa command.

---

## Step 4 — Thêm `_resolve_provider()` vào `WritingToolApp`

**File**: `Windows_and_Linux/WritingToolApp.py`

### Thêm map attribute (điền sau Step 0)

```python
# Điền <attr_name> dựa trên kết quả grep ở Step 0
_PROVIDER_ATTR_MAP: dict[str, dict[str, str | None]] = {
    "Gemini (Recommended)": {"model": "<attr_name>", "api_key": "<attr_name>"},
    "OpenAI Compatible":    {"model": "<attr_name>", "api_key": "<attr_name>"},
    "Anthropic":            {"model": "<attr_name>", "api_key": "<attr_name>"},
    "Mistral":              {"model": "<attr_name>", "api_key": "<attr_name>"},
    "OpenRouter":           {"model": "<attr_name>", "api_key": "<attr_name>"},
    "Ollama":               {"model": "<attr_name>", "api_key": None},  # local, không cần key
}
```

### Thêm method `_resolve_provider()`

```python
import copy
from models.secure_storage import get_command_api_key

def _resolve_provider(self, command=None):
    """
    Trả về provider instance phù hợp cho command.
    Không bao giờ mutate self.current_provider.
    """
    if not command or not command.provider_override:
        return self.current_provider

    # Chế độ Custom: OpenAI-compatible endpoint do user tự cấu hình
    if command.provider_override == "custom":
        base_url = (command.custom_provider_base_url or "").strip()
        model    = (command.custom_provider_model or "").strip()
        api_key  = get_command_api_key(command.id)
        if not base_url or not model:
            raise ValueError(
                f"Command '{command.name}': custom provider thiếu Base URL hoặc Model."
            )
        from aiprovider import OpenAICompatibleProvider
        tmp = OpenAICompatibleProvider(self)
        tmp.load_config({"base_url": base_url, "model": model, "api_key": api_key})
        return tmp

    # Chế độ Standard: tìm provider đã cấu hình
    provider = next(
        (p for p in self.providers if p.provider_name == command.provider_override),
        None,
    )
    if not provider:
        logging.warning(f"Provider '{command.provider_override}' not found, dùng provider mặc định")
        return self.current_provider

    model_override   = command.model_override
    api_key_override = get_command_api_key(command.id)

    # Không có gì cần override → dùng instance gốc
    if not model_override and not api_key_override:
        return provider

    # Có override → tạo shallow copy, set lại attr, reinit client
    attrs     = _PROVIDER_ATTR_MAP.get(command.provider_override, {})
    model_attr = attrs.get("model")
    key_attr   = attrs.get("api_key")

    tmp = copy.copy(provider)
    if model_override and model_attr:
        setattr(tmp, model_attr, model_override)
    if api_key_override and key_attr:
        setattr(tmp, key_attr, api_key_override)
    tmp.after_load()  # reinit API client với config mới
    return tmp
```

---

## Step 5 — Tích hợp vào `process_option_thread`

**File**: `Windows_and_Linux/WritingToolApp.py`

Ở đầu `process_option_thread`, resolve provider trước khi gọi API:

```python
command = self.command_manager.get_command(option_id_or_name)
if not command:
    command = self.command_manager.get_by_name(option_id_or_name)

try:
    active_provider = self._resolve_provider(command)
except ValueError as e:
    self.show_message_signal.emit("Provider Error", str(e))
    return
```

Thay **toàn bộ** `self.current_provider.get_response(...)` và `self.current_provider.get_response_stream(...)` trong hàm này thành `active_provider.get_response(...)` / `active_provider.get_response_stream(...)`.

Tương tự, cập nhật method `cancel()` trong `WritingToolApp` để cancel đúng instance đang chạy (lưu `active_provider` vào `self._active_provider` trước khi gọi API, dùng trong `cancel()`).

---

## Step 6 — UI `CommandEditorDialog`

**File**: `Windows_and_Linux/ui/CommandEditorDialog.py`

### Section "AI Override" — thêm sau phần Keyboard Shortcut

**Layout:**

```
┌─ AI Override (optional) ─────────────────────────────────────┐
│  [ ] Use custom AI provider for this command                  │
│                                                               │
│  Provider:  [Gemini / Anthropic / Custom OpenAI... ▼]        │
│  Model:     [________________________]  placeholder="Default" │
│  API Key:   [••••••••••••••••••••••] [👁]                     │
│             ℹ Leave blank to use your global key              │
│                                                               │
│  (chỉ hiện khi chọn "Custom OpenAI-compatible")               │
│  Base URL:  [https://api.example.com/v1_______________]       │
└───────────────────────────────────────────────────────────────┘
```

### Widgets cần thêm

```python
self.override_checkbox  = QCheckBox("Use custom AI provider for this command")
self.provider_combo     = QComboBox()   # populate: self._app.providers names + "Custom OpenAI-compatible"
self.model_input        = QLineEdit()   # placeholder "Default model"
self.api_key_input      = QLineEdit()   # echoMode = Password
self.show_key_btn       = QPushButton("Show")
self.base_url_label     = QLabel("Base URL:")
self.base_url_input     = QLineEdit()   # chỉ hiện khi custom
```

### Signals

```python
self.override_checkbox.toggled.connect(self._on_override_toggled)
self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
self.show_key_btn.clicked.connect(self._toggle_key_visibility)
```

### Logic toggle

```python
def _on_override_toggled(self, checked: bool):
    for w in [self.provider_combo, self.model_input,
              self.api_key_input, self.show_key_btn]:
        w.setEnabled(checked)
    if checked:
        self._on_provider_changed(self.provider_combo.currentText())
    else:
        self.base_url_label.hide()
        self.base_url_input.hide()

def _on_provider_changed(self, name: str):
    is_custom = (name == "Custom OpenAI-compatible")
    self.base_url_label.setVisible(is_custom)
    self.base_url_input.setVisible(is_custom)

def _toggle_key_visibility(self):
    from PySide6.QtWidgets import QLineEdit
    if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.show_key_btn.setText("Hide")
    else:
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key_btn.setText("Show")
```

### Khởi tạo từ existing command

```python
if self.command and self.command.provider_override:
    self.override_checkbox.setChecked(True)
    provider_name = "Custom OpenAI-compatible" if self.command.provider_override == "custom" \
                    else self.command.provider_override
    idx = self.provider_combo.findText(provider_name)
    if idx >= 0:
        self.provider_combo.setCurrentIndex(idx)
    self.model_input.setText(self.command.model_override or "")
    self.base_url_input.setText(self.command.custom_provider_base_url or "")
    # API key: không hiện giá trị thật — chỉ báo đã có
    if self._app:
        existing_key = self._app.command_manager.get_command_api_key(self.command.id)
        if existing_key:
            self.api_key_input.setPlaceholderText("••• Saved •••  (re-enter to change)")
        else:
            self.api_key_input.setPlaceholderText("Leave blank to use global key")
```

### Cập nhật `get_command_data()`

```python
def get_command_data(self) -> dict:
    data = {
        # ... existing fields (name, prompt, prefix, icon, ...) ...
        "provider_override": None,
        "model_override": None,
        "custom_provider_base_url": None,
        "custom_provider_model": None,
    }
    if self.override_checkbox.isChecked():
        selected = self.provider_combo.currentText()
        if selected == "Custom OpenAI-compatible":
            data["provider_override"] = "custom"
            data["custom_provider_base_url"] = self.base_url_input.text().strip() or None
            data["custom_provider_model"]    = self.model_input.text().strip() or None
        else:
            data["provider_override"] = selected
            data["model_override"]    = self.model_input.text().strip() or None
    return data

def get_api_key_input(self) -> str:
    """Trả về API key user vừa nhập. Rỗng = không thay đổi."""
    return self.api_key_input.text().strip()
```

### Trong `CommandsManagerDialog` — sau khi dialog accept

```python
if dialog.exec() == QDialog.Accepted:
    data = dialog.get_command_data()
    command = Command.from_dict({**data, "id": existing_cmd.id if existing_cmd else None})
    self.app.command_manager.save_or_update(command)

    new_key = dialog.get_api_key_input()
    if new_key:
        self.app.command_manager.save_command_api_key(command.id, new_key)
    elif not data.get("provider_override"):
        # Override bị tắt → xóa key cũ nếu có
        from models.secure_storage import delete_command_api_key
        delete_command_api_key(command.id)
```

---

## Security checklist

- [ ] `commands.json` không chứa API key (dù plaintext hay obfuscated)
- [ ] Export JSON: key thật được thay bằng `"YOUR_API_KEY_HERE"`
- [ ] Import JSON: placeholder bị bỏ qua, không lưu vào secure_storage
- [ ] Fallback file `cmd_keys.enc.json`: permissions `0600` sau khi tạo/ghi
- [ ] Không log API key ra console hay file trong bất kỳ trường hợp nào
- [ ] `api_key_input` dùng `echoMode=Password` — không hiện plaintext mặc định
- [ ] Giá trị key thật không bao giờ populate lại vào UI — chỉ hiện placeholder "Saved"

---

## Thứ tự implement

```
Step 0  →  verify attr names (bắt buộc làm đầu tiên)
Step 1  →  secure_storage.py (độc lập, có thể test riêng)
Step 2  →  Command model (thêm 4 field)
Step 3  →  CommandManager (expose 3 method)
Step 4  →  _resolve_provider() trong WritingToolApp
Step 5  →  process_option_thread dùng active_provider
Step 6  →  UI CommandEditorDialog + CommandsManagerDialog
```

---

## Files cần thay đổi

| File | Thay đổi |
|---|---|
| `models/secure_storage.py` | **Tạo mới** |
| `models/command.py` | Thêm 4 field, cập nhật to_dict/from_dict |
| `models/command_manager.py` | Thêm 3 method, gọi delete khi xóa command |
| `WritingToolApp.py` | Thêm `_PROVIDER_ATTR_MAP`, `_resolve_provider()`, cập nhật `process_option_thread` và `cancel()` |
| `ui/CommandEditorDialog.py` | Thêm section AI Override với 7 widget |
| `ui/CommandsManagerDialog.py` | Gọi `get_api_key_input()` và lưu key sau accept |
| `requirements.txt` | Thêm `keyring` |
