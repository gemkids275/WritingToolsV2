import uuid
import json
from PySide6 import QtCore, QtGui, QtWidgets
from ui.UIUtils import colorMode
from ui.CommandEditorDialog import CommandEditorDialog
from models.command import Command

class CommandsManagerDialog(QtWidgets.QDialog):
    """
    Hộp thoại quản lý danh sách các lệnh AI.
    """
    def __init__(self, parent=None, app=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Commands Manager")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Tiêu đề & Mô tả
        header_layout = QtWidgets.QVBoxLayout()
        title_label = QtWidgets.QLabel("Manage Commands")
        title_label.setStyleSheet(f"color: {'#fff' if colorMode == 'dark' else '#000'}; font-size: 18px; font-weight: bold;")
        desc_label = QtWidgets.QLabel("Add, edit, or remove AI shortcuts and system prompts.")
        desc_label.setStyleSheet(f"color: {'#aaa' if colorMode == 'dark' else '#666'}; font-size: 12px;")
        header_layout.addWidget(title_label)
        header_layout.addWidget(desc_label)
        main_layout.addLayout(header_layout)

        # Khu vực danh sách và nút điều khiển
        content_layout = QtWidgets.QHBoxLayout()
        
        # Danh sách lệnh
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {'#333' if colorMode == 'dark' else '#fff'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
                border-radius: 5px;
                padding: 5px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {'#444' if colorMode == 'dark' else '#eee'};
            }}
            QListWidget::item:selected {{
                background-color: {'#444' if colorMode == 'dark' else '#f0f0f0'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
            }}
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_edit_clicked)
        content_layout.addWidget(self.list_widget, 7)

        # Cột phím chức năng bên phải
        actions_layout = QtWidgets.QVBoxLayout()
        actions_layout.setSpacing(10)
        
        btn_style = f"""
            QPushButton {{
                background-color: {'#444' if colorMode == 'dark' else '#eee'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                border-radius: 5px;
                padding: 8px;
                text-align: left;
                padding-left: 15px;
            }}
            QPushButton:hover {{
                background-color: {'#555' if colorMode == 'dark' else '#ddd'};
            }}
        """

        self.add_btn = QtWidgets.QPushButton("Add New...")
        self.add_btn.setStyleSheet(btn_style + "QPushButton { background-color: #2e7d32; color: white; border: none; } QPushButton:hover { background-color: #1b5e20; }")
        self.add_btn.clicked.connect(self.on_add_clicked)

        self.edit_btn = QtWidgets.QPushButton("Edit...")
        self.edit_btn.setStyleSheet(btn_style)
        self.edit_btn.clicked.connect(self.on_edit_clicked)

        self.delete_btn = QtWidgets.QPushButton("Delete")
        self.delete_btn.setStyleSheet(btn_style)
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        
        self.export_btn = QtWidgets.QPushButton("Export Selected...")
        self.export_btn.setStyleSheet(btn_style)
        self.export_btn.clicked.connect(self.on_export_clicked)

        self.import_btn = QtWidgets.QPushButton("Import Command...")
        self.import_btn.setStyleSheet(btn_style)
        self.import_btn.clicked.connect(self.on_import_clicked)

        self.export_btn.setEnabled(False)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        actions_layout.addWidget(self.add_btn)
        actions_layout.addWidget(self.edit_btn)
        actions_layout.addWidget(self.delete_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.import_btn)
        actions_layout.addStretch()

        self.restore_btn = QtWidgets.QPushButton("Restore Built-ins")
        self.restore_btn.setStyleSheet(btn_style)
        self.restore_btn.clicked.connect(self.on_restore_clicked)
        actions_layout.addWidget(self.restore_btn)

        content_layout.addLayout(actions_layout, 3)
        main_layout.addLayout(content_layout)

        # Nút Close ở dưới
        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.setStyleSheet(btn_style + "QPushButton { text-align: center; padding-left: 8px; }")
        self.close_btn.clicked.connect(self.accept)
        main_layout.addWidget(self.close_btn)

        self.setStyleSheet(f"background-color: {'#252525' if colorMode == 'dark' else '#f9f9f9'};")

    def refresh_list(self):
        """Lấy dữ liệu từ CommandManager và hiển thị lên UI."""
        self.list_widget.clear()
        commands = self.app.command_manager.commands
        for cmd in commands:
            item = QtWidgets.QListWidgetItem(f"{cmd.name} {'(System)' if cmd.is_built_in else ''}")
            item.setData(QtCore.Qt.UserRole, cmd.id)
            self.list_widget.addItem(item)

    def on_add_clicked(self):
        dialog = CommandEditorDialog(self)
        if dialog.exec_():
            data = dialog.get_command_data()
            new_id = str(uuid.uuid4())
            new_cmd = Command(
                name=data["name"],
                prompt=data["prompt"],
                prefix=data["prefix"],
                icon=data["icon"],
                use_response_window=data["use_response_window"],
                is_built_in=False,
                keyboard_shortcut=data.get("keyboard_shortcut"),
                id=new_id,
                provider_override=data.get("provider_override"),
                model_override=data.get("model_override"),
                custom_provider_base_url=data.get("custom_provider_base_url"),
                custom_provider_model=data.get("custom_provider_model"),
            )
            self.app.command_manager.add_command(new_cmd)
            
            # Save API key if provided
            new_key = dialog.get_api_key_input()
            if new_key:
                self.app.command_manager.save_command_api_key(new_id, new_key)
                
            self.app.refresh_command_shortcuts()
            self.refresh_list()

    def _on_selection_changed(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            self.delete_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            return
        cmd_id = current_item.data(QtCore.Qt.UserRole)
        cmd = self.app.command_manager.get_command(cmd_id)
        self.delete_btn.setEnabled(bool(cmd and cmd.deletable))
        self.export_btn.setEnabled(bool(cmd))

    def on_edit_clicked(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        
        cmd_id = current_item.data(QtCore.Qt.UserRole)
        cmd = self.app.command_manager.get_command(cmd_id)
        if not cmd:
            return

        dialog = CommandEditorDialog(self, cmd)
        if dialog.exec_():
            data = dialog.get_command_data()
            updated_cmd = Command(
                name=data["name"],
                prompt=data["prompt"],
                prefix=data["prefix"],
                icon=data["icon"],
                use_response_window=data["use_response_window"],
                is_built_in=cmd.is_built_in,
                deletable=cmd.deletable,
                keyboard_shortcut=data.get("keyboard_shortcut"),
                id=cmd.id,
                provider_override=data.get("provider_override"),
                model_override=data.get("model_override"),
                custom_provider_base_url=data.get("custom_provider_base_url"),
                custom_provider_model=data.get("custom_provider_model"),
            )
            self.app.command_manager.update_command(updated_cmd)
            
            # Update API key if provided
            new_key = dialog.get_api_key_input()
            if new_key:
                self.app.command_manager.save_command_api_key(cmd.id, new_key)
            elif not data.get("provider_override"):
                # If override is disabled, clean up the old key
                from models.secure_storage import delete_command_api_key
                delete_command_api_key(cmd.id)
                
            self.app.refresh_command_shortcuts()
            self.refresh_list()

    def on_delete_clicked(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        
        cmd_id = current_item.data(QtCore.Qt.UserRole)
        cmd = self.app.command_manager.get_command(cmd_id)
        if not cmd:
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Delete Command",
            f"Are you sure you want to delete '{cmd.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.app.command_manager.delete_command(cmd_id)
            self.refresh_list()

    def on_restore_clicked(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Restore Built-in Commands",
            "This will restore all deleted system commands. Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.app.command_manager.restore_built_ins()
            self.refresh_list()

    def on_export_clicked(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        
        cmd_id = current_item.data(QtCore.Qt.UserRole)
        command = self.app.command_manager.get_command(cmd_id)
        if not command:
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Command",
            f"AIShortcuts_{command.name}.json",
            "JSON Files (*.json)"
        )
        if not path:
            return

        bundle = self.app.command_manager.create_export_bundle([command])
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2, ensure_ascii=False)
            QtWidgets.QMessageBox.information(self, "Success", "Command exported successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def on_import_clicked(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Command",
            "",
            "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            commands = self.app.command_manager.decode_import_bundle(data)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Invalid file: {str(e)}")
            return

        used_shortcuts = self.app.command_manager.get_used_shortcuts()
        added = 0

        for cmd in commands:
            # ID conflict: if ID already exists, assign new UUID and mark as imported
            existing = self.app.command_manager.get_command(cmd.id)
            if existing:
                if not existing.is_built_in:
                    cmd.id = str(uuid.uuid4())
                    cmd.name = cmd.name + " (Imported)"
                else:
                    # Skip built-in with same ID to avoid duplicates
                    continue

            # Shortcut conflict: clear if already used
            if cmd.keyboard_shortcut and cmd.keyboard_shortcut in used_shortcuts:
                cmd.keyboard_shortcut = None

            cmd.is_built_in = False
            self.app.command_manager.add_command(cmd)
            added += 1

        self.app.refresh_command_shortcuts()
        self.refresh_list()
        QtWidgets.QMessageBox.information(
            self, "Import Complete",
            f"{added} command(s) imported."
        )
