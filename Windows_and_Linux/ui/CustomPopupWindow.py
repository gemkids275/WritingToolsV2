import logging
import os
from functools import partial

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ui.AttachmentBar import AttachmentBar, attachment_from_file, attachment_from_qimage
from ui.UIUtils import UIUtils, colorMode, ThemeBackground
from ui.BaseTextEditor import BaseAITextEdit
from update_checker import UPDATE_DOWNLOAD_URL

_ = lambda x: x  # Will be overridden by WritingToolApp


class PopupTextEdit(BaseAITextEdit):
    """Auto-resize text input cho custom instructions, hỗ trợ paste ảnh và drop file."""
    def __init__(self, attachment_bar: 'AttachmentBar', parent=None):
        super().__init__(attachment_bar, parent)
        self.setFixedHeight(72)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def keyPressEvent(self, event):
        # Trigger submit on Enter (unless Shift/Alt is held)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)):
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class ButtonEditDialog(QDialog):
    """
    Dialog for editing or creating a button's properties
    (name/title, system instruction, open_in_window, etc.).
    """
    def __init__(self, parent=None, button_data=None, title="Edit Button"):
        super().__init__(parent)
        self.button_data = button_data if button_data else {
            "prefix": "Make this change to the following text:\n\n",
            "instruction": "",
            "icon": "icons/magnifying-glass",
            "open_in_window": False
        }
        self.setWindowTitle(title)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Name
        name_label = QLabel("Button Name:")
        name_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode == 'dark' else 'white'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
            }}
        """)
        if "name" in self.button_data:
            self.name_input.setText(self.button_data["name"])
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        
        # Instruction (changed to a multiline QPlainTextEdit)
        instruction_label = QLabel("What should your AI do with your selected text? (System Instruction)")
        instruction_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        self.instruction_input = QPlainTextEdit()
        self.instruction_input.setStyleSheet(f"""
            QPlainTextEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode == 'dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode == 'dark' else 'white'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
            }}
        """)
        self.instruction_input.setPlainText(self.button_data.get("instruction", ""))
        self.instruction_input.setMinimumHeight(100)
        self.instruction_input.setPlaceholderText("""Examples:
    - Fix / improve / explain this code.
    - Make it funny.
    - Add emojis!
    - Roast this!
    - Translate to English.
    - Make the text title case.
    - If it's all caps, make it all small, and vice-versa.
    - Write a reply to this.
    - Analyse potential biases in this news article.""")
        layout.addWidget(instruction_label)
        layout.addWidget(self.instruction_input)
        
        # open_in_window
        display_label = QLabel("How should your AI response be shown?")
        display_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold;")
        layout.addWidget(display_label)
        
        radio_layout = QHBoxLayout()
        self.replace_radio = QRadioButton("Replace the selected text")
        self.window_radio = QRadioButton("In a pop-up window (with follow-up support)")
        for r in (self.replace_radio, self.window_radio):
            r.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'};")
        
        self.replace_radio.setChecked(not self.button_data.get("open_in_window", False))
        self.window_radio.setChecked(self.button_data.get("open_in_window", False))
        
        radio_layout.addWidget(self.replace_radio)
        radio_layout.addWidget(self.window_radio)
        layout.addLayout(radio_layout)
        
        # OK & Cancel
        btn_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        for btn in (ok_button, cancel_button):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#444' if colorMode == 'dark' else '#f0f0f0'};
                    color: {'#fff' if colorMode == 'dark' else '#000'};
                    border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                    border-radius: 5px;
                    padding: 8px;
                    min-width: 100px;
                }}
                QPushButton:hover {{
                    background-color: {'#555' if colorMode == 'dark' else '#e0e0e0'};
                }}
            """)
        btn_layout.addWidget(ok_button)
        btn_layout.addWidget(cancel_button)
        layout.addLayout(btn_layout)
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {'#222' if colorMode == 'dark' else '#f5f5f5'};
                border-radius: 10px;
            }}
        """)

    def get_button_data(self):
        return {
            "name": self.name_input.text(),
            "prefix": "Make this change to the following text:\n\n",
            # Retrieve multiline text
            "instruction": self.instruction_input.toPlainText(),
            "icon": "icons/custom",
            "open_in_window": self.window_radio.isChecked()
        }

class DraggableButton(QtWidgets.QPushButton):
    def __init__(self, parent_popup, key, text):
        super().__init__(text, parent_popup)
        self.popup = parent_popup
        self.key = key
        self.drag_start_position = None
        self.setAcceptDrops(True)
        self.icon_container = None

        # Enable mouse tracking and hover events, and styled background
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        # Use a dynamic property "hover" (default False)
        self.setProperty("hover", False)

        # Set fixed size (adjust as needed)
        self.setFixedSize(120, 40)

        # Define base style using the dynamic property instead of the :hover pseudo-class
        self.base_style = f"""
            QPushButton {{
                background-color: {"#444" if colorMode=="dark" else "white"};
                border: 1px solid {"#666" if colorMode=="dark" else "#ccc"};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                text-align: left;
                color: {"#fff" if colorMode=="dark" else "#000"};
            }}
            QPushButton[hover="true"] {{
                background-color: {"#555" if colorMode=="dark" else "#f0f0f0"};
            }}
        """
        self.setStyleSheet(self.base_style)
        logging.debug("DraggableButton initialized")

    def enterEvent(self, event):
        # Only update the hover property if NOT in edit mode.
        if not self.popup.edit_mode:
            self.setProperty("hover", True)
            self.style().unpolish(self)
            self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.popup.edit_mode:
            self.setProperty("hover", False)
            self.style().unpolish(self)
            self.style().polish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.popup.edit_mode:
                self.drag_start_position = event.pos()
                event.accept()
                return
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.LeftButton) or not self.drag_start_position:
            return

        distance = (event.pos() - self.drag_start_position).manhattanLength()
        if distance < QtWidgets.QApplication.startDragDistance():
            return

        if self.popup.edit_mode:
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            idx = self.popup.button_widgets.index(self)
            mime_data.setData("application/x-button-index", str(idx).encode())
            drag.setMimeData(mime_data)

            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            self.drag_start_position = None
            drop_action = drag.exec_(QtCore.Qt.MoveAction)
            logging.debug(f"Drag completed with action: {drop_action}")

    def dragEnterEvent(self, event):
        if self.popup.edit_mode and event.mimeData().hasFormat("application/x-button-index"):
            event.acceptProposedAction()
            self.setStyleSheet(self.base_style + """
                QPushButton {
                    border: 2px dashed #666;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.base_style)
        event.accept()

    def dropEvent(self, event):
        if not self.popup.edit_mode or not event.mimeData().hasFormat("application/x-button-index"):
            event.ignore()
            return

        source_idx = int(event.mimeData().data("application/x-button-index").data().decode())
        target_idx = self.popup.button_widgets.index(self)

        if source_idx != target_idx:
            bw = self.popup.button_widgets
            bw[source_idx], bw[target_idx] = bw[target_idx], bw[source_idx]
            self.popup.rebuild_grid_layout()
            self.popup.update_json_from_grid()

        self.setStyleSheet(self.base_style)
        event.setDropAction(QtCore.Qt.MoveAction)
        event.acceptProposedAction()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.icon_container:
            self.icon_container.setGeometry(0, 0, self.width(), self.height())

class CustomPopupWindow(QtWidgets.QWidget):
    def __init__(self, app, selected_text):
        super().__init__()
        self.app = app
        self.selected_text = selected_text
        self.edit_mode = False
        self.has_text = bool(selected_text.strip())
        
        self.drag_label = None
        self.edit_button = None
        self.reset_button = None
        self.close_button = None
        self.custom_input = None
        self.input_area = None
        
        self.button_widgets = []
        self._drag_pos = None
        self._suppress_deactivate = False

        logging.debug('Initializing CustomPopupWindow')
        self.init_ui()

    def init_ui(self):
        logging.debug('Setting up CustomPopupWindow UI')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("AI Shortcuts")
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        self.background = ThemeBackground(
            self, 
            self.app.config.get('theme','gradient'),
            is_popup=True,
            border_radius=10
        )
        main_layout.addWidget(self.background)
        
        content_layout = QtWidgets.QVBoxLayout(self.background)
        # Margin Control
        content_layout.setContentsMargins(10, 4, 10, 10)
        content_layout.setSpacing(10)
        
        # TOP BAR LAYOUT & STYLE
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        # The "Edit"/"Done" button (left), same exact size as close button
        self.edit_button = QPushButton()
        pencil_icon = UIUtils.get_resource_path(os.path.join('icons', 'pencil' + ('_dark' if colorMode == 'dark' else '_light') + '.png'))
        if os.path.exists(pencil_icon):
            self.edit_button.setIcon(QtGui.QIcon(pencil_icon))
        # Reduced size to 24x24 to shrink top bar
        self.edit_button.setFixedSize(24, 24)
        self.edit_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 0px;
                margin-top: 3px;
            }}
            QPushButton:hover {{
                background-color: {'#333' if colorMode=='dark' else '#ebebeb'};
            }}
        """)
        self.edit_button.clicked.connect(self._open_commands_manager)
        top_bar.addWidget(self.edit_button, 0, Qt.AlignLeft)

        # The label "Drag to rearrange" (BOLD as requested)
        self.drag_label = QLabel(_("Drag to rearrange"))
        self.drag_label.setStyleSheet(f"""
            color: {'#fff' if colorMode=='dark' else '#333'};
            font-size: 14px;
            font-weight: bold; /* <--- BOLD TEXT */
        """)
        self.drag_label.setAlignment(Qt.AlignCenter)
        self.drag_label.hide()
        top_bar.addWidget(self.drag_label, 1, Qt.AlignVCenter | Qt.AlignHCenter)

        # The "Reset" button (edit-mode only) - also 24x24
        self.reset_button = QPushButton()
        reset_icon_path = UIUtils.get_resource_path(os.path.join('icons', 'restore' + ('_dark' if colorMode == 'dark' else '_light') + '.png'))
        if os.path.exists(reset_icon_path):
            self.reset_button.setIcon(QtGui.QIcon(reset_icon_path))
        self.reset_button.setText("")
        self.reset_button.setFixedSize(24, 24)
        self.reset_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#333' if colorMode=='dark' else '#ebebeb'};
            }}
        """)
        self.reset_button.clicked.connect(self.on_reset_clicked)
        self.reset_button.hide()
        top_bar.addWidget(self.reset_button, 0, Qt.AlignRight)

        # Close button block:
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {'#fff' if colorMode=='dark' else '#333'};
                font-size: 20px;   /* bigger text */
                font-weight: bold; /* bold text */
                border: none;
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#333' if colorMode=='dark' else '#ebebeb'};
            }}
        """)
        self.close_button.clicked.connect(self.close)
        top_bar.addWidget(self.close_button, 0, Qt.AlignRight)
        content_layout.addLayout(top_bar)

        
        # Input area (hidden in edit mode)
        self.input_area = QWidget()
        input_area_layout = QVBoxLayout(self.input_area)
        input_area_layout.setContentsMargins(0, 0, 0, 0)
        input_area_layout.setSpacing(4)

        # Attachment bar (ẩn khi trống)
        self.attachment_bar = AttachmentBar()
        input_area_layout.addWidget(self.attachment_bar)

        # Textarea full-width
        self.custom_input = PopupTextEdit(self.attachment_bar)
        self.custom_input.setPlaceholderText(_("Describe your change...") if self.has_text else _("Ask your AI..."))
        self.custom_input.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px;
                border: 1px solid {'#777' if colorMode=='dark' else '#ccc'};
                border-radius: 8px;
                background-color: {'#333' if colorMode=='dark' else 'white'};
                color: {'#fff' if colorMode=='dark' else '#000'};
            }}
        """)
        self.custom_input.submit_requested.connect(self.on_custom_change)
        input_area_layout.addWidget(self.custom_input)

        # Buttons căn phải phía dưới textarea
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        btn_row.addStretch()

        btn_size = 28
        attach_btn = QPushButton("📎")
        attach_btn.setFixedSize(btn_size, btn_size)
        attach_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                font-size: 16px;
                padding: 0px;
                color: {'#aaa' if colorMode=='dark' else '#666'};
            }}
            QPushButton:hover {{
                color: {'#fff' if colorMode=='dark' else '#000'};
            }}
        """)
        attach_btn.setToolTip(_("Attach file"))
        attach_btn.clicked.connect(self._open_file_dialog)
        btn_row.addWidget(attach_btn)

        send_btn = QPushButton()
        send_icon = UIUtils.get_resource_path(os.path.join('icons', 'send' + ('_dark' if colorMode == 'dark' else '_light') + '.png'))
        if os.path.exists(send_icon):
            send_btn.setIcon(QtGui.QIcon(send_icon))
        send_btn.setFixedSize(btn_size, btn_size)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#2e7d32' if colorMode=='dark' else '#4CAF50'};
                border: none;
                border-radius: 6px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background-color: {'#1b5e20' if colorMode=='dark' else '#45a049'};
            }}
        """)
        send_btn.clicked.connect(self.on_custom_change)
        btn_row.addWidget(send_btn)

        input_area_layout.addLayout(btn_row)
        content_layout.addWidget(self.input_area)
        
        if self.has_text:
            self.build_buttons_list()
            self.rebuild_grid_layout(content_layout)
        else:
            # If no text, hide the edit button; user can only do custom instructions
            self.edit_button.hide()
            self.custom_input.setMinimumWidth(260)

        # show update notice if applicable
        if self.app.config.get("update_available", False):
            update_label = QLabel()
            update_label.setOpenExternalLinks(True)
            # Modern update notification banner
            update_text = f'<a href="{UPDATE_DOWNLOAD_URL}" style="color: white; text-decoration: none; font-weight: bold;">✨ {_("There\'s an update! :D Download now.")}</a>'
            update_label.setText(update_text)
            update_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {'#1d4ed8' if colorMode == 'dark' else '#2563eb'};
                    color: white;
                    padding: 8px 20px;
                    border-radius: 20px;
                    margin-top: 12px;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }}
            """)
            content_layout.addWidget(update_label, alignment=QtCore.Qt.AlignCenter)
        
        logging.debug('CustomPopupWindow UI setup complete')
        self.installEventFilter(self)
        QtCore.QTimer.singleShot(250, lambda: self.custom_input.setFocus())

    def build_buttons_list(self):
        """
        Creates DraggableButton for each command from CommandManager (except "Custom"),
        storing them in self.button_widgets in the same order as in CommandManager.
        """
        self.button_widgets.clear()
        commands = self.app.command_manager.commands

        has_text = bool(self.selected_text and self.selected_text.strip())
        for cmd in commands:
            if cmd.name == "Custom":
                continue
            if cmd.id == "ChatNoSelection" and has_text:
                continue
            
            # Sử dụng cmd.id làm key thay vì cmd.name, và dịch tên hiển thị
            b = DraggableButton(self, cmd.id, _(cmd.name))
            icon_path = UIUtils.get_resource_path(cmd.icon + ('_dark' if colorMode == 'dark' else '_light') + '.png')
            if os.path.exists(icon_path):
                b.setIcon(QtGui.QIcon(icon_path))
                
            if not self.edit_mode:
                b.clicked.connect(partial(self.on_generic_instruction, cmd.id))
            self.button_widgets.append(b)

    def rebuild_grid_layout(self, parent_layout=None):
        """Rebuild grid layout with consistent sizing and proper Add New button placement."""
        if not parent_layout:
            parent_layout = self.background.layout()

        # Remove existing grid and Add New button
        for i in reversed(range(parent_layout.count())):
            item = parent_layout.itemAt(i)
            if isinstance(item, QtWidgets.QGridLayout):
                grid = item
                for j in reversed(range(grid.count())):
                    w = grid.itemAt(j).widget()
                    if w:
                        grid.removeWidget(w)
                parent_layout.removeItem(grid)
            elif (item.widget() and isinstance(item.widget(), QPushButton) 
                and item.widget().text() == "+ Add New"):
                item.widget().deleteLater()

        # Create new grid with fixed column width
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)  
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 120)
        
        # Add buttons to grid
        row = 0
        col = 0
        for b in self.button_widgets:
            grid.addWidget(b, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
        
        parent_layout.addLayout(grid)
        
        # Add New button (only in edit mode & only if we have text)
        if self.edit_mode and self.has_text:
            add_btn = QPushButton(_("+ Add New"))
            add_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#333' if colorMode=='dark' else '#e0e0e0'};
                    border: 1px solid {'#666' if colorMode=='dark' else '#ccc'};
                    border-radius: 8px;
                    padding: 10px;
                    font-size: 14px;
                    text-align: center;
                    color: {'#fff' if colorMode=='dark' else '#000'};
                    margin-top: 10px;
                }}
                QPushButton:hover {{
                    background-color: {'#444' if colorMode=='dark' else '#d0d0d0'};
                }}
            """)
            add_btn.clicked.connect(self.add_new_button_clicked)
            parent_layout.addWidget(add_btn)

    def add_edit_delete_icons(self, btn):
        """Add edit/delete icons as overlays with proper spacing."""
        if hasattr(btn, 'icon_container') and btn.icon_container:
            btn.icon_container.deleteLater()
        
        btn.icon_container = QtWidgets.QWidget(btn)
        btn.icon_container.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        
        btn.icon_container.setGeometry(0, 0, btn.width(), btn.height())
        
        circle_style = f"""
            QPushButton {{
                background-color: {'#666' if colorMode=='dark' else '#999'};
                border-radius: 10px;
                min-width: 16px;
                min-height: 16px;
                max-width: 16px;
                max-height: 16px;
                padding: 1px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {'#888' if colorMode=='dark' else '#bbb'};
            }}
        """
        
        # Create edit icon (top-left)
        edit_btn = QPushButton(btn.icon_container)
        edit_btn.setGeometry(3, 3, 16, 16)
        pencil_icon = UIUtils.get_resource_path(os.path.join('icons', 'pencil' + ('_dark' if colorMode == 'dark' else '_light') + '.png'))
        if os.path.exists(pencil_icon):
            edit_btn.setIcon(QtGui.QIcon(pencil_icon))
        edit_btn.setStyleSheet(circle_style)
        edit_btn.clicked.connect(partial(self.edit_button_clicked, btn))
        edit_btn.show()
        
        # Create delete icon (top-right)
        delete_btn = QPushButton(btn.icon_container)
        delete_btn.setGeometry(btn.width() - 23, 3, 16, 16)
        del_icon = UIUtils.get_resource_path(os.path.join('icons', 'cross' + ('_dark' if colorMode == 'dark' else '_light') + '.png'))
        if os.path.exists(del_icon):
            delete_btn.setIcon(QtGui.QIcon(del_icon))
        delete_btn.setStyleSheet(circle_style)
        delete_btn.clicked.connect(partial(self.delete_button_clicked, btn))
        delete_btn.show()
        
        btn.icon_container.raise_()
        btn.icon_container.show()

    def _open_commands_manager(self):
        """Mở Settings → Commands tab; refresh button list khi cửa sổ đóng."""
        self.app.show_settings(initial_tab="commands")
        settings_win = self.app.settings_window
        if settings_win:
            settings_win.destroyed.connect(self._on_settings_closed)

    def _on_settings_closed(self):
        self.build_buttons_list()
        self.rebuild_grid_layout()

    def toggle_edit_mode(self):
        """Toggle edit mode with improved button labels and state handling."""
        self.edit_mode = not self.edit_mode
        logging.debug(f'Edit mode toggled: {self.edit_mode}')

        if self.edit_mode:
            # Switch to edit mode:
            icon_name = "check"
            # No text, just the check icon, a bit bigger:
            self.edit_button.setText("")
            self.edit_button.setFixedSize(36, 36)
            self.edit_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    background-color: {'#333' if colorMode=='dark' else '#ebebeb'};
                }}
            """)
            # Hide close, show reset button & drag label
            self.close_button.hide()
            self.reset_button.show()
            self.drag_label.show()

        else:
            # Switch back to normal (non-edit) mode:
            icon_name = "pencil"
            self.edit_button.setText("")
            self.edit_button.setFixedSize(24, 24)  # Return to normal size
            # Show close, hide reset & drag label
            self.close_button.show()
            self.reset_button.hide()
            self.drag_label.hide()

            self.build_buttons_list()
            self.rebuild_grid_layout()


        # Update the edit button icon now that icon_name is defined
        icon_file = f"{icon_name}_{'dark' if colorMode=='dark' else 'light'}.png"
        icon_path = UIUtils.get_resource_path(os.path.join('icons', icon_file))
        if os.path.exists(icon_path):
            self.edit_button.setIcon(QtGui.QIcon(icon_path))

        # Toggle the main input area
        self.input_area.setVisible(not self.edit_mode)

        # Update button overlays
        for btn in self.button_widgets:
            try:
                btn.clicked.disconnect()
            except:
                pass

            if not self.edit_mode:
                btn.clicked.connect(partial(self.on_generic_instruction, btn.key))
                if hasattr(btn, 'icon_container') and btn.icon_container:
                    btn.icon_container.deleteLater()
                    btn.icon_container = None
            else:
                self.add_edit_delete_icons(btn)

            btn.setStyleSheet(btn.base_style)

        # Rebuild grid layout
        self.rebuild_grid_layout()


    def on_reset_clicked(self):
        """Restore all built-in commands."""
        reply = QtWidgets.QMessageBox.question(
            self, 
            "Reset Commands", 
            "Are you sure you want to restore all built-in commands? This will bring back any deleted system commands.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.app.command_manager.restore_built_ins()
            self.build_buttons_list()
            self.rebuild_grid_layout()
            logging.info("Built-in commands restored")

    def add_new_button_clicked(self):
        dialog = ButtonEditDialog(self, title="Add New Button")
        if dialog.exec_():
            bd = dialog.get_button_data()
            self.app.command_manager.add_command(bd)
            self.build_buttons_list()
            self.rebuild_grid_layout()

    def edit_button_clicked(self, btn):
        """User clicked the small pencil icon over a button."""
        key = btn.key
        bd = self.app.command_manager.get_command(key)
        bd["name"] = key
        
        dialog = ButtonEditDialog(self, bd)
        if dialog.exec_():
            new_data = dialog.get_button_data()
            self.app.command_manager.update_command(key, new_data)
            self.build_buttons_list()
            self.rebuild_grid_layout()

    def delete_button_clicked(self, btn):
        """Handle deletion of a button."""
        key = btn.key
        confirm = QtWidgets.QMessageBox()
        confirm.setWindowTitle(_("Confirm Delete?"))
        confirm.setText(_("Are you sure you want to delete the '{0}' button?").format(key))
        confirm.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        
        if confirm.exec_() == QtWidgets.QMessageBox.Yes:
            self.app.command_manager.delete_command(key)
            self.build_buttons_list()
            self.rebuild_grid_layout()

    def update_json_from_grid(self):
        """
        Ghi chú: Trong hệ thống mới, thứ tự các lệnh được quản lý bởi danh sách 
        trong CommandManager. Ở giai đoạn này, chúng ta sẽ tạm thời bỏ qua 
        việc lưu lại thứ tự kéo thả cho đến khi CommandsManagerDialog được hoàn thiện.
        """
        pass

    def _open_file_dialog(self):
        self._suppress_deactivate = True
        files, unused_filter = QFileDialog.getOpenFileNames(
            self,
            _("Attach File"),
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff);;"
            "Text Files (*.txt *.md *.csv *.json *.xml *.py *.js *.ts *.html *.css *.yaml *.yml *.toml *.ini *.log);;"
            "All Files (*)"
        )
        self._suppress_deactivate = False
        for path in files:
            att = attachment_from_file(path)
            if att:
                self.attachment_bar.add_attachment(att)

    def on_custom_change(self):
        txt = self.custom_input.toPlainText().strip()
        attachments = self.attachment_bar.get_attachments()
        if txt or attachments:
            self.app.process_option('Custom', self.selected_text, txt, attachments=attachments)
            self.close()

    def on_generic_instruction(self, command_id):
        if not self.edit_mode:
            self.app.process_option(command_id, self.selected_text)
            self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key()==QtCore.Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
