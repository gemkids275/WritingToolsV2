# Phase 6 — Follow-up Attachments Plan

**Ngày tạo**: 2026-04-19  
**Mục tiêu**: Thêm hỗ trợ copy/paste ảnh, drag-drop file, chọn file trong cửa sổ follow-up chat (`ResponseWindow`) — đồng bộ với macOS implementation.  
**Reference**: `macOS/WritingTools/Views/Chat/ResponseView.swift` (xem `followUpAttachments`, `followUpAttachmentsRow`, `handleFileImport`)  
**Target files**: `Windows_and_Linux/`

---

## Tổng quan kiến trúc

```
ResponseWindow (ui/ResponseWindow.py)
├── ChatContentScrollArea   ← hiện có, không đổi nhiều
├── AttachmentBar           ← NEW widget (ui/AttachmentBar.py)
│   └── thumbnails nằm ngang, nút × xóa từng item
└── Input area (bottom)
    ├── AutoResizeTextEdit  ← thay QLineEdit, hỗ trợ paste ảnh & drop
    ├── PaperclipButton     ← mở file picker
    └── SendButton          ← giữ nguyên
```

---

## Chi tiết từng bước

---

### Bước 1 — Tạo `models/attachment.py`

**File cần tạo**: `Windows_and_Linux/models/attachment.py`

```python
from dataclasses import dataclass, field
from enum import Enum


class AttachmentType(Enum):
    IMAGE = "image"
    TEXT = "text"


@dataclass
class Attachment:
    type: AttachmentType
    label: str                  # tên file hiển thị (basename)
    data: bytes | None = None   # raw bytes cho IMAGE
    text: str | None = None     # nội dung cho TEXT
    mime_type: str = "image/png"
```

**Lưu ý**:
- `data` là PNG/JPEG bytes raw — dùng để build base64 khi gửi lên provider
- `text` là nội dung UTF-8 của text file
- Không cần `file_path` — đọc vào bộ nhớ ngay khi add

---

### Bước 2 — Tạo `ui/AttachmentBar.py`

**File cần tạo**: `Windows_and_Linux/ui/AttachmentBar.py`

Widget tái sử dụng, dùng `QScrollArea` nằm ngang. Sẽ được dùng lại ở `CustomPopupWindow` (Phase 2) sau này.

**API**:
```python
class AttachmentBar(QWidget):
    changed = Signal(list)          # emit list[Attachment] mỗi khi thay đổi

    def add_attachment(self, attachment: Attachment): ...
    def remove_attachment(self, index: int): ...
    def get_attachments(self) -> list[Attachment]: ...
    def clear(self): ...
    def is_empty(self) -> bool: ...
```

**UI structure**:
- `QScrollArea` horizontal, `QHBoxLayout` bên trong
- Mỗi item: `QWidget` 60×60px
  - Ảnh: thumbnail `QLabel` + nút `×` overlay góc trên phải
  - Text file: icon file + tên ngắn (truncate nếu quá dài) + nút `×`
- Widget tự ẩn (`hide()`) khi empty, hiện (`show()`) khi có item
- Style: phù hợp với `colorMode` dark/light

**Thumbnail cho ảnh**:
```python
pixmap = QPixmap()
pixmap.loadFromData(attachment.data)
scaled = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
```

---

### Bước 3 — Nâng cấp `ui/ResponseWindow.py`

#### 3a. Thay `QLineEdit` → `FollowUpTextEdit` (auto-resize)

```python
class FollowUpTextEdit(QTextEdit):
    submit_requested = Signal()

    def __init__(self, *args):
        super().__init__(*args)
        self.setMinimumHeight(36)
        self.setMaximumHeight(150)
        self.document().contentsChanged.connect(self._adjust_height)

    def _adjust_height(self):
        doc_h = int(self.document().size().height()) + 12
        self.setFixedHeight(min(max(36, doc_h), 150))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                cursor = self.textCursor()
                cursor.insertText("\n")
                return
            self.submit_requested.emit()
            return

        # Paste handler
        if event.matches(QKeySequence.StandardKey.Paste):
            mime = QApplication.clipboard().mimeData()
            if mime.hasImage():
                self._paste_image(mime)
                return
            if mime.hasUrls():
                handled = self._paste_urls(mime.urls())
                if handled:
                    return
        super().keyPressEvent(event)

    def _paste_image(self, mime):
        # Convert QImage → PNG bytes → Attachment
        ...

    def _paste_urls(self, urls) -> bool:
        # Xử lý file URLs nếu là ảnh/text file
        ...
```

**Lưu ý**: `FollowUpTextEdit` cần tham chiếu đến `AttachmentBar` (inject qua constructor hoặc setter sau khi tạo).

#### 3b. Thêm `AcceptDrops` cho input area

Override `dragEnterEvent` và `dropEvent` trên `FollowUpTextEdit`:

```python
def dragEnterEvent(self, event):
    if event.mimeData().hasUrls() or event.mimeData().hasImage():
        event.acceptProposedAction()
    else:
        super().dragEnterEvent(event)

def dropEvent(self, event):
    mime = event.mimeData()
    if mime.hasImage():
        self._paste_image(mime)
        event.acceptProposedAction()
        return
    if mime.hasUrls():
        self._paste_urls(mime.urls())
        event.acceptProposedAction()
        return
    super().dropEvent(event)
```

#### 3c. Layout mới của input area trong `init_ui()`

Thay thế `bottom_bar` hiện tại:

```
content_layout
└── input_wrapper (QWidget)
    ├── attachment_bar (AttachmentBar) — ẩn khi empty
    └── input_row (QHBoxLayout)
        ├── follow_up_input (FollowUpTextEdit)
        ├── attach_button (QPushButton, icon paperclip)
        └── send_button (QPushButton, icon send)
```

**Paperclip button** mở `QFileDialog.getOpenFileNames`:
```
filter = "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;Text Files (*.txt *.md *.csv *.json *.xml *.py *.js *.ts);;All Files (*)"
```

#### 3d. Hiện attachment thumbnail trong user message bubble

Khi user gửi kèm ảnh, hiện thumbnail nhỏ phía trên text trong bubble (tùy chọn — nếu phức tạp thì ghi chú số lượng đính kèm là đủ, ví dụ: "[2 attachments]\nUser message").

---

### Bước 4 — Cập nhật `send_message()` trong `ResponseWindow`

```python
def send_message(self):
    message = self.input_field.toPlainText().strip()
    attachments = self.attachment_bar.get_attachments()
    if not message and not attachments:
        return

    self.input_field.clear()
    self.attachment_bar.clear()
    self.input_field.setEnabled(False)

    # Build display text cho user bubble
    display_text = message
    if attachments:
        names = ", ".join(a.label for a in attachments)
        display_text = f"[{names}]\n{message}" if message else f"[{names}]"

    text_display = self.chat_area.add_message(display_text, is_user=True)
    # ... zoom sync ...

    self.chat_history.append({"role": "user", "content": message or "(see attachments)"})
    self.start_thinking_animation()
    self.app.process_followup_question(self, message, attachments=attachments)
```

---

### Bước 5 — Cập nhật `process_followup_question()` trong `WritingToolApp.py`

**File**: `Windows_and_Linux/WritingToolApp.py`  
**Method**: `process_followup_question` (~line 844)

Thêm param `attachments=None`:

```python
def process_followup_question(self, response_window, question, attachments=None):
    attachments = attachments or []

    def process_thread():
        # Extract images và text context từ attachments
        images = [a.data for a in attachments if a.type == AttachmentType.IMAGE]
        text_context = "\n\n".join(
            f"[{a.label}]:\n{a.text}"
            for a in attachments
            if a.type == AttachmentType.TEXT and a.text
        )
        full_question = question
        if text_context:
            full_question = f"{question}\n\nAdditional Context:\n{text_context}" if question else text_context

        # Cập nhật chat history với full_question (bao gồm text context)
        response_window.chat_history[-1]["content"] = full_question

        # Truyền images vào provider
        # streaming path:
        for chunk in active_provider.get_response_stream(system_instruction, full_question, images=images):
            ...
        # non-streaming path:
        response_text = active_provider.get_response(system_instruction, full_question, images=images)
```

**Lưu ý**: Cần kiểm tra signature của `get_response_stream` và `get_response` trong `aiprovider.py` — các providers đã hỗ trợ `images` param chưa. Nếu chưa, cần thêm `images=None` vào signature nhưng không cần implement vision logic ngay (Phase 1 là nơi implement vision).

---

## Files cần tạo / sửa

| File | Loại | Thay đổi |
|------|------|----------|
| `models/attachment.py` | **Tạo mới** | Attachment dataclass |
| `ui/AttachmentBar.py` | **Tạo mới** | Horizontal scroll attachment widget |
| `ui/ResponseWindow.py` | **Sửa** | Thay QLineEdit → FollowUpTextEdit, thêm AttachmentBar, paste/drop handler, paperclip button |
| `WritingToolApp.py` | **Sửa nhỏ** | `process_followup_question` thêm param `attachments` |

---

## Files KHÔNG thay đổi trong phase này

- `ui/CustomPopupWindow.py` — sẽ tái sử dụng `AttachmentBar` ở Phase 2
- `aiprovider.py` — chỉ cần đảm bảo `images=None` param tồn tại trong signature
- `models/command_manager.py`, `models/command.py` — không liên quan
- `main.py`, `requirements.txt` — không cần package mới (PySide6 đã có đủ)

---

## Extension points (để dành cho phase sau)

- `CustomPopupWindow` sẽ import `AttachmentBar` từ `ui/AttachmentBar.py` — thiết kế widget phải standalone
- Vision support thực sự (base64 encoding) sẽ được implement ở Phase 1 trong `aiprovider.py`
- Hiện tại nếu provider chưa support images, images list sẽ bị bỏ qua gracefully

---

## Constraints

- Dùng PySide6 (không dùng PyQt5/6) — đã có trong requirements
- Tương thích dark/light mode qua `colorMode` từ `ui/UIUtils.py`
- Không dùng thư viện ngoài ngoài những gì đã có trong `requirements.txt`
- Giữ nguyên backward compatibility: `process_followup_question(window, question)` không truyền attachments vẫn hoạt động bình thường
