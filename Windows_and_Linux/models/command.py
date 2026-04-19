from dataclasses import dataclass, field
import uuid

@dataclass
class Command:
    name: str
    prompt: str          # system instruction for AI
    prefix: str          # prefix added before user text (e.g., "Proofread this:\n\n")
    icon: str            # icon name or emoji
    use_response_window: bool = False
    is_built_in: bool = False
    deletable: bool = True
    keyboard_shortcut: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # AI Override fields (Phase 6)
    provider_override: str | None = None           # e.g., "Gemini (Recommended)", or "custom"
    model_override: str | None = None              # specific model name
    custom_provider_base_url: str | None = None    # used only when provider_override == "custom"
    custom_provider_model: str | None = None       # used only when provider_override == "custom"
    
    # Sync with macOS (Phase 7)
    preserve_formatting: bool = False

    def _clean_icon_for_export(self) -> str:
        """Process icon to a concise format for macOS compatibility."""
        if not self.icon: return ""
        if self.icon.startswith("icons/"):
            return self.icon[6:]
        return self.icon

    def to_dict(self, include_key_placeholder: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "prefix": self.prefix,
            "icon": self._clean_icon_for_export(),
            "useResponseWindow": self.use_response_window,
            "isBuiltIn": self.is_built_in,
            "deletable": self.deletable,
            "keyboard_shortcut": self.keyboard_shortcut,
            "hasShortcut": bool(self.keyboard_shortcut),
            "providerOverride": self.provider_override,
            "modelOverride": self.model_override,
            "customProviderBaseUrl": self.custom_provider_base_url,
            "customProviderModel": self.custom_provider_model,
            "preserveFormatting": self.preserve_formatting
        }
        if include_key_placeholder:
            d["api_key"] = "YOUR_API_KEY_HERE"
        return d

    @staticmethod
    def _resolve_icon_for_import(icon: str) -> str:
        """Verify icon name and assign 'icons/' path if it looks like a local icon."""
        if not icon: return ""
        # If icons/ prefix already exists, keep it
        if icon.startswith("icons/"):
            return icon
        
        # Real existence check is done in the manager. 
        # Here we just restore the conventional path prefix.
        return f"icons/{icon}"

    @staticmethod
    def from_dict(d: dict) -> "Command":
        # Support both snake_case (legacy Windows) and camelCase (macOS/New Windows)
        return Command(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", ""),
            prompt=d.get("prompt", d.get("instruction", "")),
            prefix=d.get("prefix", ""),
            icon=Command._resolve_icon_for_import(d.get("icon", "")),
            use_response_window=d.get("useResponseWindow", d.get("use_response_window", d.get("open_in_window", False))),
            is_built_in=d.get("isBuiltIn", d.get("is_built_in", False)),
            deletable=d.get("deletable", True),
            keyboard_shortcut=d.get("keyboard_shortcut") or None,
            provider_override=d.get("providerOverride", d.get("provider_override")),
            model_override=d.get("modelOverride", d.get("model_override")),
            custom_provider_base_url=d.get("customProviderBaseUrl", d.get("custom_provider_base_url")),
            custom_provider_model=d.get("customProviderModel", d.get("custom_provider_model")),
            preserve_formatting=d.get("preserveFormatting", d.get("preserve_formatting", False))
        )
