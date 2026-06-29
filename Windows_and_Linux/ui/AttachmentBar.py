import io
import os

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget

from models.attachment import Attachment, AttachmentType
from ui.UIUtils import colorMode
from ui.ImagePreview import show_image_preview


class AttachmentThumbnail(QWidget):
    remove_requested = Signal(int)

    def __init__(self, attachment: Attachment, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(64, 64)
        self._build(attachment)

    def _build(self, attachment: Attachment):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        container = QWidget(self)
        container.setFixedSize(64, 64)
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {'#3a3a3a' if colorMode == 'dark' else '#e8e8e8'};
                border-radius: 6px;
                border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
            }}
        """)

        if attachment.type == AttachmentType.IMAGE and attachment.data:
            pixmap = QPixmap()
            pixmap.loadFromData(attachment.data)
            scaled = pixmap.scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            img_label = QLabel(container)
            img_label.setPixmap(scaled)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setGeometry(4, 4, 56, 56)
            img_label.setCursor(Qt.CursorShape.PointingHandCursor)
            img_label.mousePressEvent = lambda e: show_image_preview(pixmap, self.window())
        else:
            # Text file — icon + tên ngắn
            name_label = QLabel(container)
            display = attachment.label if len(attachment.label) <= 8 else attachment.label[:7] + "…"
            name_label.setText(f"📄\n{display}")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-size: 10px; background: transparent; border: none;")
            name_label.setGeometry(2, 8, 60, 48)
            name_label.setWordWrap(True)

        # Nút × góc trên phải
        remove_btn = QPushButton("×", container)
        remove_btn.setFixedSize(16, 16)
        remove_btn.move(46, 2)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#666' if colorMode == 'dark' else '#999'};
                color: white;
                border-radius: 8px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {'#e53935' if colorMode == 'dark' else '#e53935'};
            }}
        """)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.index))

        layout.addWidget(container)


class AttachmentBar(QWidget):
    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: list[Attachment] = []
        self._build_ui()
        self.hide()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setFixedHeight(76)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._row = QHBoxLayout(self._inner)
        self._row.setContentsMargins(4, 4, 4, 4)
        self._row.setSpacing(8)
        self._row.addStretch()

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

    def _rebuild(self):
        # Xóa hết items cũ (trừ stretch cuối)
        while self._row.count() > 1:
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, att in enumerate(self._attachments):
            thumb = AttachmentThumbnail(att, i)
            thumb.remove_requested.connect(self._on_remove)
            self._row.insertWidget(self._row.count() - 1, thumb)

        self.setVisible(len(self._attachments) > 0)
        self.changed.emit(list(self._attachments))

    def _on_remove(self, index: int):
        if 0 <= index < len(self._attachments):
            self._attachments.pop(index)
            self._rebuild()

    def add_attachment(self, attachment: Attachment):
        self._attachments.append(attachment)
        self._rebuild()

    def get_attachments(self) -> list[Attachment]:
        return list(self._attachments)

    def clear(self):
        self._attachments.clear()
        self._rebuild()

    def is_empty(self) -> bool:
        return len(self._attachments) == 0


def attachment_from_file(path: str) -> Attachment | None:
    """Đọc file từ đĩa và trả về Attachment phù hợp, hoặc None nếu không hỗ trợ."""
    IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.tif'}
    TEXT_EXTS = {'.txt', '.md', '.csv', '.json', '.xml', '.py', '.js', '.ts',
                 '.html', '.css', '.yaml', '.yml', '.toml', '.ini', '.log'}

    ext = os.path.splitext(path)[1].lower()
    label = os.path.basename(path)

    if ext in IMAGE_EXTS:
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
            '.webp': 'image/webp', '.bmp': 'image/bmp',
            '.tiff': 'image/tiff', '.tif': 'image/tiff',
        }
        try:
            with open(path, 'rb') as f:
                data = f.read()
            return Attachment(
                type=AttachmentType.IMAGE,
                label=label,
                data=data,
                mime_type=mime_map.get(ext, 'image/png')
            )
        except OSError:
            return None

    if ext in TEXT_EXTS:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            return Attachment(type=AttachmentType.TEXT, label=label, text=text, mime_type='text/plain')
        except OSError:
            return None

    return None


def attachment_from_qimage(qimage: QtGui.QImage, label: str = "pasted_image.png") -> Attachment | None:
    """Chuyển QImage từ clipboard thành Attachment IMAGE."""
    buf = QtCore.QByteArray()
    buf_io = QtCore.QBuffer(buf)
    buf_io.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    qimage.save(buf_io, "PNG")
    buf_io.close()
    data = bytes(buf.data())
    if not data:
        return None
    return Attachment(type=AttachmentType.IMAGE, label=label, data=data, mime_type='image/png')
