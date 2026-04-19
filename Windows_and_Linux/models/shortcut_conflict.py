from dataclasses import dataclass


@dataclass
class ConflictResult:
    has_conflict: bool
    conflict_type: str   # "app_hotkey" | "command" | "none"
    conflict_name: str   # display name của thứ bị conflict


def normalize(shortcut: str) -> str:
    return shortcut.lower().replace(" ", "")


def check_conflict(
    shortcut: str,
    app_hotkey: str,
    command_shortcuts: dict,        # {command_id: shortcut_str}
    exclude_command_id: str | None = None,
) -> ConflictResult:
    if not shortcut:
        return ConflictResult(False, "none", "")

    n = normalize(shortcut)

    if app_hotkey and n == normalize(app_hotkey):
        return ConflictResult(True, "app_hotkey", "App Hotkey")

    for cmd_id, cmd_shortcut in command_shortcuts.items():
        if cmd_id == exclude_command_id:
            continue
        if cmd_shortcut and n == normalize(cmd_shortcut):
            return ConflictResult(True, "command", cmd_id)

    return ConflictResult(False, "none", "")
