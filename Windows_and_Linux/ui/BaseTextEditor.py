from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication
from ui.AttachmentBar import AttachmentBar, attachment_from_file, attachment_from_qimage

class BaseAITextEdit(QtWidgets.QTextEdit):
    """
    Base class for text editors in the AI Writing Tools project.
    Handles common functionality like image pasting, file dropping, and context menus.
    """
    submit_requested = QtCore.Signal()

    def __init__(self, attachment_bar: AttachmentBar, parent=None):
        super().__init__(parent)
        self._attachment_bar = attachment_bar
        self.setAcceptDrops(True)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
                cursor = self.textCursor()
                cursor.insertText("\n")
                return
            self.submit_requested.emit()
            return

        if event.matches(QKeySequence.StandardKey.Paste):
            mime = QApplication.clipboard().mimeData()
            if mime.hasImage():
                self._handle_image_mime(mime)
                return
            if mime.hasUrls():
                if self._handle_url_mime(mime.urls()):
                    return

        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasImage():
            self._handle_image_mime(mime)
            event.acceptProposedAction()
            return
        if mime.hasUrls():
            if self._handle_url_mime(mime.urls()):
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def _handle_image_mime(self, mime):
        qimage = mime.imageData()
        # imageData() on Windows may return None or an invalid QImage — fallback to clipboard directly
        if not isinstance(qimage, QtGui.QImage) or qimage.isNull():
            qimage = QApplication.clipboard().image()
        if qimage and not qimage.isNull():
            att = attachment_from_qimage(qimage)
            if att:
                self._attachment_bar.add_attachment(att)

    def insertFromMimeData(self, source):
        """Override to capture image paste from right-click menu and Ctrl+V."""
        if source.hasImage():
            self._handle_image_mime(source)
            return
        # Windows right-click paste: source.hasImage() may be False even when clipboard has image
        clipboard_image = QApplication.clipboard().image()
        if not clipboard_image.isNull():
            att = attachment_from_qimage(clipboard_image)
            if att:
                self._attachment_bar.add_attachment(att)
            return
        if source.hasUrls():
            if self._handle_url_mime(source.urls()):
                return
        super().insertFromMimeData(source)

    def canInsertFromMimeData(self, source):
        """Allow paste if contains images or URLs (files)."""
        if source.hasImage() or source.hasUrls():
            return True
        return super().canInsertFromMimeData(source)

    def contextMenuEvent(self, event):
        """Override context menu to handle Image Paste correctly on Windows."""
        menu = self.createStandardContextMenu()
        clipboard_image = QApplication.clipboard().image()
        if not clipboard_image.isNull():
            # Check for Paste action (supports English and Vietnamese labels)
            for action in menu.actions():
                txt = action.text().lower()
                if 'paste' in txt or 'dán' in txt or action.shortcut() == QKeySequence.StandardKey.Paste:
                    action.setEnabled(True)
                    try:
                        action.triggered.disconnect()
                    except Exception:
                        pass
                    action.triggered.connect(self._paste_image_direct)
                    break
        menu.exec(event.globalPos())

    def _paste_image_direct(self):
        clipboard_image = QApplication.clipboard().image()
        if not clipboard_image.isNull():
            att = attachment_from_qimage(clipboard_image)
            if att:
                self._attachment_bar.add_attachment(att)

    def _handle_url_mime(self, urls) -> bool:
        added = False
        for url in urls:
            if url.isLocalFile():
                att = attachment_from_file(url.toLocalFile())
                if att:
                    self._attachment_bar.add_attachment(att)
                    added = True
        return added
