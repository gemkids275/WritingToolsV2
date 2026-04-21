from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

class ImagePreviewDialog(QtWidgets.QDialog):
    """Cửa sổ modal hiển thị ảnh phóng to."""
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Layout chính phủ toàn màn hình
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Widget nền mờ
        self.overlay = QtWidgets.QWidget()
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.85);")
        overlay_layout = QtWidgets.QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(20, 20, 20, 20)
        
        # Label hiển thị ảnh
        self.img_label = QtWidgets.QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Scale ảnh nếu lớn hơn màn hình
        scaled_pixmap = self._get_scaled_pixmap(pixmap)
        self.img_label.setPixmap(scaled_pixmap)
        
        overlay_layout.addWidget(self.img_label)
        self.main_layout.addWidget(self.overlay)
        
        # Đóng khi click vào bất kỳ đâu
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Phóng to cửa sổ ra toàn màn hình để làm overlay
        screen_geo = QtWidgets.QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geo)

    def _get_scaled_pixmap(self, pixmap):
        screen_geo = QtWidgets.QApplication.primaryScreen().geometry()
        max_w = screen_geo.width() - 80
        max_h = screen_geo.height() - 80
        
        if pixmap.width() > max_w or pixmap.height() > max_h:
            return pixmap.scaled(
                max_w, max_h, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
        return pixmap

    def mousePressEvent(self, event):
        """Đóng khi click chuột."""
        self.accept()

    def keyPressEvent(self, event):
        """Đóng khi nhấn ESC."""
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

def show_image_preview(pixmap, parent=None):
    """Hàm tiện ích để hiển thị preview."""
    if not pixmap or pixmap.isNull():
        return
    dialog = ImagePreviewDialog(pixmap, parent)
    dialog.exec()
