import logging
import os
import sys

import markdown2
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QScrollArea

from models.attachment import AttachmentType
from ui.AttachmentBar import AttachmentBar, attachment_from_file, attachment_from_qimage
from ui.UIUtils import UIUtils, colorMode
from ui.ImagePreview import show_image_preview
from ui.BaseTextEditor import BaseAITextEdit

_ = lambda x: x


class ClickableLabel(QtWidgets.QLabel):
    """QLabel có thể click để phát tín hiệu."""
    clicked = QtCore.Signal(QtGui.QPixmap)

    def __init__(self, display_pixmap, original_pixmap, parent=None):
        super().__init__(parent)
        self.setPixmap(display_pixmap)
        self.original_pixmap = original_pixmap
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.original_pixmap)


class FollowUpTextEdit(BaseAITextEdit):
    """Auto-resize text input cho follow-up questions, hỗ trợ paste ảnh và drop file."""
    def __init__(self, attachment_bar: 'AttachmentBar', parent=None):
        super().__init__(attachment_bar, parent)
        self.setFixedHeight(72)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def keyPressEvent(self, event):
        # Override to ensure height doesn't change if specialized behavior is needed,
        # but here we mostly just want to trigger submit on Enter.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)):
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class MarkdownTextBrowser(QtWidgets.QTextBrowser):
    """Enhanced text browser for displaying Markdown content with improved sizing"""
    
    def __init__(self, parent=None, is_user_message=False):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.zoom_factor = 1.2
        self.base_font_size = 14
        self.is_user_message = is_user_message
        
        # Critical: Remove scrollbars to prevent extra space
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Set size policies to prevent unwanted expansion
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum
        )
        
        self._apply_zoom()
        
    def _apply_zoom(self):
        new_size = int(self.base_font_size * self.zoom_factor)
        
        # Updated stylesheet with table styling
        self.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {('transparent' if self.is_user_message else '#333' if colorMode == 'dark' else 'white')};
                color: {'#ffffff' if colorMode == 'dark' else '#000000'};
                border: {('none' if self.is_user_message else '1px solid ' + ('#555' if colorMode == 'dark' else '#ccc'))};
                border-radius: 8px;
                padding: 8px;
                margin: 0px;
                font-size: {new_size}px;
                line-height: 1.3;
                width: 100%;
            }}

            /* Table styles */
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 10px 0;
            }}
            
            th, td {{
                border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
                padding: 8px;
                text-align: left;
            }}
            
            th {{
                background-color: {'#444' if colorMode == 'dark' else '#f5f5f5'};
                font-weight: bold;
            }}
            
            tr:nth-child(even) {{
                background-color: {'#3a3a3a' if colorMode == 'dark' else '#f9f9f9'};
            }}
            
            tr:hover {{
                background-color: {'#484848' if colorMode == 'dark' else '#f0f0f0'};
            }}
        """)
        
    def _update_size(self):
        # Calculate correct document width
        available_width = self.viewport().width() - 16  # Account for padding
        self.document().setTextWidth(available_width)
        
        # Get precise content height
        doc_size = self.document().size()
        content_height = doc_size.height()
        
        # Add minimal padding for content
        new_height = int(content_height + 16)  # Reduced total padding
        
        if self.minimumHeight() != new_height:
            self.setMinimumHeight(new_height)
            self.setMaximumHeight(new_height)  # Force fixed height
            
            # Update scroll area if needed
            scroll_area = self.get_scroll_area()
            if scroll_area:
                scroll_area.update_content_height()
                
    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            # Get the main response window
            parent = self.parent()
            while parent and not isinstance(parent, ResponseWindow):
                parent = parent.parent()
                
            if parent:
                if delta > 0:
                    parent.zoom_all_messages('in')
                else:
                    parent.zoom_all_messages('out')
                event.accept()
        else:
            # Pass wheel events to parent for scrolling
            if self.parent():
                self.parent().wheelEvent(event)
            
    def zoom_in(self):
        old_factor = self.zoom_factor
        self.zoom_factor = min(3.0, self.zoom_factor * 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()
        
    def zoom_out(self):
        old_factor = self.zoom_factor
        self.zoom_factor = max(0.5, self.zoom_factor / 1.1)
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()
        
    def reset_zoom(self):
        old_factor = self.zoom_factor
        self.zoom_factor = 1.2  # Reset to default zoom
        if old_factor != self.zoom_factor:
            self._apply_zoom()
            self._update_size()
    
    def get_scroll_area(self):
        """Find the parent ChatContentScrollArea"""
        parent = self.parent()
        while parent:
            if isinstance(parent, ChatContentScrollArea):
                return parent
            parent = parent.parent()
        return None
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_size()


class ChatContentScrollArea(QScrollArea):
    """Improved scrollable container for chat messages with dynamic sizing and proper spacing"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.content_widget = None
        self.layout = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Main container widget with explicit size policy
        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding
        )
        self.setWidget(self.content_widget)
        
        # Main layout with improved spacing
        self.layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.layout.setSpacing(8)  # Reduced spacing between messages
        self.layout.setContentsMargins(15, 15, 15, 15)  # Adjusted margins
        self.layout.addStretch()
        
        # Enhanced scroll area styling
        self.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(128, 128, 128, 0.5);
                min-height: 20px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def add_message(self, text, is_user=False, attachments=None):
        # Remove bottom stretch
        self.layout.takeAt(self.layout.count() - 1)

        # Create message container with improved width
        msg_container = QtWidgets.QWidget()
        msg_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum
        )

        # Message layout with minimal margins
        msg_layout = QtWidgets.QVBoxLayout(msg_container)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(4)

        # Render image attachments inline (user messages only)
        if attachments:
            for att in attachments:
                if att.type == AttachmentType.IMAGE and att.data:
                    pixmap = QtGui.QPixmap()
                    pixmap.loadFromData(att.data)
                    if not pixmap.isNull():
                        max_w, max_h = 220, 160
                        display_pixmap = pixmap
                        if pixmap.width() > max_w or pixmap.height() > max_h:
                            display_pixmap = pixmap.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        
                        img_label = ClickableLabel(display_pixmap, pixmap)
                        img_label.setStyleSheet("border-radius: 6px; margin-bottom: 2px;")
                        img_label.clicked.connect(lambda p: show_image_preview(p, self.window()))
                        msg_layout.addWidget(img_label)

        # Create text display with updated width
        text_display = MarkdownTextBrowser(is_user_message=is_user)
        text_display.markdown_text = text

        # Enable tables extension in markdown2
        html = markdown2.markdown(text, extras=['tables', 'strike'])
        text_display.setHtml(html)

        # Calculate proper text display size using full width
        text_display.document().setTextWidth(self.width() - 20)
        doc_size = text_display.document().size()
        text_display.setMinimumHeight(int(doc_size.height() + 16))

        msg_layout.addWidget(text_display)

        # Copy button row (aligned right)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        copy_btn = QtWidgets.QPushButton(_("Copy"))
        copy_btn.setFixedHeight(22)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {'#888' if colorMode == 'dark' else '#999'};
                border: none;
                font-size: 11px;
                padding: 0 4px;
            }}
            QPushButton:hover {{
                color: {'#ccc' if colorMode == 'dark' else '#333'};
            }}
        """)
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        _icon_suffix = '_dark' if colorMode == 'dark' else '_light'
        _copy_icon = QtGui.QIcon(os.path.join(os.path.dirname(sys.argv[0]), 'icons', f'copy{_icon_suffix}.png'))
        _check_icon = QtGui.QIcon(os.path.join(os.path.dirname(sys.argv[0]), 'icons', f'check{_icon_suffix}.png'))
        copy_btn.setIcon(_copy_icon)
        copy_btn.setIconSize(QtCore.QSize(12, 12))

        def _copy(checked=False, btn=copy_btn, td=text_display, ci=_copy_icon, ki=_check_icon):
            QtWidgets.QApplication.clipboard().setText(td.markdown_text)
            btn.setIcon(ki)
            btn.setText(_("Copied!"))
            QtCore.QTimer.singleShot(1500, lambda: (btn.setIcon(ci), btn.setText(_("Copy"))))

        copy_btn.clicked.connect(_copy)
        btn_row.addWidget(copy_btn)
        msg_layout.addLayout(btn_row)

        self.layout.addWidget(msg_container)
        self.layout.addStretch()

        if hasattr(self.parent(), 'current_text_display'):
            self.parent().current_text_display = text_display

        QtCore.QTimer.singleShot(50, self.post_message_updates)

        return text_display

    def post_message_updates(self):
        """Handle updates after adding a message with proper timing"""
        self.scroll_to_bottom()
        if isinstance(self.parent(), ResponseWindow):
            self.parent()._adjust_window_height()

    def update_content_height(self):
        """Recalculate total content height with improved spacing calculation"""
        total_height = 0
        
        # Calculate height of all messages
        for i in range(self.layout.count() - 1):  # Skip stretch item
            item = self.layout.itemAt(i)
            if item and item.widget():
                widget_height = item.widget().sizeHint().height()
                total_height += widget_height
        
        # Add spacing between messages and margins
        total_height += (self.layout.spacing() * (self.layout.count() - 2))  # Message spacing
        total_height += self.layout.contentsMargins().top() + self.layout.contentsMargins().bottom()
        
        # Set minimum height with some padding
        self.content_widget.setMinimumHeight(total_height + 10)
        
        # Update window height if needed
        if isinstance(self.parent(), ResponseWindow):
            self.parent()._adjust_window_height()

    def scroll_to_bottom(self):
        """Smooth scroll to bottom of content"""
        vsb = self.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def resizeEvent(self, event):
        """Handle resize events with improved width calculations"""
        super().resizeEvent(event)
        
        # Update width for all message displays
        available_width = self.width() - 40  # Account for margins
        for i in range(self.layout.count() - 1):  # Skip stretch item
            item = self.layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                text_display = container.layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    # Recalculate text width and height
                    text_display.document().setTextWidth(available_width)
                    doc_size = text_display.document().size()
                    text_display.setMinimumHeight(int(doc_size.height() + 20))  # Reduced padding


class ResponseWindow(QtWidgets.QWidget):
    """Enhanced response window with improved sizing and zoom handling"""
    
    def __init__(self, app, title=_("Response"), command_id=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.command_id = command_id
        self.original_title = title
        self.setWindowTitle(title)
        self.option = title.replace(" Result", "")
        self.selected_text = None
        self.input_field = None
        self.loading_label = None
        self.loading_container = None
        self.chat_area = None
        self.chat_history = []
        self.current_streaming_display = None
        self.current_streaming_text = ""
        self._ignore_tokens = False
        self._streaming_active = False # New guard

        # Setup thinking animation with full range of dots
        self.thinking_timer = QtCore.QTimer(self)
        self.thinking_timer.timeout.connect(self.update_thinking_dots)
        self.thinking_dots_state = 0
        self.thinking_dots = ["", ".", "..", "..."]  # Now properly includes all states
        self.thinking_timer.setInterval(300)

        self.init_ui()
        logging.debug('Connecting response signals')
        self.app.followup_response_signal.connect(self.handle_followup_response)
        self.app.streaming_token_signal.connect(self.append_token)
        logging.debug('Response signals connected')

        # Set initial size for "Thinking..." state
        initial_width = 500
        initial_height = 350
        self.resize(initial_width, initial_height)
                
    def init_ui(self):
        # Window setup with enhanced flags
        self.setWindowFlags(QtCore.Qt.WindowType.Window | 
                          QtCore.Qt.WindowType.WindowCloseButtonHint | 
                          QtCore.Qt.WindowType.WindowMinimizeButtonHint |
                          QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        self.setMinimumSize(600, 600)
        
        # Main layout setup
        UIUtils.setup_window_and_layout(self)
        content_layout = QtWidgets.QVBoxLayout(self.background)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(10)

        # Top bar with zoom controls
        top_bar = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel(_(self.option))
        title_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        top_bar.addWidget(title_label)
        
        top_bar.addStretch()

        # Zoom label with matched size
        zoom_label = QtWidgets.QLabel(_("Zoom:"))
        zoom_label.setStyleSheet(f"""
            color: {'#aaaaaa' if colorMode == 'dark' else '#666666'};
            font-size: 14px;
            margin-right: 5px;
        """)
        top_bar.addWidget(zoom_label)
        
        # Enhanced zoom controls with swapped order
        zoom_controls = [
            ('plus', _('Zoom In'), lambda: self.zoom_all_messages('in')),
            ('minus', _('Zoom Out'), lambda: self.zoom_all_messages('out')),
            ('reset', _('Reset Zoom'), lambda: self.zoom_all_messages('reset'))
        ]
            
        for icon, tooltip, action in zoom_controls:
            btn = QtWidgets.QPushButton()
            btn.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.argv[0]), 'icons', icon + ('_dark' if colorMode == 'dark' else '_light') + '.png')))
            btn.setStyleSheet(self.get_button_style())
            btn.setToolTip(tooltip)
            btn.clicked.connect(action)
            btn.setFixedSize(30, 30)
            top_bar.addWidget(btn)
            
        content_layout.addLayout(top_bar)

        # Copy controls with matching text size
        copy_bar = QtWidgets.QHBoxLayout()
        copy_hint = QtWidgets.QLabel(_("Select to copy with formatting"))
        copy_hint.setStyleSheet(f"color: {'#aaaaaa' if colorMode == 'dark' else '#666666'}; font-size: 14px;")
        copy_bar.addWidget(copy_hint)
        copy_bar.addStretch()
        
        self.copy_md_btn = QtWidgets.QPushButton(_("Copy All"))
        self.copy_md_btn.setStyleSheet(self.get_button_style())
        self.copy_md_btn.clicked.connect(self.copy_first_response)
        copy_bar.addWidget(self.copy_md_btn)
        content_layout.addLayout(copy_bar)

        # Loading indicator
        loading_container = QtWidgets.QWidget()
        loading_layout = QtWidgets.QHBoxLayout(loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        
        self.loading_label = QtWidgets.QLabel(_("Thinking"))
        self.loading_label.setStyleSheet(f"""
            QLabel {{
                color: {'#ffffff' if colorMode == 'dark' else '#333333'};
                font-size: 18px;
                padding: 20px;
            }}
        """)
        self.loading_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        loading_inner_container = QtWidgets.QWidget()
        loading_inner_container.setFixedWidth(180)
        loading_inner_layout = QtWidgets.QHBoxLayout(loading_inner_container)
        loading_inner_layout.setContentsMargins(0, 0, 0, 0)
        loading_inner_layout.addWidget(self.loading_label)
        
        loading_layout.addStretch()
        loading_layout.addWidget(loading_inner_container)
        loading_layout.addStretch()
        
        content_layout.addWidget(loading_container)
        self.loading_container = loading_container
        
        # Start thinking animation
        self.start_thinking_animation(initial=True)
        
        # Enhanced chat area with full width
        self.chat_area = ChatContentScrollArea()
        self.chat_area.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.chat_area.setMinimumHeight(280)
        content_layout.addWidget(self.chat_area, stretch=1)

        # Input area
        input_wrapper = QtWidgets.QWidget()
        input_wrapper_layout = QtWidgets.QVBoxLayout(input_wrapper)
        input_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        input_wrapper_layout.setSpacing(4)

        # Attachment bar (ẩn khi trống)
        self.attachment_bar = AttachmentBar()
        input_wrapper_layout.addWidget(self.attachment_bar)

        # Textarea full-width
        self.input_field = FollowUpTextEdit(self.attachment_bar)
        self.input_field.setPlaceholderText(_("Ask a follow-up question") + '...')
        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode == 'dark' else 'white'};
                color: {'#ffffff' if colorMode == 'dark' else '#000000'};
                font-size: 14px;
            }}
        """)
        self.input_field.submit_requested.connect(self.send_message)
        input_wrapper_layout.addWidget(self.input_field)

        # Buttons căn phải phía dưới textarea
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        btn_size = 32
        attach_button = QtWidgets.QPushButton("📎")
        attach_button.setFixedSize(btn_size, btn_size)
        attach_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#444' if colorMode == 'dark' else '#f0f0f0'};
                border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                border-radius: 6px;
                font-size: 15px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#555' if colorMode == 'dark' else '#e0e0e0'};
            }}
        """)
        attach_button.setToolTip(_("Attach file"))
        attach_button.clicked.connect(self._open_file_dialog)
        btn_row.addWidget(attach_button)

        send_button = QtWidgets.QPushButton()
        send_button.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'send' + ('_dark' if colorMode == 'dark' else '_light') + '.png')))
        send_button.setFixedSize(btn_size, btn_size)
        send_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#2e7d32' if colorMode == 'dark' else '#4CAF50'};
                border: none;
                border-radius: 6px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: {'#1b5e20' if colorMode == 'dark' else '#45a049'};
            }}
        """)
        send_button.clicked.connect(self.send_message)
        btn_row.addWidget(send_button)

        input_wrapper_layout.addLayout(btn_row)
        input_wrapper.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        content_layout.addWidget(input_wrapper, stretch=0)

    # Method to get first response text
    def get_first_response_text(self):
        """Get the first model response text from chat history"""
        try:
            # Check chat history exists
            if not self.chat_history:
                return None
                
            # Find first assistant message
            for msg in self.chat_history:
                if msg["role"] == "assistant":
                    return msg["content"]
                    
            return None
        except Exception as e:
            logging.error(f"Error getting first response: {e}")
            return None

    def copy_first_response(self):
        """Copy all assistant responses as Markdown"""
        all_responses = "\n\n".join(
            msg["content"] for msg in self.chat_history if msg["role"] == "assistant"
        )
        if all_responses:
            QtWidgets.QApplication.clipboard().setText(all_responses)
            self.copy_md_btn.setText(_("Copied!"))
            QtCore.QTimer.singleShot(1500, lambda: self.copy_md_btn.setText(_("Copy as Markdown")))

    def get_button_style(self):
        return f"""
            QPushButton {{
                background-color: {'#444' if colorMode == 'dark' else '#f0f0f0'};
                color: {'#ffffff' if colorMode == 'dark' else '#000000'};
                border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {'#555' if colorMode == 'dark' else '#e0e0e0'};
            }}
        """

    def update_thinking_dots(self):
        """Update the thinking animation dots with proper cycling"""
        self.thinking_dots_state = (self.thinking_dots_state + 1) % len(self.thinking_dots)
        dots = self.thinking_dots[self.thinking_dots_state]
        
        if self.loading_label.isVisible():
            self.loading_label.setText(_("Thinking")+f"{dots}")
        else:
            self.input_field.setPlaceholderText(_("Thinking")+f"{dots}")
    
    def start_thinking_animation(self, initial=False):
        """Start the thinking animation for either initial load or follow-up questions"""
        self.thinking_dots_state = 0
        
        if initial:
            self.loading_label.setText(_("Thinking"))
            self.loading_label.setVisible(True)
            self.loading_container.setVisible(True)
        else:
            self.input_field.setPlaceholderText(_("Thinking"))
            self.loading_container.setVisible(False)
            
        self.thinking_timer.start()

    def _open_file_dialog(self):
        """Mở file dialog để chọn ảnh hoặc text file đính kèm."""
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            _("Attach File"),
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff);;"
            "Text Files (*.txt *.md *.csv *.json *.xml *.py *.js *.ts *.html *.css *.yaml *.yml *.toml *.ini *.log);;"
            "All Files (*)"
        )
        for path in files:
            att = attachment_from_file(path)
            if att:
                self.attachment_bar.add_attachment(att)

    def stop_thinking_animation(self):
        """Stop the thinking animation"""
        self.thinking_timer.stop()
        self.loading_container.hide()
        self.loading_label.hide()
        self.input_field.setPlaceholderText(_("Ask a follow-up question"))
        self.input_field.setEnabled(True)
        
        # Force layout update
        if self.layout():
            self.layout().invalidate()
            self.layout().activate()

    def zoom_all_messages(self, action='in'):
        """Apply zoom action to all messages in the chat"""
        for i in range(self.chat_area.layout.count() - 1):  # Skip stretch item
            item = self.chat_area.layout.itemAt(i)
            if item and item.widget():
                text_display = item.widget().layout().itemAt(0).widget()
                if isinstance(text_display, MarkdownTextBrowser):
                    if action == 'in':
                        text_display.zoom_in()
                    elif action == 'out':
                        text_display.zoom_out()
                    else:  # reset
                        text_display.reset_zoom()
        
        # Update layout after zooming
        self.chat_area.update_content_height()
        
    def _adjust_window_height(self):
        """Calculate and set the ideal window height"""
        # Skip adjustment if window already has a size
        if hasattr(self, '_size_initialized'):
            return
                
        try:
            # Get content widget height
            content_height = self.chat_area.content_widget.sizeHint().height()
                
            # Calculate other UI elements height
            ui_elements_height = (
                self.layout().contentsMargins().top() +
                self.layout().contentsMargins().bottom() +
                self.input_field.height() +
                self.layout().spacing() * 5 +
                200  # Increased from 185 for taller default height
            )
                
            # Get screen constraints
            screen = QtWidgets.QApplication.screenAt(self.pos())
            if not screen:
                screen = QtWidgets.QApplication.primaryScreen()
                
            # Calculate maximum available height (85% of screen)
            max_height = int(screen.geometry().height() * 0.85)
                
            # Calculate desired height to show more content initially
            desired_content_height = int(content_height * 0.85)  # Show 85% of content
            desired_total_height = min(
                desired_content_height + ui_elements_height,
                max_height
            )
                
            # Set reasonable minimum height
            final_height = max(750, desired_total_height)
                
            # Set width to 600px
            final_width = 600
                
            # Update both width and height
            self.resize(final_width, final_height)
                
            # Center on screen
            frame_geometry = self.frameGeometry()
            screen_center = screen.geometry().center()
            frame_geometry.moveCenter(screen_center)
            self.move(frame_geometry.topLeft())
                
            # Mark size as initialized
            self._size_initialized = True
                
        except Exception as e:
            logging.error(f"Error adjusting window height: {e}")
            self.resize(600, 750)  # fallback size
            self._size_initialized = True

    @Slot(str)
    def append_token(self, token):
        """Append a token to the current streaming message display"""
        if not token or self._ignore_tokens or not self._streaming_active:
            return
            
        if self.current_streaming_display is None:
            self.stop_thinking_animation()
            # Start a new message for streaming
            self.current_streaming_text = token
            self.current_streaming_display = self.chat_area.add_message(self.current_streaming_text)
            
            # Maintain consistent zoom level
            if hasattr(self, 'current_text_display'):
                self.current_streaming_display.zoom_factor = self.current_text_display.zoom_factor
                self.current_streaming_display._apply_zoom()
        else:
            self.current_streaming_text += token
            # Update HTML content with markdown
            html = markdown2.markdown(self.current_streaming_text, extras=['tables', 'strike'])
            self.current_streaming_display.setHtml(html)
            self.current_streaming_display.markdown_text = self.current_streaming_text
            self.current_streaming_display._update_size()
            
        # Smoothly scroll as content grows
        self.chat_area.scroll_to_bottom()

    @Slot(str)
    def set_text(self, text):
        """Set initial response text with enhanced handling"""
        if not text.strip():
            return

        # If we were streaming, save full response to history then return
        if self.current_streaming_display:
            self.chat_history = [
                {"role": "user", "content": f"{self.option}: {self.selected_text}"},
                {"role": "assistant", "content": text}
            ]
            self.current_streaming_display = None
            self.current_streaming_text = ""
            return
                
        # Always ensure chat history is initialized properly
        self.chat_history = [
            {"role": "user", "content": f"{self.option}: {self.selected_text}"},
            {"role": "assistant", "content": text}  # Add initial response immediately
        ]
        
        self.stop_thinking_animation()
        text_display = self.chat_area.add_message(text)
        
        # Update zoom state
        if hasattr(self.app.config, 'response_window_zoom'):
            text_display.zoom_factor = self.app.config['response_window_zoom']
            text_display._apply_zoom()
        
        QtCore.QTimer.singleShot(100, self._adjust_window_height)
        
    @Slot(str)
    def handle_followup_response(self, response_text):
        """Handle the follow-up response from the AI with improved layout handling"""
        self._streaming_active = False # Immediately stop accepting tokens
        self._ignore_tokens = True
        
        streaming_display = self.current_streaming_display
        was_streaming = streaming_display is not None
        
        self.current_streaming_display = None
        self.current_streaming_text = ""

        if response_text:
            self.loading_label.setVisible(False)

            # Update streaming bubble with the complete final text
            if was_streaming and streaming_display:
                html = markdown2.markdown(response_text, extras=['tables', 'strike'])
                streaming_display.setHtml(html)
                streaming_display.markdown_text = response_text
                streaming_display._update_size()

            last_msg = self.chat_history[-1] if self.chat_history else None
            if last_msg and last_msg["role"] == "user":
                if not was_streaming:
                    self.chat_area.add_message(response_text)
                self.chat_history.append({
                    "role": "assistant",
                    "content": response_text
                })

        self.stop_thinking_animation()
        self.input_field.setEnabled(True)
        
        # Update window height
        QtCore.QTimer.singleShot(100, self._adjust_window_height)
        
    def send_message(self):
        """Send a new message/question"""
        message = self.input_field.toPlainText().strip()
        attachments = self.attachment_bar.get_attachments()
        if not message and not attachments:
            return

        self.input_field.setEnabled(False)
        self.input_field.clear()
        self.attachment_bar.clear()
        self._ignore_tokens = False
        self._streaming_active = True # Allow tokens

        # Build display text cho user bubble
        if attachments:
            names = ", ".join(a.label for a in attachments)
            display_text = f"[{names}]\n{message}" if message else f"[{names}]"
        else:
            display_text = message

        text_display = self.chat_area.add_message(display_text, is_user=True, attachments=attachments)
        if hasattr(self, 'current_text_display'):
            text_display.zoom_factor = self.current_text_display.zoom_factor
            text_display._apply_zoom()

        self.chat_history.append({"role": "user", "content": message or "(see attachments)"})
        self.start_thinking_animation()
        self.app.process_followup_question(self, message, attachments=attachments)
        
    def copy_as_markdown(self):
        """Copy conversation as Markdown"""
        markdown = ""
        for msg in self.chat_history:
            if msg["role"] == "user":
                markdown += f"**User**: {msg['content']}\n\n"
            else:
                markdown += f"**Assistant**: {msg['content']}\n\n"
                
        QtWidgets.QApplication.clipboard().setText(markdown)
        
    def closeEvent(self, event):
        """Handle window close event"""
        # Save zoom factor to main config
        if hasattr(self, 'current_text_display'):
            self.app.config['response_window_zoom'] = self.current_text_display.zoom_factor
            self.app.save_config(self.app.config)

        self.chat_history = []
        
        if hasattr(self.app, 'current_response_window'):
            delattr(self.app, 'current_response_window')
        

        super().closeEvent(event)
