import json
import os
import uuid
import logging
from typing import List, Optional
from models.command import Command
from models.secure_storage import save_command_api_key, get_command_api_key, delete_command_api_key

class CommandManager:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.commands_path = os.path.join(config_dir, "commands.json")
        self._commands: List[Command] = []
        self._deleted_built_in_ids: List[str] = []

    @property
    def commands(self) -> List[Command]:
        """Trả về tất cả lệnh (built-in chưa bị xóa + custom)."""
        return [c for c in self._commands if c.id not in self._deleted_built_in_ids]

    @property
    def custom_commands(self) -> List[Command]:
        return [c for c in self._commands if not c.is_built_in]

    def _get_default_commands(self) -> List[Command]:
        """Tạo danh sách các lệnh mặc định gốc."""
        defaults = [
            ("Proofread", "Check for spelling and grammatical errors and provide a corrected version.", "Proofread this:", "icons/spell-check"),
            ("Rewrite", "Rewrite the text to make it more clear and engaging while maintaining the original meaning.", "Rewrite this:", "icons/rewrite"),
            ("Friendly", "Rewrite the text to make it sound friendly and warm.", "Make this friendly:", "icons/smiley-face"),
            ("Professional", "Rewrite the text to make it sound professional and formal.", "Make this professional:", "icons/briefcase"),
            ("Concise", "Make the text more concise and direct.", "Make this concise:", "icons/shrink"),
            ("Summary", "Provide a brief summary of the text.", "Summarize this:", "icons/summary"),
            ("Key Points", "Identify and list the key points of the text.", "Extract key points:", "icons/keypoints"),
            ("Table", "Format the data or information in the text into a Markdown table.", "Format as table:", "icons/table")
        ]

        commands = []
        for name, prompt, prefix, icon in defaults:
            cmd_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
            commands.append(Command(
                id=cmd_id, name=name, prompt=prompt, prefix=prefix, icon=icon,
                use_response_window=True, is_built_in=True
            ))

        # Special command: system prompt used when no text is selected
        commands.append(Command(
            id="ChatNoSelection",
            name="Chat",
            prompt="You are a friendly, helpful, compassionate, and endearing AI conversational assistant. Avoid making assumptions or generating harmful, biased, or inappropriate content. When in doubt, do not make up information. Ask the user for clarification if needed. Try not be unnecessarily repetitive in your response. You can, and should as appropriate, use Markdown formatting to make your response nicely readable.",
            prefix="",
            icon="icons/custom",
            use_response_window=True,
            is_built_in=True,
            deletable=False,
        ))
        return commands

    def load(self):
        """Tải lệnh từ commands.json hoặc nạp mặc định nếu không tồn tại."""
        if not os.path.exists(self.commands_path):
            logging.info("commands.json not found. Initializing with defaults.")
            self._commands = self._get_default_commands()
            self.save()
            return

        try:
            with open(self.commands_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Tiền xử lý để tách API key nếu có trong JSON (dành cho import/migration)
                commands_data = data.get("commands", [])
                self._commands = []
                for d in commands_data:
                    api_key = d.pop("api_key", None)
                    cmd = Command.from_dict(d)
                    self._commands.append(cmd)
                    
                    # Nếu có api_key thật (không phải placeholder), lưu vào secure storage
                    if api_key and api_key != "YOUR_API_KEY_HERE":
                        self.save_command_api_key(cmd.id, api_key)
                
                self._deleted_built_in_ids = data.get("deleted_built_in_ids", [])
        except Exception as e:
            logging.error(f"Error loading commands.json: {e}")
            self._commands = self._get_default_commands()

    def save(self):
        """Lưu trạng thái hiện tại vào commands.json."""
        try:
            data = {
                "version": 1,
                "commands": [c.to_dict() for c in self._commands],
                "deleted_built_in_ids": self._deleted_built_in_ids
            }
            with open(self.commands_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving commands.json: {e}")

    # CRUD Operations
    def add_command(self, command: Command):
        self._commands.append(command)
        self.save()

    def update_command(self, updated_command: Command):
        for i, cmd in enumerate(self._commands):
            if cmd.id == updated_command.id:
                self._commands[i] = updated_command
                break
        self.save()

    def delete_command(self, command_id: str):
        command = next((c for c in self._commands if c.id == command_id), None)
        if not command or not command.deletable:
            return

        if command.is_built_in:
            if command_id not in self._deleted_built_in_ids:
                self._deleted_built_in_ids.append(command_id)
        else:
            self._commands = [c for c in self._commands if c.id != command_id]

        # Cleanup API key
        delete_command_api_key(command_id)
        self.save()

    def replace_all_commands(self, commands: List[Command]):
        """Replace every command (built-in + custom) with the given list."""
        self._commands = list(commands)
        self._deleted_built_in_ids = []
        self.save()

    def restore_built_ins(self):
        """Khôi phục toàn diện về trạng thái xuất xưởng."""
        self._commands = self._get_default_commands()
        self._deleted_built_in_ids = []
        self.save()

    def reorder_commands(self, new_id_order: list) -> None:
        """Sắp xếp lại _commands theo thứ tự ID mới từ UI."""
        index = {c.id: c for c in self._commands}
        reordered = [index[cid] for cid in new_id_order if cid in index]
        # Giữ lại các command không có trong new_id_order (nếu có) ở cuối
        seen = set(new_id_order)
        reordered += [c for c in self._commands if c.id not in seen]
        self._commands = reordered
        self.save()

    def get_by_name(self, name: str) -> Optional[Command]:
        return next((c for c in self.commands if c.name == name), None)

    def get_command(self, command_id: str) -> Optional[Command]:
        return next((c for c in self._commands if c.id == command_id), None)

    # Key Management Proxy
    def save_command_api_key(self, command_id: str, api_key: str):
        save_command_api_key(command_id, api_key)

    def get_command_api_key(self, command_id: str) -> str:
        return get_command_api_key(command_id)

    # Cross-platform provider key mapping (Windows full name ↔ macOS short key)
    _PROVIDER_KEY_TO_SHORT = {
        "Gemini (Recommended)":            "gemini",
        "Anthropic":                       "anthropic",
        "Mistral":                         "mistral",
        "OpenRouter":                      "openrouter",
        "OpenAI Compatible (For Experts)": "openai",
        "Ollama (For Experts)":            "ollama",
        "custom":                          "custom",
    }
    _PROVIDER_KEY_TO_FULL = {v: k for k, v in _PROVIDER_KEY_TO_SHORT.items()}

    # Export / Import Logic (Phase 7)
    def create_export_bundle(self, commands: List[Command]) -> dict:
        """Tạo gói dữ liệu để export (tương thích macOS)."""
        import time
        # Tách lệnh ChatNoSelection ra trường riêng cho giống macOS
        chat_cmd = next((c for c in commands if c.id == "ChatNoSelection"), None)
        other_cmds = [c for c in commands if c.id != "ChatNoSelection"]
        
        def _normalize(cmd_dict: dict) -> dict:
            raw = cmd_dict.get("providerOverride")
            if raw:
                cmd_dict["providerOverride"] = self._PROVIDER_KEY_TO_SHORT.get(raw, raw)
            return cmd_dict

        bundle = {
            "version": 1,
            "exportDate": time.time(),
            "appIdentifier": "AIShortcuts",
            "commands": [_normalize(c.to_dict()) for c in other_cmds],
        }
        
        if chat_cmd:
            bundle["customInstruction"] = chat_cmd.to_dict()
            
        return bundle

    def decode_import_bundle(self, data: str) -> List[Command]:
        """Giải mã gói dữ liệu import và trả về danh sách Command."""
        try:
            parsed = json.loads(data)
            # macOS dùng appIdentifier, Win cũ dùng app_identifier
            app_id = parsed.get("appIdentifier", parsed.get("app_identifier"))
            
            # Check if appIdentifier is valid or if it's a valid commands bundle
            if app_id not in ["WritingTools", "AIShortcuts"] and "commands" not in parsed:
                raise ValueError("This file is not a valid AI Shortcuts backup.")
            
            commands_data = parsed.get("commands", [])
            
            # Handle customInstruction (macOS-style Chat command)
            custom_inst = parsed.get("customInstruction")
            if custom_inst and isinstance(custom_inst, dict):
                custom_inst["id"] = "ChatNoSelection"
                commands_data.append(custom_inst)
            
            result = []
            for d in commands_data:
                if not isinstance(d, dict): continue
                d.pop("api_key", None)
                # Expand short provider key → Windows full name
                raw = d.get("providerOverride") or d.get("provider_override")
                if raw:
                    full = self._PROVIDER_KEY_TO_FULL.get(raw)
                    if full:
                        d["providerOverride"] = full
                cmd = Command.from_dict(d)
                # All imported commands are custom on the target platform,
                # regardless of is_built_in status on the source platform.
                cmd.is_built_in = False
                cmd.deletable = True

                # Icon fallback: macOS SF Symbol names won't exist on Windows
                if cmd.icon:
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    full_icon_path = os.path.join(base_dir, f"{cmd.icon}_light.png")
                    if not os.path.exists(full_icon_path):
                        cmd.icon = ""

                result.append(cmd)
            return result
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format.")
        except Exception as e:
            raise ValueError(str(e))

    def get_used_shortcuts(self) -> set:
        """Trả về tập hợp các phím tắt đang được sử dụng."""
        return {c.keyboard_shortcut for c in self.commands if c.keyboard_shortcut}
