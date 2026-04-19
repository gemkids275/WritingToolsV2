import logging
import os
import sys
import threading
import uuid
import json

from aiprovider import AIProvider
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QListWidgetItem,
                                QRadioButton, QScrollArea, QStackedWidget,
                                QVBoxLayout, QWidget)

from ui.AutostartManager import AutostartManager
from ui.UIUtils import UIUtils, colorMode
from ui.CommandEditorDialog import CommandEditorDialog
from models.command import Command
from models.shortcut_conflict import check_conflict
from update_checker import VERSION_STR

# For translations
_ = lambda x: x

class SettingsWindow(QtWidgets.QWidget):
    """
    The settings window for the application.
    Modern Sidebar-based layout similar to macOS version.
    """
    close_signal = QtCore.Signal()
    update_result_signal = Signal(bool)

    def __init__(self, app, providers_only=False, initial_tab=None):
        super().__init__()
        self.app = app
        self.providers_only = providers_only
        self.initial_tab = initial_tab
        
        # UI Elements
        self.sidebar = None
        self.stacked_widget = None
        
        # General Page Elements
        self.shortcut_input = None
        self.autostart_checkbox = None
        self.gradient_radio = None
        self.plain_radio = None
        self.streaming_checkbox = None
        self.language_dropdown = None
        
        # Commands Page Elements
        self.commands_list_widget = None
        
        # Provider Page Elements
        self.provider_dropdown = None
        self.provider_container_layout = None
        self.current_provider_layout = None
        
        self.init_ui()
        self.retranslate_ui()
        self.update_result_signal.connect(self.handle_update_result)

    def retranslate_ui(self):
        self.setWindowTitle(self.app._("Settings"))
        # Update sidebar items
        if self.sidebar:
            self.sidebar.item(0).setText(self.app._("General"))
            self.sidebar.item(1).setText(self.app._("AI Providers"))
            self.sidebar.item(2).setText(self.app._("Commands"))
            self.sidebar.item(3).setText(self.app._("About"))
        
        # We need to refresh the current page to update translated labels
        # However, for simplicity in this Sidebar layout, Sidebar items are handled above.
        # Most labels in create_general_page etc. are static and would need a full page recreation
        # but re-triggering retranslate_ui on the App level will handle most cases if we call it correctly.

    def init_ui(self):
        """Initialize the modern sidebar UI."""
        self.setMinimumSize(750, 550)
        UIUtils.setup_window_and_layout(self)
        
        # Main layout: Horizontal (Sidebar | Content)
        main_layout = QHBoxLayout(self.background)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- SIDEBAR ---
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet(f"""
            QListWidget {{
                background-color: {'rgba(45, 45, 45, 0.8)' if colorMode == 'dark' else 'rgba(240, 240, 240, 0.8)'};
                border: none;
                border-right: 1px solid {'#444' if colorMode == 'dark' else '#ccc'};
                outline: none;
                padding-top: 10px;
            }}
            QListWidget::item {{
                height: 45px;
                padding-left: 15px;
                color: {'#ffffff' if colorMode == 'dark' else '#333333'};
                font-size: 14px;
            }}
            QListWidget::item:selected {{
                background-color: {'#555' if colorMode == 'dark' else '#ddd'};
                border-left: 4px solid #4CAF50;
                font-weight: bold;
            }}
        """)
        
        # Add Sidebar Items
        item_general = QListWidgetItem("General")
        item_providers = QListWidgetItem("AI Providers")
        item_commands = QListWidgetItem("Commands")
        item_about = QListWidgetItem("About")
        
        self.sidebar.addItem(item_general)
        self.sidebar.addItem(item_providers)
        self.sidebar.addItem(item_commands)
        self.sidebar.addItem(item_about)
        
        main_layout.addWidget(self.sidebar)
        
        # --- CONTENT AREA (Stacked Widget) ---
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        
        # Add Pages
        self.stacked_widget.addWidget(self.create_general_page())
        self.stacked_widget.addWidget(self.create_providers_page())
        self.stacked_widget.addWidget(self.create_commands_page())
        self.stacked_widget.addWidget(self.create_about_page())
        
        # Connect sidebar selection
        self.sidebar.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        
        # Handle initial tab or providers_only mode
        if self.initial_tab == "about":
            self.sidebar.setCurrentRow(3)
        elif self.initial_tab == "commands":
            self.sidebar.setCurrentRow(2)
        elif self.providers_only:
            self.sidebar.setCurrentRow(1)
        else:
            self.sidebar.setCurrentRow(0)
            
        main_layout.addWidget(self.stacked_widget)

    def create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)
        
        title = QtWidgets.QLabel(self.app._("General Settings"))
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        layout.addWidget(title)
        
        # Shortcut
        shortcut_group = QWidget()
        short_layout = QVBoxLayout(shortcut_group)
        short_layout.setContentsMargins(0, 0, 0, 0)
        
        shortcut_label = QtWidgets.QLabel(self.app._("Global Shortcut Key:"))
        shortcut_label.setStyleSheet(f"font-size: 16px; color: {'#aaa' if colorMode == 'dark' else '#666'};")
        short_layout.addWidget(shortcut_label)
        
        self.shortcut_input = QtWidgets.QLineEdit(self.app.config.get('shortcut', 'ctrl+space'))
        self.shortcut_input.setStyleSheet(f"""
            font-size: 16px; padding: 8px; border-radius: 5px;
            background-color: {'#444' if colorMode == 'dark' else 'white'};
            color: {'#ffffff' if colorMode == 'dark' else '#000000'};
            border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
        """)
        short_layout.addWidget(self.shortcut_input)
        layout.addWidget(shortcut_group)
        
        # Autostart
        if AutostartManager.get_startup_path():
            self.autostart_checkbox = QtWidgets.QCheckBox(self.app._("Launch Writing Tools on system startup"))
            self.autostart_checkbox.setStyleSheet(f"font-size: 15px; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
            self.autostart_checkbox.setChecked(AutostartManager.check_autostart())
            layout.addWidget(self.autostart_checkbox)
        
        # Theme
        theme_group = QWidget()
        theme_v_layout = QVBoxLayout(theme_group)
        theme_v_layout.setContentsMargins(0, 0, 0, 0)
        
        theme_label = QtWidgets.QLabel(self.app._("Background Appearance:"))
        theme_label.setStyleSheet(f"font-size: 16px; color: {'#aaa' if colorMode == 'dark' else '#666'};")
        theme_v_layout.addWidget(theme_label)
        
        theme_h_layout = QHBoxLayout()
        self.gradient_radio = QRadioButton(self.app._("Vibrant Gradient"))
        self.plain_radio = QRadioButton(self.app._("Minimal Plain"))
        self.gradient_radio.setStyleSheet(f"color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        self.plain_radio.setStyleSheet(f"color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        
        current_theme = self.app.config.get('theme', 'gradient')
        self.gradient_radio.setChecked(current_theme == 'gradient')
        self.plain_radio.setChecked(current_theme == 'plain')
        
        theme_h_layout.addWidget(self.gradient_radio)
        theme_h_layout.addWidget(self.plain_radio)
        theme_v_layout.addLayout(theme_h_layout)
        layout.addWidget(theme_group)
        
        # Language
        lang_group = QWidget()
        lang_v_layout = QVBoxLayout(lang_group)
        lang_v_layout.setContentsMargins(0, 0, 0, 0)
        
        lang_label = QtWidgets.QLabel(self.app._("Interface Language:"))
        lang_label.setStyleSheet(f"font-size: 16px; color: {'#aaa' if colorMode == 'dark' else '#666'};")
        lang_v_layout.addWidget(lang_label)
        
        self.language_dropdown = QtWidgets.QComboBox()
        self.language_dropdown.addItem("Tiếng Việt", "vi")
        self.language_dropdown.addItem("English", "en")
        self.language_dropdown.addItem("Italiano", "it")
        self.language_dropdown.setStyleSheet(f"""
            font-size: 16px; padding: 8px; border-radius: 5px;
            background-color: {'#444' if colorMode == 'dark' else 'white'};
            color: {'#ffffff' if colorMode == 'dark' else '#000000'};
            border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
        """)
        
        # Set current selection
        current_locale = self.app.config.get('locale', 'vi')
        idx = self.language_dropdown.findData(current_locale)
        if idx != -1:
            self.language_dropdown.setCurrentIndex(idx)
        
        lang_v_layout.addWidget(self.language_dropdown)
        layout.addWidget(lang_group)
        
        # Streaming
        self.streaming_checkbox = QtWidgets.QCheckBox(self.app._("Enable Real-time Streaming (Recommended)"))
        self.streaming_checkbox.setStyleSheet(f"font-size: 15px; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        self.streaming_checkbox.setChecked(self.app.config.get('streaming', True))
        layout.addWidget(self.streaming_checkbox)
        
        layout.addStretch()
        
        # Save Button at bottom
        save_btn = QtWidgets.QPushButton(self.app._("Save Settings"))
        save_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 12px; font-size: 16px; border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #45a049; }
        """)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        return page

    def create_providers_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        title = QtWidgets.QLabel(self.app._("AI Providers"))
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        layout.addWidget(title)
        
        # Provider Selector
        selector_group = QWidget()
        sel_layout = QVBoxLayout(selector_group)
        sel_layout.setContentsMargins(0, 0, 0, 0)
        
        sel_label = QtWidgets.QLabel(self.app._("Select Active Provider:"))
        sel_label.setStyleSheet(f"font-size: 14px; color: {'#aaa' if colorMode == 'dark' else '#666'};")
        sel_layout.addWidget(sel_label)
        
        self.provider_dropdown = QtWidgets.QComboBox()
        self.provider_dropdown.setStyleSheet(f"""
            font-size: 16px; padding: 8px; border-radius: 5px;
            background-color: {'#444' if colorMode == 'dark' else 'white'};
            color: {'#ffffff' if colorMode == 'dark' else '#000000'};
            border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
        """)
        
        current_provider_name = self.app.config.get('provider', self.app.providers[0].provider_name)
        for provider in self.app.providers:
            self.provider_dropdown.addItem(provider.provider_name)
        
        self.provider_dropdown.setCurrentText(current_provider_name)
        sel_layout.addWidget(self.provider_dropdown)
        layout.addWidget(selector_group)
        
        # Separator
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {'#444' if colorMode == 'dark' else '#ddd'};")
        layout.addWidget(line)
        
        # Provider Details Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        self.provider_container_widget = QWidget()
        self.provider_container_layout = QVBoxLayout(self.provider_container_widget)
        self.provider_container_layout.setContentsMargins(0, 0, 0, 0)
        self.provider_container_layout.setSpacing(15)
        
        scroll.setWidget(self.provider_container_widget)
        layout.addWidget(scroll)
        
        # Initial Provider UI
        self.update_provider_ui()
        
        # Connect dropdown
        self.provider_dropdown.currentIndexChanged.connect(self.update_provider_ui)

        # Save Button
        save_btn = QtWidgets.QPushButton(self.app._("Save Settings"))
        save_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 12px; font-size: 16px; border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #45a049; }
        """)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        return page

    def create_commands_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)
        
        title = QtWidgets.QLabel(self.app._("Commands Management"))
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        layout.addWidget(title)

        desc = QtWidgets.QLabel(self.app._("Add, edit, or remove AI shortcuts and system prompts."))
        desc.setStyleSheet(f"color: {'#aaa' if colorMode == 'dark' else '#666'}; font-size: 13px;")
        layout.addWidget(desc)

        # Content Layout (List | Actions)
        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(20)

        # 1. Commands List
        self.commands_list_widget = QtWidgets.QListWidget()
        self.commands_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {'#333' if colorMode == 'dark' else '#fff'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#555' if colorMode == 'dark' else '#ccc'};
                border-radius: 6px;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 12px;
                border-bottom: 1px solid {'#444' if colorMode == 'dark' else '#eee'};
            }}
            QListWidget::item:selected {{
                background-color: {'#4CAF50' if colorMode == 'dark' else '#e8f5e9'};
                color: {'#fff' if colorMode == 'dark' else '#2e7d32'};
                border-radius: 4px;
            }}
        """)
        self.commands_list_widget.setIconSize(QtCore.QSize(20, 20))
        self.commands_list_widget.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.commands_list_widget.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.commands_list_widget.model().rowsMoved.connect(self._on_commands_reordered)
        self.commands_list_widget.itemDoubleClicked.connect(self.on_edit_command_clicked)
        content_layout.addWidget(self.commands_list_widget, 7)

        # 2. Side Actions
        side_layout = QVBoxLayout()
        side_layout.setSpacing(10)

        btn_style = f"""
            QPushButton {{
                background-color: {'#444' if colorMode == 'dark' else '#eee'};
                color: {'#fff' if colorMode == 'dark' else '#000'};
                border: 1px solid {'#666' if colorMode == 'dark' else '#ccc'};
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {'#555' if colorMode == 'dark' else '#ddd'};
            }}
        """

        add_btn = QtWidgets.QPushButton(self.app._("Add New..."))
        add_btn.setStyleSheet(btn_style + "QPushButton { background-color: #2e7d32; color: white; border: none; font-weight: bold; } QPushButton:hover { background-color: #1b5e20; }")
        add_btn.clicked.connect(self.on_add_command_clicked)
        
        edit_btn = QtWidgets.QPushButton(self.app._("Edit..."))
        edit_btn.setStyleSheet(btn_style)
        edit_btn.clicked.connect(self.on_edit_command_clicked)

        self.delete_btn = QtWidgets.QPushButton(self.app._("Delete"))
        self.delete_btn.setStyleSheet(btn_style + "QPushButton:disabled { background-color: #444; color: #888; border: 1px solid #555; }")
        self.delete_btn.clicked.connect(self.on_delete_command_clicked)

        self.commands_list_widget.itemSelectionChanged.connect(self.on_command_selection_changed)

        side_layout.addWidget(add_btn)
        side_layout.addWidget(edit_btn)
        side_layout.addWidget(self.delete_btn)

        self.export_cmd_btn = QtWidgets.QPushButton(self.app._("Export Selected..."))
        self.export_cmd_btn.setStyleSheet(btn_style)
        self.export_cmd_btn.clicked.connect(self.on_export_command_clicked)

        self.import_cmd_btn = QtWidgets.QPushButton(self.app._("Import Command..."))
        self.import_cmd_btn.setStyleSheet(btn_style)
        self.import_cmd_btn.clicked.connect(self.on_import_command_clicked)

        side_layout.addWidget(self.export_cmd_btn)
        side_layout.addWidget(self.import_cmd_btn)
        side_layout.addStretch()

        restore_btn = QtWidgets.QPushButton(self.app._("Restore Defaults"))
        restore_btn.setStyleSheet(btn_style)
        restore_btn.clicked.connect(self.on_restore_commands_clicked)
        side_layout.addWidget(restore_btn)

        content_layout.addLayout(side_layout, 3)
        layout.addLayout(content_layout)

        # 3. Bottom Backup/Restore Actions
        backup_layout = QtWidgets.QHBoxLayout()
        backup_layout.setSpacing(10)
        
        self.export_all_btn = QtWidgets.QPushButton(self.app._("Backup All Config..."))
        self.export_all_btn.setStyleSheet(btn_style)
        self.export_all_btn.clicked.connect(self.on_export_all_clicked)
        
        self.import_all_btn = QtWidgets.QPushButton(self.app._("Restore Full Config..."))
        self.import_all_btn.setStyleSheet(btn_style)
        self.import_all_btn.clicked.connect(self.on_import_all_clicked)
        
        backup_layout.addWidget(self.export_all_btn)
        backup_layout.addWidget(self.import_all_btn)
        backup_layout.addStretch()
        layout.addLayout(backup_layout)

        # Initial data load
        self.refresh_commands_list()
        
        return page

    def _on_commands_reordered(self):
        new_order = [
            self.commands_list_widget.item(i).data(QtCore.Qt.UserRole)
            for i in range(self.commands_list_widget.count())
        ]
        # ChatNoSelection luôn ở cuối — nếu bị kéo đi chỗ khác thì đưa lại
        if "ChatNoSelection" in new_order:
            new_order = [cid for cid in new_order if cid != "ChatNoSelection"]
            new_order.append("ChatNoSelection")
        self.app.command_manager.reorder_commands(new_order)
        self.refresh_commands_list()

    def refresh_commands_list(self):
        """Lấy dữ liệu từ CommandManager và hiển thị lên UI."""
        if not self.commands_list_widget:
            return

        self.commands_list_widget.clear()
        commands = self.app.command_manager.commands
        for cmd in commands:
            label = f"{cmd.name} {'(System)' if cmd.is_built_in else ''}"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, cmd.id)
            if cmd.icon:
                suffix = '_dark' if colorMode == 'dark' else '_light'
                icon_path = os.path.join(os.path.dirname(sys.argv[0]), f"{cmd.icon}{suffix}.png")
                if os.path.exists(icon_path):
                    item.setIcon(QtGui.QIcon(icon_path))
            self.commands_list_widget.addItem(item)

    def on_add_command_clicked(self):
        dialog = CommandEditorDialog(self)
        if dialog.exec_():
            data = dialog.get_command_data()
            new_id = str(uuid.uuid4())
            new_cmd = Command(
                id=new_id,
                name=data["name"],
                prompt=data["prompt"],
                prefix=data["prefix"],
                icon=data["icon"],
                use_response_window=data["use_response_window"],
                keyboard_shortcut=data.get("keyboard_shortcut"),
                is_built_in=False,
                provider_override=data.get("provider_override"),
                model_override=data.get("model_override"),
                custom_provider_base_url=data.get("custom_provider_base_url"),
                custom_provider_model=data.get("custom_provider_model"),
            )
            self.app.command_manager.add_command(new_cmd)
            new_key = dialog.get_api_key_input()
            if new_key:
                self.app.command_manager.save_command_api_key(new_id, new_key)
            self.app.refresh_command_shortcuts()
            self.refresh_commands_list()

    def on_edit_command_clicked(self):
        current_item = self.commands_list_widget.currentItem()
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
                id=cmd.id,
                name=data["name"],
                prompt=data["prompt"],
                prefix=data["prefix"],
                icon=data["icon"],
                use_response_window=data["use_response_window"],
                keyboard_shortcut=data.get("keyboard_shortcut"),
                is_built_in=cmd.is_built_in,
                deletable=cmd.deletable,
                provider_override=data.get("provider_override"),
                model_override=data.get("model_override"),
                custom_provider_base_url=data.get("custom_provider_base_url"),
                custom_provider_model=data.get("custom_provider_model"),
            )
            self.app.command_manager.update_command(updated_cmd)
            new_key = dialog.get_api_key_input()
            if new_key:
                self.app.command_manager.save_command_api_key(cmd.id, new_key)
            elif not data.get("provider_override"):
                from models.secure_storage import delete_command_api_key
                delete_command_api_key(cmd.id)
            self.app.refresh_command_shortcuts()
            self.refresh_commands_list()

    def on_command_selection_changed(self):
        current_item = self.commands_list_widget.currentItem()
        if not current_item:
            self.delete_btn.setEnabled(False)
            return
            
        cmd_id = current_item.data(QtCore.Qt.UserRole)
        cmd = self.app.command_manager.get_command(cmd_id)
        self.delete_btn.setEnabled(bool(cmd and cmd.deletable))
        self.export_cmd_btn.setEnabled(bool(cmd))

    def on_delete_command_clicked(self):
        current_item = self.commands_list_widget.currentItem()
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
            self.refresh_commands_list()

    def on_restore_commands_clicked(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Restore Built-in Commands",
            "This will restore all deleted system commands. Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.app.command_manager.restore_built_ins()
            self.refresh_commands_list()

    def on_export_command_clicked(self):
        current_item = self.commands_list_widget.currentItem()
        if not current_item:
            return
        
        cmd_id = current_item.data(QtCore.Qt.UserRole)
        command = self.app.command_manager.get_command(cmd_id)
        if not command:
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self.app._("Export Command"),
            f"AIShortcuts_{command.name}.json",
            "JSON Files (*.json)"
        )
        if not path:
            return

        bundle = self.app.command_manager.create_export_bundle([command])
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2, ensure_ascii=False)
            QtWidgets.QMessageBox.information(self, self.app._("Success"), self.app._("Command exported successfully."))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, self.app._("Error"), str(e))

    def on_import_command_clicked(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.app._("Import Command"),
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
            QtWidgets.QMessageBox.critical(self, self.app._("Error"), f"Invalid file: {str(e)}")
            return

        used_shortcuts = self.app.command_manager.get_used_shortcuts()
        added = 0

        for cmd in commands:
            existing = self.app.command_manager.get_command(cmd.id)
            if existing:
                if not existing.is_built_in:
                    cmd.id = str(uuid.uuid4())
                    cmd.name = cmd.name + " (Imported)"
                else:
                    continue

            if cmd.keyboard_shortcut and cmd.keyboard_shortcut in used_shortcuts:
                cmd.keyboard_shortcut = None

            cmd.is_built_in = False
            self.app.command_manager.add_command(cmd)
            added += 1

        self.refresh_commands_list()
        # Refresh popup if open
        if hasattr(self.app, 'popup_window') and self.app.popup_window:
            self.app.popup_window.setup_ui()

        QtWidgets.QMessageBox.information(self, self.app._("Success"), self.app._("{0} command(s) imported.").format(added))

    def on_export_all_clicked(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self.app._("Export All Config"),
            "AIShortcuts_FullBackup.json",
            "JSON Files (*.json)"
        )
        if not path:
            return

        all_commands = self.app.command_manager.commands
        bundle = self.app.command_manager.create_export_bundle(all_commands)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2, ensure_ascii=False)
            QtWidgets.QMessageBox.information(self, self.app._("Success"), self.app._("Config exported successfully."))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, self.app._("Error"), str(e))

    def on_import_all_clicked(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.app._("Restore Config"),
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
            QtWidgets.QMessageBox.critical(self, self.app._("Error"), self.app._("Invalid file: {0}").format(str(e)))
            return

        if not commands:
            QtWidgets.QMessageBox.warning(self, self.app._("Empty Backup"), self.app._("No commands found in this file."))
            return

        dialog = ImportChoiceDialog(self, self.app, commands)
        dialog.exec()
        self.app.refresh_command_shortcuts()
        self.refresh_commands_list()

    def update_provider_ui(self):
        """Update the detail panel for the selected provider."""
        if self.current_provider_layout:
            # Clear old layout
            UIUtils.clear_layout(self.current_provider_layout)
            self.current_provider_layout.deleteLater()
            self.current_provider_layout = None
            
        idx = self.provider_dropdown.currentIndex()
        if idx < 0: return
        
        provider = self.app.providers[idx]
        self.current_provider_layout = QVBoxLayout()
        
        # Header (Logo + Name)
        header_layout = QHBoxLayout()
        if provider.logo:
            logo_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', f"provider_{provider.logo}.png")
            if os.path.exists(logo_path):
                pixmap = UIUtils.resize_and_round_image(QImage(logo_path), 40, 20)
                lbl_logo = QtWidgets.QLabel()
                lbl_logo.setPixmap(pixmap)
                header_layout.addWidget(lbl_logo)
        
        lbl_name = QtWidgets.QLabel(provider.provider_name)
        lbl_name.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {'#ffffff' if colorMode == 'dark' else '#333333'};")
        header_layout.addWidget(lbl_name)
        header_layout.addStretch()
        self.current_provider_layout.addLayout(header_layout)
        
        # Description
        if provider.description:
            lbl_desc = QtWidgets.QLabel(provider.description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet(f"color: {'#aaa' if colorMode == 'dark' else '#666'}; font-size: 14px;")
            self.current_provider_layout.addWidget(lbl_desc)
        
        # Provider Button (e.g. Get API Key)
        if hasattr(provider, 'button_text') and provider.button_text:
            btn = QtWidgets.QPushButton(provider.button_text)
            btn.setStyleSheet("""
                QPushButton { background-color: #0078D4; color: white; padding: 8px 15px; border-radius: 4px; border: none; }
                QPushButton:hover { background-color: #005A9E; }
            """)
            btn.clicked.connect(provider.button_action)
            self.current_provider_layout.addWidget(btn, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        # Settings Fields
        # Ensure config exists for this provider
        if "providers" not in self.app.config: self.app.config["providers"] = {}
        if provider.provider_name not in self.app.config["providers"]:
            self.app.config["providers"][provider.provider_name] = {}
            
        for setting in provider.settings:
            val = self.app.config["providers"][provider.provider_name].get(setting.name, setting.default_value)
            setting.set_value(val)
            setting.render_to_layout(self.current_provider_layout)
        self.current_provider_layout.addStretch()
        self.provider_container_layout.addLayout(self.current_provider_layout)

    def create_about_page(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 20, 30, 20)

        # Apply dark mode styles using darkdetect
        is_dark = colorMode == 'dark'

        # Icon
        icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if os.path.exists(icon_path):
            lbl_icon = QtWidgets.QLabel()
            lbl_icon.setPixmap(QtGui.QPixmap(icon_path).scaled(96, 96, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(lbl_icon, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            
        # Title
        title = QtWidgets.QLabel(self.app._("About AI Shortcuts"))
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {'#ffffff' if is_dark else '#333333'};")
        layout.addWidget(title, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Description
        desc = QtWidgets.QLabel(self.app._("AI Shortcuts is a free, lightweight utility that enhances your writing with AI."))
        desc.setStyleSheet(f"font-size: 14px; color: {'#bbbbbb' if is_dark else '#666666'};")
        desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # Separator Line
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        line.setStyleSheet(f"color: {'#444444' if is_dark else '#dddddd'};")
        layout.addWidget(line)

        # -- Creators Section --
        creators_label = QtWidgets.QLabel(self.app._("Creators"))
        creators_label.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {'#ffffff' if is_dark else '#333333'};")
        layout.addWidget(creators_label)

        creators_card = QtWidgets.QFrame()
        creators_card.setObjectName("CreatorsCard")
        creators_card.setStyleSheet("""
            #CreatorsCard {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QLabel { background: transparent; border: none; }
        """ if is_dark else """
            #CreatorsCard {
                background: rgba(0, 0, 0, 0.03);
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 8px;
            }
            QLabel { background: transparent; border: none; }
        """)
        
        card_layout = QtWidgets.QVBoxLayout(creators_card)
        card_layout.setSpacing(8)

        # Nam Trần (Fork Author)
        nam_title = QtWidgets.QLabel(self.app._("Customized version & Forked by Nam Trần"))
        nam_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        nam_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        card_layout.addWidget(nam_title)

        nam_sub = QtWidgets.QLabel(self.app._("A technology enthusiast"))
        nam_sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        nam_sub.setStyleSheet("font-size: 12px; color: #888888;")
        card_layout.addWidget(nam_sub)

        nam_links = QtWidgets.QHBoxLayout()
        nam_links.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        email_nam = QtWidgets.QLabel('<a href="mailto:gemkids275@gmail.com" style="color: #3b82f6; text-decoration: none;">Email Nam</a>')
        email_nam.setOpenExternalLinks(True)
        github_nam = QtWidgets.QLabel('<a href="https://github.com/gemkids275/WritingToolsV2" style="color: #3b82f6; text-decoration: none;">GitHub Repo</a>')
        github_nam.setOpenExternalLinks(True)
        nam_links.addWidget(email_nam)
        nam_links.addSpacing(15)
        nam_links.addWidget(github_nam)
        card_layout.addLayout(nam_links)

        # Separator inside card
        inner_line = QtWidgets.QFrame()
        inner_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        inner_line.setStyleSheet(f"color: {'#333333' if is_dark else '#eeeeee'};")
        card_layout.addWidget(inner_line)

        # Original Developers
        orig_header = QtWidgets.QLabel(self.app._("Original Developers"))
        orig_header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        orig_header.setStyleSheet("font-size: 12px; color: #888888;")
        card_layout.addWidget(orig_header)

        # Jesai
        jesai_lbl = QtWidgets.QLabel("Jesai")
        jesai_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        jesai_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        card_layout.addWidget(jesai_lbl)

        jesai_links = QtWidgets.QHBoxLayout()
        jesai_links.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        jesai_email = QtWidgets.QLabel('<a href="mailto:theJayTea@gmail.com" style="color: #3b82f6; text-decoration: none;">Email</a>')
        jesai_email.setOpenExternalLinks(True)
        jesai_web = QtWidgets.QLabel('<a href="https://github.com/theJayTea" style="color: #3b82f6; text-decoration: none;">Bliss AI</a>')
        jesai_web.setOpenExternalLinks(True)
        jesai_links.addWidget(jesai_email)
        jesai_links.addSpacing(10)
        jesai_links.addWidget(jesai_web)
        card_layout.addLayout(jesai_links)

        # Arya
        arya_lbl = QtWidgets.QLabel("Arya Mirsepasi")
        arya_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        arya_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        card_layout.addWidget(arya_lbl)

        arya_links = QtWidgets.QHBoxLayout()
        arya_links.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        arya_email = QtWidgets.QLabel('<a href="mailto:aryamirsepasi@gmail.com" style="color: #3b82f6; text-decoration: none;">Email</a>')
        arya_email.setOpenExternalLinks(True)
        arya_web = QtWidgets.QLabel('<a href="https://prosekey.ai" style="color: #3b82f6; text-decoration: none;">ProseKey AI</a>')
        arya_web.setOpenExternalLinks(True)
        arya_links.addWidget(arya_email)
        arya_links.addSpacing(10)
        arya_links.addWidget(arya_web)
        card_layout.addLayout(arya_links)

        layout.addWidget(creators_card)

        # -- Version & Updates Section --
        updates_label = QtWidgets.QLabel(self.app._("Version & Updates"))
        updates_label.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {'#ffffff' if is_dark else '#333333'};")
        layout.addWidget(updates_label)

        updates_card = QtWidgets.QFrame()
        updates_card.setObjectName("UpdatesCard")
        updates_card.setStyleSheet(creators_card.styleSheet())
        
        updates_layout = QtWidgets.QVBoxLayout(updates_card)
        
        v_info = QtWidgets.QLabel(self.app._("Version: {0}").format(VERSION_STR))
        v_info.setStyleSheet("font-weight: bold; font-size: 13px;")
        updates_layout.addWidget(v_info)

        self.update_status = QtWidgets.QLabel(self.app._("Not checked yet."))
        self.update_status.setStyleSheet("font-size: 12px; color: #888888;")
        updates_layout.addWidget(self.update_status)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_check_update = QtWidgets.QPushButton(self.app._("Check for Updates"))
        self.btn_check_update.setFixedSize(140, 32)
        # Professional Blue Button style
        self.btn_check_update.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:pressed { background-color: #1e40af; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; }
        """)
        self.btn_check_update.clicked.connect(self.on_check_update_clicked)
        
        view_releases = QtWidgets.QLabel(f'<a href="https://github.com/gemkids275/WritingToolsV2/releases" style="color: #3b82f6; text-decoration: none;">{self.app._("View Releases")}</a>')
        view_releases.setOpenExternalLinks(True)
        
        btn_layout.addWidget(self.btn_check_update)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(view_releases)
        btn_layout.addStretch()
        updates_layout.addLayout(btn_layout)

        layout.addWidget(updates_card)
        layout.addStretch()
        
        # Wrap layout in a widget for QStackedWidget
        page_widget = QtWidgets.QWidget()
        page_widget.setLayout(layout)
        return page_widget

    def on_check_update_clicked(self):
        """Handle check for update button click."""
        self.btn_check_update.setEnabled(False)
        self.update_status.setText("Checking for updates...")
        
        def do_check():
            try:
                update_available = self.app.update_checker.check_updates()
                self.update_result_signal.emit(update_available)
            except Exception as e:
                logging.error(f"Error checking updates: {e}")
                self.update_result_signal.emit(False)

        threading.Thread(target=do_check, daemon=True).start()

    @Slot(bool)
    def handle_update_result(self, update_available):
        """Update UI based on check result."""
        if update_available:
            self.update_status.setText("A new version is available!")
            self.update_status.setStyleSheet("font-size: 12px; color: #10b981; font-weight: bold;")
        else:
            self.update_status.setText("You're up to date.")
            self.update_status.setStyleSheet("font-size: 12px; color: #888888;")
        self.btn_check_update.setEnabled(True)

    def save_settings(self):
        """Save the current settings from all pages."""
        # Conflict check: global hotkey vs command shortcuts
        new_shortcut = self.shortcut_input.text().strip()
        if new_shortcut:
            cmd_shortcuts = {
                c.id: c.keyboard_shortcut
                for c in self.app.command_manager.commands
                if c.keyboard_shortcut
            }
            result = check_conflict(new_shortcut, "", cmd_shortcuts)
            if result.has_conflict:
                cmd = self.app.command_manager.get_command(result.conflict_name)
                conflict_name = cmd.name if cmd else result.conflict_name
                QtWidgets.QMessageBox.warning(
                    self, "Shortcut Conflict",
                    f'"{new_shortcut}" is already used by command "{conflict_name}".\nPlease choose a different shortcut.'
                )
                return

        # 1. Update general config
        self.app.config['shortcut'] = new_shortcut or self.app.config.get('shortcut', 'ctrl+space')
        self.app.config['theme'] = 'gradient' if self.gradient_radio.isChecked() else 'plain'
        self.app.config['streaming'] = self.streaming_checkbox.isChecked()
        self.app.config['provider'] = self.provider_dropdown.currentText()
        
        # Update Language
        new_locale = self.language_dropdown.currentData()
        old_locale = self.app.config.get('locale', 'vi')
        self.app.config['locale'] = new_locale
        
        if self.autostart_checkbox:
            AutostartManager.set_autostart(self.autostart_checkbox.isChecked())
            
        # 2. Save current provider's specific config
        current_idx = self.provider_dropdown.currentIndex()
        if current_idx >= 0:
            self.app.providers[current_idx].save_config()
            
        # 3. Update active provider in App
        provider_name = self.app.config['provider']
        self.app.current_provider = next(
            (p for p in self.app.providers if p.provider_name == provider_name),
            self.app.providers[0]
        )
        self.app.current_provider.load_config(
            self.app.config.get("providers", {}).get(provider_name, {})
        )
        
        # 4. Refresh global state
        self.app.register_hotkey()
        self.app.save_config(self.app.config) # Save to config.json
        
        # Trigger language change if changed
        if new_locale != old_locale:
            self.app.change_language(new_locale)
            
        QtWidgets.QMessageBox.information(self, self.app._("Success"), self.app._("Settings saved successfully."))
        self.close()

    def closeEvent(self, event):
        if self.providers_only:
            self.close_signal.emit()
        super().closeEvent(event)


class ImportChoiceDialog(QtWidgets.QDialog):
    """
    Shown after a backup file is parsed.
    Lets the user choose between replacing all commands or selecting individual ones.
    """
    def __init__(self, parent, app, commands):
        super().__init__(parent)
        self.app = app
        self.commands = commands
        self.setWindowTitle("Restore Config")
        self.setMinimumWidth(520)
        self.setMinimumHeight(460)
        self._build_ui()

    def _build_ui(self):
        is_dark = colorMode == 'dark'
        bg   = '#252525' if is_dark else '#f9f9f9'
        fg   = '#ffffff' if is_dark else '#000000'
        muted = '#aaaaaa' if is_dark else '#666666'
        border = '#555' if is_dark else '#ccc'
        item_sep = '#444' if is_dark else '#eee'
        sel_bg = '#444' if is_dark else '#e8f5e9'

        self.setStyleSheet(f"background-color: {bg}; color: {fg};")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QtWidgets.QLabel("Restore Config")
        title.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {fg};")
        layout.addWidget(title)

        # Warning banner
        warn = QtWidgets.QLabel(
            f"⚠️  <b>Replace All</b> will remove <b>every</b> command currently installed "
            f"(including System commands) and replace them with the {len(self.commands)} "
            f"command(s) from this backup. <b>This cannot be undone.</b><br><br>"
            f"Use <b>Import Selected</b> to add only the commands you choose, "
            f"without removing anything."
        )
        warn.setWordWrap(True)
        warn.setTextFormat(QtCore.Qt.RichText)
        warn.setStyleSheet(
            f"font-size: 12px; color: {muted}; "
            f"background: {'#3a2a00' if is_dark else '#fff8e1'}; "
            f"border: 1px solid {'#665500' if is_dark else '#ffe082'}; "
            f"border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(warn)

        # Command list with checkboxes
        list_label = QtWidgets.QLabel("Commands in this backup:")
        list_label.setStyleSheet(f"font-size: 13px; color: {muted};")
        layout.addWidget(list_label)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {'#333' if is_dark else '#fff'};
                color: {fg};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 4px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 7px 10px;
                border-bottom: 1px solid {item_sep};
            }}
            QListWidget::item:selected {{
                background-color: {sel_bg};
            }}
        """)
        for cmd in self.commands:
            item = QtWidgets.QListWidgetItem(cmd.name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        # Select all / none
        sel_layout = QtWidgets.QHBoxLayout()
        btn_style_small = (
            f"QPushButton {{ background: transparent; color: #4CAF50; "
            f"border: none; font-size: 12px; padding: 2px 6px; }} "
            f"QPushButton:hover {{ text-decoration: underline; }}"
        )
        all_btn  = QtWidgets.QPushButton("Select All")
        none_btn = QtWidgets.QPushButton("Select None")
        all_btn.setStyleSheet(btn_style_small)
        none_btn.setStyleSheet(btn_style_small)
        all_btn.clicked.connect(lambda: self._set_all(QtCore.Qt.Checked))
        none_btn.clicked.connect(lambda: self._set_all(QtCore.Qt.Unchecked))
        sel_layout.addWidget(all_btn)
        sel_layout.addWidget(none_btn)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # Action buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: {'#444' if is_dark else '#eee'}; "
            f"color: {fg}; border: 1px solid {border}; border-radius: 5px; padding: 9px 18px; }}"
            f"QPushButton:hover {{ background-color: {'#555' if is_dark else '#ddd'}; }}"
        )
        cancel_btn.clicked.connect(self.reject)

        import_sel_btn = QtWidgets.QPushButton("Import Selected")
        import_sel_btn.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white; border: none; "
            "border-radius: 5px; padding: 9px 18px; font-weight: bold; } "
            "QPushButton:hover { background-color: #1b5e20; }"
        )
        import_sel_btn.clicked.connect(self._import_selected)

        replace_all_btn = QtWidgets.QPushButton("⚠ Replace All")
        replace_all_btn.setStyleSheet(
            "QPushButton { background-color: #b71c1c; color: white; border: none; "
            "border-radius: 5px; padding: 9px 18px; font-weight: bold; } "
            "QPushButton:hover { background-color: #7f0000; }"
        )
        replace_all_btn.clicked.connect(self._replace_all)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(import_sel_btn)
        btn_layout.addWidget(replace_all_btn)
        layout.addLayout(btn_layout)

    def _set_all(self, state):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def _checked_commands(self):
        return [
            self.commands[i]
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == QtCore.Qt.Checked
        ]

    def _import_selected(self):
        selected = self._checked_commands()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "Nothing Selected", "Please check at least one command to import.")
            return

        used_shortcuts = self.app.command_manager.get_used_shortcuts()
        added = 0
        for cmd in selected:
            existing = self.app.command_manager.get_command(cmd.id)
            if existing:
                cmd.id = str(uuid.uuid4())
                cmd.name = cmd.name + " (Imported)"

            if cmd.keyboard_shortcut and cmd.keyboard_shortcut in used_shortcuts:
                cmd.keyboard_shortcut = None
            elif cmd.keyboard_shortcut:
                used_shortcuts.add(cmd.keyboard_shortcut)

            self.app.command_manager.add_command(cmd)
            added += 1

        QtWidgets.QMessageBox.information(self, "Done", f"{added} command(s) imported.")
        self.accept()

    def _replace_all(self):
        confirm = QtWidgets.QMessageBox.warning(
            self,
            "Replace All Commands?",
            f"This will permanently remove ALL {len(self.app.command_manager.commands)} current command(s) "
            f"(including System commands) and replace them with "
            f"{len(self.commands)} command(s) from the backup.\n\n"
            f"This cannot be undone. Are you sure?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self.app.command_manager.replace_all_commands(self.commands)
        QtWidgets.QMessageBox.information(self, "Done", f"All commands replaced with {len(self.commands)} command(s) from backup.")
        self.accept()