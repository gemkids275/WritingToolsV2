import os
import sys
from PySide6 import QtCore, QtGui, QtWidgets
from ui.UIUtils import colorMode
from ui.ShortcutEditWidget import ShortcutEditWidget
from models.command import Command
from models.shortcut_conflict import check_conflict


def _icon_path(base: str) -> str:
    suffix = '_dark' if colorMode == 'dark' else '_light'
    return os.path.join(os.path.dirname(sys.argv[0]), f"{base}{suffix}.png")


def _available_icons() -> list[str]:
    """Trả về danh sách base path (VD: 'icons/pencil') có đủ cả _dark và _light."""
    icons_dir = os.path.join(os.path.dirname(sys.argv[0]), 'icons')
    if not os.path.isdir(icons_dir):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for fname in sorted(os.listdir(icons_dir)):
        if not fname.endswith('_dark.png'):
            continue
        base_name = fname[:-len('_dark.png')]
        light_path = os.path.join(icons_dir, f"{base_name}_light.png")
        if not os.path.exists(light_path):
            continue
        # Bỏ qua icon UI nội bộ (check, copy, cross, minus, plus, send, reset, restore, regenerate, rotate-left)
        skip = {'check', 'copy', 'cross', 'minus', 'plus', 'send', 'reset',
                'restore', 'regenerate', 'rotate-left'}
        if base_name in skip:
            continue
        base_path = f"icons/{base_name}"
        if base_path not in seen:
            seen.add(base_path)
            result.append(base_path)
    return result


class IconPickerDialog(QtWidgets.QDialog):
    def __init__(self, current_icon: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Icon")
        self.setMinimumWidth(380)
        self.selected_icon = current_icon
        self._all_icons = _available_icons()
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.setStyleSheet(f"background-color: {'#2a2a2a' if colorMode == 'dark' else '#f5f5f5'};")

        # Search bar
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search icons...")
        self.search.setStyleSheet(f"""
            QLineEdit {{
                background: {'#333' if colorMode == 'dark' else '#fff'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
                border-radius: 6px; padding: 6px 10px; font-size: 13px;
            }}
        """)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        # Scroll area with icon grid
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self._grid_widget = QtWidgets.QWidget()
        self._grid_widget.setStyleSheet("background: transparent;")
        self._grid = QtWidgets.QGridLayout(self._grid_widget)
        self._grid.setSpacing(6)
        scroll.setWidget(self._grid_widget)
        layout.addWidget(scroll)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setStyleSheet(self._btn_style())
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

        self._render_icons(self._all_icons)

    def _render_icons(self, icons: list[str]):
        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 5
        for idx, base in enumerate(icons):
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(56, 56)
            btn.setToolTip(base.split('/')[-1])
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

            icon_file = _icon_path(base)
            if os.path.exists(icon_file):
                btn.setIcon(QtGui.QIcon(icon_file))
                btn.setIconSize(QtCore.QSize(28, 28))

            is_selected = (base == self.selected_icon)
            btn.setStyleSheet(self._icon_btn_style(selected=is_selected))
            btn.clicked.connect(lambda checked=False, b=base: self._select(b))
            self._grid.addWidget(btn, idx // cols, idx % cols)

    def _select(self, base: str):
        self.selected_icon = base
        self.accept()

    def _filter(self, text: str):
        filtered = [b for b in self._all_icons if text.lower() in b.split('/')[-1].lower()]
        self._render_icons(filtered)

    def _icon_btn_style(self, selected=False):
        if selected:
            return """QPushButton {
                background: #4CAF50; border: 2px solid #2e7d32; border-radius: 8px;
            }"""
        return f"""QPushButton {{
            background: {'#3a3a3a' if colorMode == 'dark' else '#fff'};
            border: 1px solid {'#555' if colorMode == 'dark' else '#ddd'};
            border-radius: 8px;
        }}
        QPushButton:hover {{
            background: {'#4a4a4a' if colorMode == 'dark' else '#e8f5e9'};
            border: 1px solid #4CAF50;
        }}"""

    def _btn_style(self):
        return f"""QPushButton {{
            background: {'#444' if colorMode == 'dark' else '#eee'};
            color: {'#fff' if colorMode == 'dark' else '#000'};
            border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
            border-radius: 5px; padding: 7px 16px;
        }}
        QPushButton:hover {{ background: {'#555' if colorMode == 'dark' else '#ddd'}; }}"""


class CommandEditorDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, command=None):
        super().__init__(parent)
        self.command = command
        self._selected_icon = command.icon if command else ""
        # Traverse parent chain để lấy app reference cho conflict check
        p = parent
        while p and not hasattr(p, 'app'):
            p = p.parent() if hasattr(p, 'parent') else None
        self._app = getattr(p, 'app', None)
        self.setWindowTitle("Edit Command" if command else "Add New Command")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        label_style = f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: bold; font-size: 13px;"

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(QtCore.Qt.AlignLeft)

        # Name
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("e.g., Proofread")
        if self.command:
            self.name_input.setText(self.command.name)
        name_label = QtWidgets.QLabel()
        name_label.setText('Command Name <span style="color:red;">*</span>:')
        form.addRow(name_label, self.name_input)

        # Icon picker button
        self.icon_btn = QtWidgets.QPushButton("Change Icon")
        self.icon_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.icon_btn.setIconSize(QtCore.QSize(20, 20))
        self.icon_btn.clicked.connect(self._open_icon_picker)
        self._refresh_icon_preview()
        form.addRow(QtWidgets.QLabel("Icon:"), self.icon_btn)

        # Prefix
        self.prefix_input = QtWidgets.QLineEdit()
        self.prefix_input.setPlaceholderText("e.g., Proofread this:\\n\\n")
        if self.command:
            self.prefix_input.setText(self.command.prefix)
        form.addRow(QtWidgets.QLabel("Prefix Text:"), self.prefix_input)

        input_style = f"""
            QLineEdit, QPlainTextEdit {{
                background-color: {'#333' if colorMode == 'dark' else '#fff'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
                border-radius: 4px; padding: 5px;
            }}
        """
        icon_btn_style = f"""
            QPushButton {{
                background-color: {'#444' if colorMode == 'dark' else '#eee'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                border-radius: 5px; padding: 6px 12px; font-size: 13px;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: {'#555' if colorMode == 'dark' else '#ddd'}; }}
        """
        self.icon_btn.setStyleSheet(icon_btn_style)

        for i in range(form.rowCount()):
            label_item = form.itemAt(i, QtWidgets.QFormLayout.LabelRole)
            field_item = form.itemAt(i, QtWidgets.QFormLayout.FieldRole)
            if label_item and label_item.widget():
                label_item.widget().setStyleSheet(label_style)
            if field_item and field_item.widget() and isinstance(field_item.widget(), QtWidgets.QLineEdit):
                field_item.widget().setStyleSheet(input_style)

        layout.addLayout(form)

        # Prompt
        prompt_label = QtWidgets.QLabel()
        prompt_label.setText('System Prompt / Instruction <span style="color:red;">*</span>:')
        prompt_label.setStyleSheet(label_style)
        layout.addWidget(prompt_label)
        self.prompt_input = QtWidgets.QPlainTextEdit()
        self.prompt_input.setPlaceholderText("Describe how the AI should behave...")
        if self.command:
            self.prompt_input.setPlainText(self.command.prompt)
        self.prompt_input.setStyleSheet(input_style)
        layout.addWidget(self.prompt_input)

        # Options
        self.window_checkbox = QtWidgets.QCheckBox("Open in a separate pop-up window")
        self.window_checkbox.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'};")
        if self.command:
            self.window_checkbox.setChecked(self.command.use_response_window)
        layout.addWidget(self.window_checkbox)

        # Keyboard Shortcut
        shortcut_label = QtWidgets.QLabel("Keyboard Shortcut:")
        shortcut_label.setStyleSheet(label_style)
        layout.addWidget(shortcut_label)

        self.shortcut_widget = ShortcutEditWidget()
        if self.command and self.command.keyboard_shortcut:
            self.shortcut_widget.set_shortcut(self.command.keyboard_shortcut)
        self.shortcut_widget.shortcut_changed.connect(self._on_shortcut_changed)
        layout.addWidget(self.shortcut_widget)

        self.conflict_label = QtWidgets.QLabel()
        self.conflict_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self.conflict_label.hide()
        layout.addWidget(self.conflict_label)

        # AI Override Section (Phase 6)
        layout.addSpacing(10)
        self.override_group = QtWidgets.QGroupBox("AI Override (Optional)")
        self.override_group.setStyleSheet(f"""
            QGroupBox {{
                color: {'#fff' if colorMode == 'dark' else '#333'};
                font-weight: bold;
                border: 1px solid {'#444' if colorMode == 'dark' else '#ddd'};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """)
        over_layout = QtWidgets.QVBoxLayout(self.override_group)
        over_layout.setSpacing(10)

        self.override_checkbox = QtWidgets.QCheckBox("Use custom AI provider for this command")
        self.override_checkbox.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#333'}; font-weight: normal;")
        self.override_checkbox.toggled.connect(self._on_override_toggled)
        over_layout.addWidget(self.override_checkbox)

        over_form = QtWidgets.QFormLayout()
        over_form.setSpacing(8)
        
        # Provider combo
        self.provider_combo = QtWidgets.QComboBox()
        if self._app:
            providers = [p.provider_name for p in self._app.providers]
            self.provider_combo.addItems(providers)
        self.provider_combo.addItem("Custom OpenAI-compatible")
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        over_form.addRow(QtWidgets.QLabel("Provider:"), self.provider_combo)

        # Model input
        self.model_input = QtWidgets.QLineEdit()
        self.model_input.setPlaceholderText("Leave blank for default")
        over_form.addRow(QtWidgets.QLabel("Model:"), self.model_input)

        # API Key input
        key_layout = QtWidgets.QHBoxLayout()
        self.api_key_input = QtWidgets.QLineEdit()
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Leave blank to use global key")
        self.show_key_btn = QtWidgets.QPushButton("Show")
        self.show_key_btn.setFixedWidth(50)
        self.show_key_btn.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.api_key_input)
        key_layout.addWidget(self.show_key_btn)
        over_form.addRow(QtWidgets.QLabel("API Key:"), key_layout)

        # Base URL (for custom)
        self.base_url_label = QtWidgets.QLabel("Base URL:")
        self.base_url_input = QtWidgets.QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.example.com/v1")
        over_form.addRow(self.base_url_label, self.base_url_input)

        # Apply styles to override form
        for i in range(over_form.rowCount()):
            label_item = over_form.itemAt(i, QtWidgets.QFormLayout.LabelRole)
            field_item = over_form.itemAt(i, QtWidgets.QFormLayout.FieldRole)
            if label_item and label_item.widget():
                label_item.widget().setStyleSheet(label_style + "font-weight: normal;")
            if field_item and field_item.widget() and isinstance(field_item.widget(), (QtWidgets.QLineEdit, QtWidgets.QComboBox)):
                field_item.widget().setStyleSheet(input_style if isinstance(field_item.widget(), QtWidgets.QLineEdit) else f"""
                    QComboBox {{
                        background-color: {'#333' if colorMode == 'dark' else '#fff'};
                        color: {'#fff' if colorMode == 'dark' else '#000'};
                        border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
                        border-radius: 4px; padding: 4px;
                    }}
                """)

        over_layout.addLayout(over_form)
        layout.addWidget(self.override_group)

        # Trạng thái ban đầu của override UI
        self._init_override_data()
        self._on_override_toggled(self.override_checkbox.isChecked())

        # Save / Cancel
        button_box = QtWidgets.QHBoxLayout()
        button_box.addStretch()

        btn_style = f"""
            QPushButton {{
                background-color: {'#444' if colorMode == 'dark' else '#eee'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                border-radius: 5px; padding: 8px 15px; min-width: 80px;
            }}
            QPushButton:hover {{ background-color: {'#555' if colorMode == 'dark' else '#ddd'}; }}
        """
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setStyleSheet(btn_style)
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setStyleSheet(btn_style + """
            QPushButton { font-weight: bold; background-color: #2e7d32; color: white; border: none; }
            QPushButton:hover { background-color: #1b5e20; }
            QPushButton:disabled { background-color: #9e9e9e; color: #e0e0e0; }
        """)
        self.save_btn.clicked.connect(self.accept)

        self.name_input.textChanged.connect(self.update_save_button_state)
        self.prompt_input.textChanged.connect(self.update_save_button_state)

        button_box.addWidget(cancel_btn)
        button_box.addWidget(self.save_btn)
        layout.addLayout(button_box)

        self.update_save_button_state()
        self.setStyleSheet(f"background-color: {'#252525' if colorMode == 'dark' else '#f9f9f9'};")

    def _open_icon_picker(self):
        dialog = IconPickerDialog(current_icon=self._selected_icon, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._selected_icon = dialog.selected_icon
            self._refresh_icon_preview()

    def _init_override_data(self):
        if not self.command or not self.command.provider_override:
            self.base_url_label.hide()
            self.base_url_input.hide()
            return
            
        self.override_checkbox.setChecked(True)
        provider_name = "Custom OpenAI-compatible" if self.command.provider_override == "custom" \
                        else self.command.provider_override
        idx = self.provider_combo.findText(provider_name)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        
        # Load model name based on provider type
        if self.command.provider_override == "custom":
            self.model_input.setText(self.command.custom_provider_model or "")
        else:
            self.model_input.setText(self.command.model_override or "")
            
        self.base_url_input.setText(self.command.custom_provider_base_url or "")
        
        if self._app:
            existing_key = self._app.command_manager.get_command_api_key(self.command.id)
            if existing_key:
                self.api_key_input.setPlaceholderText("•••• Saved •••• (re-enter to change)")
            else:
                self.api_key_input.setPlaceholderText("Leave blank to use global key")

    def _on_override_toggled(self, checked: bool):
        for w in [self.provider_combo, self.model_input, self.api_key_input, self.show_key_btn, self.base_url_input]:
            w.setEnabled(checked)
        if checked:
            self._on_provider_changed(self.provider_combo.currentText())
        else:
            self.base_url_label.hide()
            self.base_url_input.hide()

    # Providers that expose a configurable Base URL
    _PROVIDERS_WITH_BASE_URL = {"Custom OpenAI-compatible", "OpenAI Compatible (For Experts)", "Ollama (For Experts)"}

    def _on_provider_changed(self, name: str):
        has_base_url = name in self._PROVIDERS_WITH_BASE_URL
        is_custom    = name == "Custom OpenAI-compatible"
        self.base_url_label.setVisible(has_base_url)
        self.base_url_input.setVisible(has_base_url)
        if name == "Ollama (For Experts)":
            self.base_url_input.setPlaceholderText("http://localhost:11434")
            self.model_input.setPlaceholderText("E.g. llama3.1:8b")
        elif is_custom or name == "OpenAI Compatible (For Experts)":
            self.base_url_input.setPlaceholderText("https://api.example.com/v1")
            self.model_input.setPlaceholderText("E.g. gpt-4o")
        else:
            self.model_input.setPlaceholderText("Leave blank for default")

        # Pre-fill base URL from global provider config when field is empty
        if has_base_url and not self.base_url_input.text().strip() and self._app:
            provider_config = self._app.config.get("providers", {}).get(name, {})
            global_base_url = provider_config.get("api_base", "")
            if global_base_url:
                self.base_url_input.setText(global_base_url)

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QtWidgets.QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("Show")

    def _refresh_icon_preview(self):
        if self._selected_icon:
            path = _icon_path(self._selected_icon)
            if os.path.exists(path):
                self.icon_btn.setIcon(QtGui.QIcon(path))
                self.icon_btn.setText(f"  {self._selected_icon.split('/')[-1]}")
                return
        self.icon_btn.setIcon(QtGui.QIcon())
        self.icon_btn.setText("Change Icon")

    def _on_shortcut_changed(self, shortcut: str):
        if not shortcut or not self._app:
            self.conflict_label.hide()
            self.update_save_button_state()
            return
        cmd_shortcuts = {
            c.id: c.keyboard_shortcut
            for c in self._app.command_manager.commands
            if c.keyboard_shortcut
        }
        result = check_conflict(
            shortcut=shortcut,
            app_hotkey=self._app.config.get("shortcut", ""),
            command_shortcuts=cmd_shortcuts,
            exclude_command_id=self.command.id if self.command else None,
        )
        if result.has_conflict:
            name = result.conflict_name
            if result.conflict_type == "command":
                cmd = self._app.command_manager.get_command(result.conflict_name)
                if cmd:
                    name = cmd.name
            self.conflict_label.setText(f'⚠ Already used by "{name}"')
            self.conflict_label.show()
        else:
            self.conflict_label.hide()
        self.update_save_button_state()

    def update_save_button_state(self, *args):
        name_ok = len(self.name_input.text().strip()) > 0
        prompt_ok = len(self.prompt_input.toPlainText().strip()) > 0
        no_conflict = not self.conflict_label.isVisible()
        self.save_btn.setEnabled(name_ok and prompt_ok and no_conflict)

    def accept(self):
        if not self.name_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Required Field", "Please enter a Command Name.")
            self.name_input.setFocus()
            return
        if not self.prompt_input.toPlainText().strip():
            QtWidgets.QMessageBox.warning(self, "Required Field", "Please enter the System Prompt / Instruction.")
            self.prompt_input.setFocus()
            return
        super().accept()

    def get_command_data(self) -> dict:
        data = {
            "name": self.name_input.text().strip(),
            "prompt": self.prompt_input.toPlainText().strip(),
            "prefix": self.prefix_input.text(),
            "icon": self._selected_icon,
            "use_response_window": self.window_checkbox.isChecked(),
            "keyboard_shortcut": self.shortcut_widget.get_shortcut() or None,
            "id": self.command.id if self.command else None,
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
                data["custom_provider_model"] = self.model_input.text().strip() or None
            else:
                data["provider_override"] = selected
                data["model_override"] = self.model_input.text().strip() or None
                # Lưu base_url override cho providers có trường này (Ollama, OpenAI Compatible)
                if selected in self._PROVIDERS_WITH_BASE_URL:
                    data["custom_provider_base_url"] = self.base_url_input.text().strip() or None
                
        return data

    def get_api_key_input(self) -> str:
        """Trả về API key người dùng vừa nhập. Trống = không đổi/không dùng."""
        return self.api_key_input.text().strip()
