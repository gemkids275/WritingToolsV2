# Phase 7: Export / Import Config (Windows & Linux)

## Goal

Implement export and import functionality for commands and full config on the Windows/Linux platform, mirroring the macOS feature. Users can back up their commands (including shortcuts, AI overrides) and share individual commands as JSON files.

---

## Current State

### Already in place
- `Command.to_dict()` — serializes all fields including `keyboard_shortcut`, `provider_override`, `model_override`, etc.
- `Command.from_dict()` — deserializes all fields including `keyboard_shortcut`
- `CommandManager` — handles CRUD, secure API key storage, save/load from `commands.json`
- `CommandsManagerDialog` — has share icon button and "Import Command" button (UI exists, no logic)
- `SettingsWindow` — has "Export All Config" and "Import Full Config" buttons (UI exists, no logic)

### Missing
- Export/import logic methods in `CommandManager`
- Wiring of existing buttons in `CommandsManagerDialog` and `SettingsWindow`
- Shortcut conflict detection on import

---

## JSON Export Format

```json
{
  "version": 1,
  "export_date": "2026-04-19T12:00:00",
  "app_identifier": "WritingTools",
  "commands": [
    {
      "id": "uuid-...",
      "name": "Dịch VN",
      "prompt": "Translate to Vietnamese...",
      "prefix": "",
      "icon": "icons/globe",
      "use_response_window": true,
      "is_built_in": false,
      "deletable": true,
      "keyboard_shortcut": "ctrl+shift+v",
      "provider_override": null,
      "model_override": null,
      "custom_provider_base_url": null,
      "custom_provider_model": null
    }
  ]
}
```

**Rules:**
- `api_key` is NEVER included in export (stripped before serializing)
- `app_identifier` must equal `"WritingTools"` — used to validate on import
- `keyboard_shortcut` is included and restored on import (with conflict handling)
- Built-in commands ARE included in full config export, excluded from single command export

---

## Files to Modify

| File | Changes |
|---|---|
| `Windows_and_Linux/models/command_manager.py` | Add 3 new methods |
| `Windows_and_Linux/ui/CommandsManagerDialog.py` | Wire export/import single command buttons |
| `Windows_and_Linux/ui/SettingsWindow.py` | Wire Export All Config / Import Full Config buttons |

**No new files. No changes to `commands.json` format.**

---

## Step 1 — Add methods to `CommandManager`

File: `Windows_and_Linux/models/command_manager.py`

### 1a. `create_export_bundle(commands: List[Command]) -> dict`

```python
def create_export_bundle(self, commands: List[Command]) -> dict:
    from datetime import datetime, timezone
    return {
        "version": 1,
        "export_date": datetime.now(timezone.utc).isoformat(),
        "app_identifier": "WritingTools",
        "commands": [c.to_dict() for c in commands],  # no api_key placeholder
    }
```

- Caller decides which commands to pass (all vs single)
- `to_dict()` does NOT include `api_key` by default — safe as-is

### 1b. `decode_import_bundle(data: bytes | str) -> list[Command]`

```python
def decode_import_bundle(self, data: bytes | str) -> list[Command]:
    import json
    parsed = json.loads(data)
    if parsed.get("app_identifier") != "WritingTools":
        raise ValueError("Invalid file: not a WritingTools config backup.")
    commands_data = parsed.get("commands", [])
    result = []
    for d in commands_data:
        d.pop("api_key", None)  # strip placeholder if present
        result.append(Command.from_dict(d))
    return result
```

### 1c. `get_used_shortcuts() -> set[str]`

```python
def get_used_shortcuts(self) -> set[str]:
    return {c.keyboard_shortcut for c in self.commands if c.keyboard_shortcut}
```

Helper used during import to detect shortcut conflicts.

---

## Step 2 — Wire buttons in `CommandsManagerDialog`

File: `Windows_and_Linux/ui/CommandsManagerDialog.py`

### Export single command (share icon button)

```python
def _export_command(self, command: Command):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import json

    path, _ = QFileDialog.getSaveFileName(
        self,
        self.tr("Export Command"),
        f"{command.name}.json",
        self.tr("JSON Files (*.json)")
    )
    if not path:
        return

    bundle = self.command_manager.create_export_bundle([command])
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, self.tr("Success"), self.tr("Command exported successfully."))
    except Exception as e:
        QMessageBox.critical(self, self.tr("Error"), str(e))
```

### Import single command ("Import Command" button)

```python
def _import_command(self):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import json

    path, _ = QFileDialog.getOpenFileName(
        self,
        self.tr("Import Command"),
        "",
        self.tr("JSON Files (*.json)")
    )
    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        commands = self.command_manager.decode_import_bundle(data)
    except Exception as e:
        QMessageBox.critical(self, self.tr("Error"), self.tr("Invalid file: {0}").format(str(e)))
        return

    used_shortcuts = self.command_manager.get_used_shortcuts()
    added = 0

    for cmd in commands:
        # ID conflict: if ID already exists and not built-in, assign new UUID
        existing = self.command_manager.get_command(cmd.id)
        if existing:
            if not existing.is_built_in:
                cmd.id = str(uuid.uuid4())
                cmd.name = cmd.name + self.tr(" (Imported)")
            else:
                # Skip built-in with same ID
                continue

        # Shortcut conflict: clear shortcut if already used
        if cmd.keyboard_shortcut and cmd.keyboard_shortcut in used_shortcuts:
            cmd.keyboard_shortcut = None

        cmd.is_built_in = False
        self.command_manager.add_command(cmd)
        added += 1

    self._reload_list()
    QMessageBox.information(
        self,
        self.tr("Import Complete"),
        self.tr("{0} command(s) imported.").format(added)
    )
```

---

## Step 3 — Wire buttons in `SettingsWindow`

File: `Windows_and_Linux/ui/SettingsWindow.py`

### Export All Config

```python
def _export_all_config(self):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import json

    path, _ = QFileDialog.getSaveFileName(
        self,
        self.tr("Export All Config"),
        "WritingTools_Backup.json",
        self.tr("JSON Files (*.json)")
    )
    if not path:
        return

    all_commands = self.app.command_manager.commands
    bundle = self.app.command_manager.create_export_bundle(all_commands)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, self.tr("Success"), self.tr("Config exported successfully."))
    except Exception as e:
        QMessageBox.critical(self, self.tr("Error"), str(e))
```

### Import Full Config

```python
def _import_full_config(self):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import json

    path, _ = QFileDialog.getOpenFileName(
        self,
        self.tr("Import Config"),
        "",
        self.tr("JSON Files (*.json)")
    )
    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        commands = self.app.command_manager.decode_import_bundle(data)
    except Exception as e:
        QMessageBox.critical(self, self.tr("Error"), self.tr("Invalid file: {0}").format(str(e)))
        return

    confirm = QMessageBox.question(
        self,
        self.tr("Replace All Commands?"),
        self.tr("This will replace all your current custom commands. Built-in commands will not be affected. Continue?"),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    # Remove all existing custom commands
    for cmd in list(self.app.command_manager.custom_commands):
        self.app.command_manager.delete_command(cmd.id)

    used_shortcuts = self.app.command_manager.get_used_shortcuts()

    for cmd in commands:
        if cmd.is_built_in:
            continue  # skip built-ins from backup, keep local ones

        # Shortcut conflict
        if cmd.keyboard_shortcut and cmd.keyboard_shortcut in used_shortcuts:
            cmd.keyboard_shortcut = None
        else:
            if cmd.keyboard_shortcut:
                used_shortcuts.add(cmd.keyboard_shortcut)

        cmd.is_built_in = False
        self.app.command_manager.add_command(cmd)

    # Notify popup window to reload command buttons
    if hasattr(self.app, 'popup_window') and self.app.popup_window:
        self.app.popup_window.reload_commands()

    QMessageBox.information(self, self.tr("Success"), self.tr("Config imported successfully."))
```

---

## Shortcut Conflict Handling Rules

| Scenario | Action |
|---|---|
| Imported command has shortcut not used by anyone | Restore shortcut as-is |
| Imported command has shortcut already used by existing command | Clear shortcut (set to `None`), silently |
| Full import: multiple imported commands conflict with each other | First one wins, rest get `None` |

No warning dialogs for shortcut conflicts — silent clear is consistent with macOS behavior.

---

## Checklist for Agent

- [ ] Add `create_export_bundle()` to `CommandManager`
- [ ] Add `decode_import_bundle()` to `CommandManager`
- [ ] Add `get_used_shortcuts()` to `CommandManager`
- [ ] Wire share icon button → `_export_command()` in `CommandsManagerDialog`
- [ ] Wire "Import Command" button → `_import_command()` in `CommandsManagerDialog`
- [ ] Wire "Export All Config" button → `_export_all_config()` in `SettingsWindow`
- [ ] Wire "Import Full Config" button → `_import_full_config()` in `SettingsWindow`
- [ ] Test: export single command → import on fresh install
- [ ] Test: export all → import replaces custom commands only
- [ ] Test: import file with shortcut conflict → shortcut cleared silently
- [ ] Test: import invalid JSON → error dialog shown
