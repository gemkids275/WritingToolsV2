"""
AI Provider Architecture for Writing Tools
--------------------------------------------

This module handles different AI model providers (Gemini, OpenAI-compatible, Ollama) and manages their interactions
with the main application. It uses an abstract base class pattern for provider implementations.

Key Components:
1. AIProviderSetting – Base class for provider settings (e.g. API keys, model names)
    • TextSetting      – A simple text input for settings
    • DropdownSetting  – A dropdown selection setting

2. AIProvider – Abstract base class that all providers implement.
   It defines the interface for:
      • Getting a response from the AI model
      • Loading and saving configuration settings
      • Cancelling an ongoing request

3. Provider Implementations:
    • GeminiProvider – Uses Google’s Generative AI API (Gemini) to generate content.
    • OpenAICompatibleProvider – Connects to any OpenAI-compatible API (v1/chat/completions)
    • OllamaProvider – Connects to a locally running Ollama server (e.g. for llama.cpp)

Response Flow:
   • The main app calls get_response() with a system instruction and a prompt.
   • The provider formats and sends the request to its API endpoint.
   • For operations that require a window (e.g. Summary, Key Points), the provider returns the full text.
   • For direct text replacement, the provider emits the full text via the output_ready_signal.
   • Conversation history (for follow-up questions) is maintained by the main app.

Note: Streaming has been fully removed throughout the code.
"""

import base64
import logging
import webbrowser
from abc import ABC, abstractmethod
from typing import List

# External libraries
import anthropic
from mistralai.client import Mistral
from google import genai
from google.genai import types as genai_types
from ollama import Client as OllamaClient
from openai import OpenAI
from PySide6 import QtWidgets
from PySide6.QtWidgets import QVBoxLayout
from ui.UIUtils import colorMode

_ = lambda x: x  # Will be overridden by WritingToolApp

# Obfuscation prefix to identify encrypted API keys
_OBFUSCATION_PREFIX = "enc:"
_XOR_KEY = 0x5A  # Simple XOR key for obfuscation


def obfuscate_api_key(key: str) -> str:
    """
    Obfuscate an API key using XOR + Base64 encoding.
    Returns the obfuscated string with 'enc:' prefix.
    """
    if not key or key.startswith(_OBFUSCATION_PREFIX):
        return key  # Already obfuscated or empty
    xored = bytes([b ^ _XOR_KEY for b in key.encode('utf-8')])
    return _OBFUSCATION_PREFIX + base64.b64encode(xored).decode('ascii')


def deobfuscate_api_key(obfuscated: str) -> str:
    """
    Deobfuscate an API key that was obfuscated with obfuscate_api_key().
    If the key doesn't have the 'enc:' prefix, returns it as-is (plaintext).
    """
    if not obfuscated or not obfuscated.startswith(_OBFUSCATION_PREFIX):
        return obfuscated  # Not obfuscated, return as-is
    encoded = obfuscated[len(_OBFUSCATION_PREFIX):]
    xored = base64.b64decode(encoded)
    return bytes([b ^ _XOR_KEY for b in xored]).decode('utf-8')


class AIProviderSetting(ABC):
    """
    Abstract base class for a provider setting (e.g., API key, model selection).
    """
    def __init__(self, name: str, display_name: str = None, default_value: str = None, description: str = None):
        self.name = name
        self.display_name = display_name if display_name else name
        self.default_value = default_value if default_value else ""
        self.description = description if description else ""

    @abstractmethod
    def render_to_layout(self, layout: QVBoxLayout):
        """Render the setting widget(s) into the provided layout."""
        pass

    @abstractmethod
    def set_value(self, value):
        """Set the internal value from configuration."""
        pass

    @abstractmethod
    def get_value(self):
        """Return the current value from the widget."""
        pass


class TextSetting(AIProviderSetting):
    """
    A text-based setting (for API keys, URLs, etc.).
    """
    def __init__(self, name: str, display_name: str = None, default_value: str = None, description: str = None):
        super().__init__(name, display_name, default_value, description)
        self.internal_value = default_value
        self.input = None

    def render_to_layout(self, layout: QVBoxLayout):
        row_layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(self.display_name)
        label.setStyleSheet(f"font-size: 16px; color: {'#ffffff' if colorMode=='dark' else '#333333'};")
        row_layout.addWidget(label)
        self.input = QtWidgets.QLineEdit(self.internal_value or "")
        self.input.setStyleSheet(f"""
            font-size: 16px;
            padding: 5px;
            background-color: {'#444' if colorMode=='dark' else 'white'};
            color: {'#ffffff' if colorMode=='dark' else '#000000'};
            border: 1px solid {'#666' if colorMode=='dark' else '#ccc'};
        """)
        self.input.setPlaceholderText(self.description)
        if self.name == "api_key":
            self.input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            toggle_btn = QtWidgets.QPushButton(_("Show"))
            toggle_btn.setFixedWidth(52)
            toggle_btn.setStyleSheet(
                f"QPushButton {{ font-size: 13px; padding: 5px 6px; "
                f"background-color: {'#555' if colorMode=='dark' else '#e0e0e0'}; "
                f"color: {'#fff' if colorMode=='dark' else '#333'}; "
                f"border: 1px solid {'#666' if colorMode=='dark' else '#ccc'}; border-radius: 4px; }} "
                f"QPushButton:hover {{ background-color: {'#666' if colorMode=='dark' else '#d0d0d0'}; }}"
            )
            def _toggle(_checked=False, inp=self.input, btn=toggle_btn):
                if inp.echoMode() == QtWidgets.QLineEdit.EchoMode.Password:
                    inp.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
                    btn.setText(_("Hide"))
                else:
                    inp.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
                    btn.setText(_("Show"))
            toggle_btn.clicked.connect(_toggle)
            row_layout.addWidget(self.input)
            row_layout.addWidget(toggle_btn)
        else:
            row_layout.addWidget(self.input)
        layout.addLayout(row_layout)

    def set_value(self, value):
        self.internal_value = value

    def get_value(self):
        return self.input.text()


class DropdownSetting(AIProviderSetting):
    """
    A dropdown setting (e.g., for selecting a model).

    Optionally supports a "Custom" option that reveals a text input for arbitrary values.
    When allow_custom=True, users can select "Custom" from the dropdown and enter any value.
    If the loaded config value doesn't match any preset option, "Custom" is auto-selected.
    """
    # Sentinel value used internally to identify the "Custom" dropdown option
    _CUSTOM_SENTINEL = "__custom__"

    def __init__(self, name: str, display_name: str = None, default_value: str = None,
                 description: str = None, options: list = None, allow_custom: bool = False,
                 custom_placeholder: str = "Enter custom value"):
        super().__init__(name, display_name, default_value, description)
        self.options = options if options else []
        self.internal_value = default_value
        self.dropdown = None
        self.allow_custom = allow_custom
        self.custom_placeholder = custom_placeholder
        self.custom_input = None
        self.custom_input_container = None

    def render_to_layout(self, layout: QVBoxLayout):
        row_layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(_(self.display_name))
        label.setStyleSheet(f"font-size: 16px; color: {'#ffffff' if colorMode=='dark' else '#333333'};")
        row_layout.addWidget(label)
        self.dropdown = QtWidgets.QComboBox()
        self.dropdown.setStyleSheet(f"""
            font-size: 16px;
            padding: 5px;
            background-color: {'#444' if colorMode=='dark' else 'white'};
            color: {'#ffffff' if colorMode=='dark' else '#000000'};
            border: 1px solid {'#666' if colorMode=='dark' else '#ccc'};
        """)

        # Add preset options
        for option, value in self.options:
            self.dropdown.addItem(_(option), value)

        # Add "Custom" option if enabled
        if self.allow_custom:
            self.dropdown.addItem(_("🔧 Custom"), self._CUSTOM_SENTINEL)

        # Set initial selection based on internal_value
        index = self.dropdown.findData(self.internal_value)
        if index != -1:
            # Value matches a preset option
            self.dropdown.setCurrentIndex(index)
        elif self.allow_custom and self.internal_value:
            # Value doesn't match any preset - it's a custom value, select "Custom"
            custom_index = self.dropdown.findData(self._CUSTOM_SENTINEL)
            if custom_index != -1:
                self.dropdown.setCurrentIndex(custom_index)

        row_layout.addWidget(self.dropdown)
        layout.addLayout(row_layout)

        # Create custom input row if allow_custom is enabled
        if self.allow_custom:
            self.custom_input_container = QtWidgets.QWidget()
            custom_row_layout = QtWidgets.QHBoxLayout(self.custom_input_container)
            custom_row_layout.setContentsMargins(0, 5, 0, 0)

            self.custom_input = QtWidgets.QLineEdit()
            self.custom_input.setPlaceholderText(self.custom_placeholder)
            self.custom_input.setStyleSheet(f"""
                font-size: 16px;
                padding: 5px;
                background-color: {'#444' if colorMode=='dark' else 'white'};
                color: {'#ffffff' if colorMode=='dark' else '#000000'};
                border: 1px solid {'#666' if colorMode=='dark' else '#ccc'};
            """)

            # If current value is custom (not in presets), populate the input
            if self.dropdown.currentData() == self._CUSTOM_SENTINEL and self.internal_value:
                self.custom_input.setText(self.internal_value)

            custom_row_layout.addWidget(self.custom_input)
            layout.addWidget(self.custom_input_container)

            # Connect signal to show/hide custom input when dropdown changes
            self.dropdown.currentIndexChanged.connect(self._on_dropdown_changed)
            # Set initial visibility
            self._update_custom_input_visibility()

    def _on_dropdown_changed(self):
        """Handle dropdown selection change to show/hide custom input."""
        self._update_custom_input_visibility()

    def _update_custom_input_visibility(self):
        """Show or hide the custom input based on dropdown selection."""
        if self.custom_input_container:
            is_custom = self.dropdown.currentData() == self._CUSTOM_SENTINEL
            self.custom_input_container.setVisible(is_custom)
            # Focus the input when switching to Custom for better UX
            if is_custom and self.custom_input:
                self.custom_input.setFocus()

    def set_value(self, value):
        self.internal_value = value

    def get_value(self):
        # If "Custom" is selected, return the text input value (stripped of whitespace)
        if self.allow_custom and self.dropdown.currentData() == self._CUSTOM_SENTINEL:
            return self.custom_input.text().strip()
        return self.dropdown.currentData()


class AIProvider(ABC):
    """
    Abstract base class for AI providers.
    
    All providers must implement:
      • get_response(system_instruction, prompt) -> str
      • after_load() to create their client or model instance
      • before_load() to cleanup any existing client
      • cancel() to cancel an ongoing request
    """
    def __init__(self, app, provider_name: str, settings: List[AIProviderSetting],
                 description: str = "An unfinished AI provider!",
                 logo: str = "generic",
                 button_text: str = "Go to URL",
                 button_action: callable = None):
        self.provider_name = provider_name
        self.settings = settings
        self.app = app
        self.description = description if description else "An unfinished AI provider!"
        self.logo = logo
        self.button_text = button_text
        self.button_action = button_action

    @abstractmethod
    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        """
        Send the given system instruction and prompt to the AI provider and return the full response text.
        """
        pass

    @abstractmethod
    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        """
        Generator that yields chunks of response text from the AI provider.
        """
        pass

    def load_config(self, config: dict):
        """
        Load configuration settings into the provider.
        """
        for setting in self.settings:
            if setting.name in config:
                setattr(self, setting.name, config[setting.name])
                setting.set_value(config[setting.name])
            else:
                setattr(self, setting.name, setting.default_value)
        self.after_load()

    def save_config(self):
        """
        Save provider configuration settings into the main config file.
        """
        config = {}
        for setting in self.settings:
            config[setting.name] = setting.get_value()
        self.app.config["providers"][self.provider_name] = config
        self.app.save_config(self.app.config)

    @abstractmethod
    def after_load(self):
        """
        Called after configuration is loaded; create your API client here.
        """
        pass

    @abstractmethod
    def before_load(self):
        """
        Called before reloading configuration; cleanup your API client here.
        """
        pass

    def _require_client(self):
        if not getattr(self, 'client', None):
            raise RuntimeError(
                _("{0} API key is not configured. Please set your API key in Settings → AI Providers.").format(self.provider_name)
            )

    @abstractmethod
    def cancel(self):
        """
        Cancel any ongoing API request.
        """
        pass


class AnthropicProvider(AIProvider):
    """
    Provider for Anthropic's Claude API.
    """
    def __init__(self, app):
        self.close_requested = False
        self.client = None
        settings = [
            TextSetting(name="api_key", display_name="API Key", description="Paste your Anthropic API key here"),
            DropdownSetting(
                name="model_name",
                display_name="Model",
                default_value="claude-3-5-sonnet-latest",
                description="Select Claude model to use",
                options=[
                    ("Claude 3.5 Sonnet", "claude-3-5-sonnet-latest"),
                    ("Claude 3.5 Haiku", "claude-3-5-haiku-latest"),
                    ("Claude 3 Opus", "claude-3-opus-latest"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., claude-3-sonnet-20240229"
            )
        ]
        super().__init__(app, "Anthropic", settings,
            _("• Anthropic's Claude is renowned for high-quality writing, safe reasoning, and large context windows.\n"
              "• Ideal for complex analysis and creative writing tasks.\n"
              "• Supports Claude 3.5 Sonnet, Haiku, and Opus models."),
            "anthropic",
            _("Get API Key"),
            lambda: webbrowser.open("https://console.anthropic.com/settings/keys"))

    def before_load(self):
        self.client = None

    def after_load(self):
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def before_load(self):
        self.client = None

    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        self._require_client()
        self.close_requested = False
        content = []
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64
                    }
                })
        content.append({"type": "text", "text": prompt})

        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            system=system_instruction,
            messages=[{"role": "user", "content": content}]
        )
        response_text = response.content[0].text
        if not return_response and not hasattr(self.app, 'current_response_window'):
            self.app.output_ready_signal.emit(response_text)
            return ""
        return response_text

    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        self.close_requested = False
        content = []
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64
                    }
                })
        content.append({"type": "text", "text": prompt})

        self._require_client()
        with self.client.messages.stream(
            model=self.model_name,
            max_tokens=4096,
            system=system_instruction,
            messages=[{"role": "user", "content": content}]
        ) as stream:
            for text in stream.text_stream:
                if self.close_requested:
                    break
                yield text

    def cancel(self):
        self.close_requested = True


class MistralProvider(AIProvider):
    """
    Provider for Mistral AI API.
    """
    def __init__(self, app):
        self.close_requested = False
        self.client = None
        settings = [
            TextSetting(name="api_key", display_name="API Key", description="Paste your Mistral API key here"),
            DropdownSetting(
                name="model_name",
                display_name="Model",
                default_value="mistral-large-latest",
                options=[
                    ("Mistral Large", "mistral-large-latest"),
                    ("Mistral Small", "mistral-small-latest"),
                    ("Pixtral 12B (Vision)", "pixtral-12b-2409"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., mistral-medium-latest"
            )
        ]
        super().__init__(app, "Mistral", settings,
            _("• Mistral AI offers state-of-the-art open models with high efficiency.\n"
              "• Great performance in both European languages and coding.\n"
              "• Supports Mistral Large, Small, and vision-capable Pixtral."),
            "mistral",
            _("Get API Key"),
            lambda: webbrowser.open("https://console.mistral.ai/api-keys/"))

    def before_load(self):
        self.client = None

    def after_load(self):
        if self.api_key:
            self.client = Mistral(api_key=self.api_key)

    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        self._require_client()
        self.close_requested = False
        messages = [{"role": "system", "content": system_instruction}]
        
        content = [{"type": "text", "text": prompt}]
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": f"data:{mime_type};base64,{b64}"
                })
        messages.append({"role": "user", "content": content})

        response = self.client.chat.complete(
            model=self.model_name,
            messages=messages
        )
        response_text = response.choices[0].message.content
        if not return_response and not hasattr(self.app, 'current_response_window'):
            self.app.output_ready_signal.emit(response_text)
            return ""
        return response_text

    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        self._require_client()
        self.close_requested = False
        messages = [{"role": "system", "content": system_instruction}]
        content = [{"type": "text", "text": prompt}]
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": f"data:{mime_type};base64,{b64}"
                })
        messages.append({"role": "user", "content": content})

        stream = self.client.chat.stream(
            model=self.model_name,
            messages=messages
        )
        for chunk in stream:
            if self.close_requested:
                break
            if chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content

    def cancel(self):
        self.close_requested = True


class OpenRouterProvider(AIProvider):
    """
    Provider for OpenRouter (OpenAI-compatible but with specific headers).
    """
    def __init__(self, app):
        self.close_requested = False
        self.client = None
        settings = [
            TextSetting(name="api_key", display_name="API Key", description="Paste your OpenRouter API key here"),
            DropdownSetting(
                name="model_name",
                display_name="Model",
                default_value="anthropic/claude-3.5-sonnet",
                options=[
                    ("Claude 3.5 Sonnet", "anthropic/claude-3.5-sonnet"),
                    ("GPT-4o", "openai/gpt-4o"),
                    ("DeepSeek V3", "deepseek/deepseek-chat"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., google/gemini-pro-1.5"
            )
        ]
        super().__init__(app, "OpenRouter", settings,
            _("• OpenRouter provides unified access to over 100+ AI models (Claude, Llama, GPT, etc.).\n"
              "• Offers the most competitive pricing and many free-tier models.\n"
              "• Best for power users who want to switch models frequently."),
            "openrouter",
            _("Get API Key"),
            lambda: webbrowser.open("https://openrouter.ai/keys"))

    def before_load(self):
        self.client = None

    def after_load(self):
        if self.api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/gemkids275/WritingToolsV2",
                    "X-Title": "Writing Tools V2",
                }
            )

    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        self._require_client()
        self.close_requested = False
        content = [{"type": "text", "text": prompt}]
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"}
                })
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": content}
            ]
        )
        response_text = response.choices[0].message.content
        if not return_response and not hasattr(self.app, 'current_response_window'):
            self.app.output_ready_signal.emit(response_text)
            return ""
        return response_text

    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        self._require_client()
        self.close_requested = False
        content = [{"type": "text", "text": prompt}]
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"}
                })

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": content}
            ],
            stream=True
        )
        for chunk in stream:
            if self.close_requested:
                break
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def cancel(self):
        self.close_requested = True


class GeminiProvider(AIProvider):
    """
    Provider for Google's Gemini API.
    
    Uses google.generativeai.GenerativeModel.generate_content() to generate text.
    Streaming is no longer offered so we always do a single-shot call.
    """
    def __init__(self, app):
        self.close_requested = False
        self.client = None

        settings = [
            TextSetting(name="api_key", display_name="API Key", description="Paste your Gemini API key here"),
            DropdownSetting(
                name="model_name",
                display_name="Model",
                default_value="gemma-3-27b-it",
                description="Select Gemini model to use",
                options=[
                    ("⭐ Gemma 3 27B (very intelligent | unlimited usage)", "gemma-3-27b-it"),
                    ("Gemma 3 4B (intelligent | unlimited usage)", "gemma-3-4b-it"),
                    ("Gemini Flash Latest (very intelligent | only 20 uses/day)", "gemini-flash-latest"),
                    ("Gemini Flash Lite Latest (intelligent | only 20 uses/day)", "gemini-flash-lite-latest"),
                ],
                allow_custom=True,
                custom_placeholder="e.g., gemini-3-pro-preview"
            )
        ]
        super().__init__(app, "Gemini (Recommended)", settings,
            _("• Google’s Gemini 1.5 & 2.0 (Gemma) are multimodal models with world-class performance.\n"
              "• Offers extremely fast inference and massive context windows (up to 1M+ tokens).\n"
              "• Get a free API key to start using Gemini Flash and Pro models."),
            "gemini",
            _("Get API Key"),
            lambda: webbrowser.open("https://aistudio.google.com/app/apikey"))

    def _build_config(self, system_instruction: str) -> genai_types.GenerateContentConfig:
        return genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=1000,
            temperature=0.5,
            safety_settings=[
                genai_types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                genai_types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                genai_types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                genai_types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
            ]
        )

    def _build_contents(self, prompt: str, images: list = None) -> list:
        parts = []
        if images:
            for mime_type, b64 in images:
                parts.append(genai_types.Part.from_bytes(
                    data=base64.b64decode(b64),
                    mime_type=mime_type
                ))
        parts.append(genai_types.Part.from_text(text=prompt))
        return parts



    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        self.close_requested = False
        try:
            self._require_client()
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=self._build_contents(prompt, images),
                config=self._build_config(system_instruction)
            )
            response_text = response.text.rstrip('\n')
            if not return_response and not hasattr(self.app, 'current_response_window'):
                self.app.output_ready_signal.emit(response_text)
                return ""
            return response_text
        except Exception as e:
            logging.error(f"Error processing Gemini response: {e}")
            error_msg = str(e)
            if not return_response:
                self.app.output_ready_signal.emit(error_msg)
            return error_msg
        finally:
            self.close_requested = False
        return ""

    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        self._require_client()
        self.close_requested = False
        for chunk in self.client.models.generate_content_stream(
            model=self.model_name,
            contents=self._build_contents(prompt, images),
            config=self._build_config(system_instruction)
        ):
            if self.close_requested:
                break
            if chunk.text:
                yield chunk.text

    def cancel(self):
        self.close_requested = True

    def load_config(self, config: dict):
        if 'api_key' in config:
            config = config.copy()
            config['api_key'] = deobfuscate_api_key(config['api_key'])
        super().load_config(config)

    def save_config(self):
        config = {}
        for setting in self.settings:
            value = setting.get_value()
            if setting.name == 'api_key':
                value = obfuscate_api_key(value)
            config[setting.name] = value
        self.app.config["providers"][self.provider_name] = config
        self.app.save_config(self.app.config)

    def after_load(self):
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def before_load(self):
        self.client = None

    def cancel(self):
        self.close_requested = True


class OpenAICompatibleProvider(AIProvider):
    """
    Provider for OpenAI-compatible APIs.
    
    Uses self.client.chat.completions.create() to obtain a response.
    Streaming is fully removed.
    """
    def __init__(self, app):
        self.close_requested = None
        self.client = None

        settings = [
            TextSetting(name="api_key", display_name="API Key", description="API key for the OpenAI-compatible API."),
            TextSetting("api_base", "API Base URL", "https://api.openai.com/v1", "E.g. https://api.openai.com/v1"),
            TextSetting("api_organisation", "API Organisation", "", "Leave blank if not applicable."),
            TextSetting("api_project", "API Project", "", "Leave blank if not applicable."),
            TextSetting("api_model", "API Model", "gpt-4o-mini", "E.g. gpt-4o-mini"),
        ]
        super().__init__(app, "OpenAI Compatible (For Experts)", settings,
            _("• Connect to ANY OpenAI-compatible service (e.g. OpenAI, Groq, Together AI, Perplexity).\n"
              "• Supports custom Base URLs, Organizations, and Project IDs.\n"
              "• Perfect for local LLM servers (LM Studio, LocalAI) or specialized providers."),
            "openai", _("Get OpenAI API Key"), lambda: webbrowser.open("https://platform.openai.com/account/api-keys"))

    def before_load(self):
        self.client = None

    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        """
        Send a chat request to the OpenAI-compatible API.
        """
        self._require_client()
        self.close_requested = False

        content = [{"type": "text", "text": prompt}]
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"}
                })

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": content}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.api_model,
                messages=messages,
                temperature=0.5,
                stream=False
            )
            response_text = response.choices[0].message.content.strip()

            if not return_response and not hasattr(self.app, 'current_response_window'):
                self.app.output_ready_signal.emit(response_text)
            return response_text

        except Exception as e:
            error_str = str(e)
            logging.error(f"Error while generating content: {error_str}")
            if not return_response:
                if "exceeded" in error_str or "rate limit" in error_str:
                    self.app.show_message_signal.emit(
                        "Rate Limit Hit",
                        "It appears you have hit an API rate/usage limit. Please try again later or adjust your settings."
                    )
                else:
                    self.app.show_message_signal.emit("Error", f"An error occurred: {error_str}")
            return error_str

    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        """
        Send a streaming chat request to the OpenAI-compatible API.
        """
        self._require_client()
        self.close_requested = False
        content = [{"type": "text", "text": prompt}]
        if images:
            for mime_type, b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"}
                })

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": content}
        ]

        stream = self.client.chat.completions.create(
            model=self.api_model,
            messages=messages,
            temperature=0.5,
            stream=True
        )
        for chunk in stream:
            if self.close_requested:
                break
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def after_load(self):
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            organization=self.api_organisation,
            project=self.api_project
        )

    def before_load(self):
        self.client = None

    def cancel(self):
        self.close_requested = True


class OllamaProvider(AIProvider):
    """
    Provider for connecting to an Ollama server.
    
    Uses the /chat endpoint of the Ollama server to generate a response.
    Streaming is not used.
    """
    def __init__(self, app):
        self.close_requested = None
        self.client = None
        self.app = app
        settings = [
            TextSetting("api_base", "API Base URL", "http://localhost:11434", "E.g. http://localhost:11434"),
            TextSetting("api_model", "API Model", "llama3.1:8b", "E.g. llama3.1:8b"),
            TextSetting("keep_alive", "Time to keep the model loaded in memory in minutes", "5", "E.g. 5")
        ]
        super().__init__(app, "Ollama (For Experts)", settings,
            "• Connect to an Ollama server (local LLM).",
            "ollama", "Ollama Set-up Instructions",
            lambda: webbrowser.open("https://github.com/theJayTea/WritingTools?tab=readme-ov-file#-optional-ollama-local-llm-instructions-for-windows-v7-onwards"))

    def get_response(self, system_instruction: str, prompt: str, images: list = None, return_response: bool = False) -> str:
        """
        Send a chat request to the Ollama server.
        """
        self.close_requested = False

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
        
        # Add vision support
        kwargs = {}
        if images:
            messages[-1]["images"] = images

        try:
            response = self.client.chat(model=self.api_model, messages=messages, stream=False)
            response_text = response['message']['content'].strip()
            if not return_response and not hasattr(self.app, 'current_response_window'):
                self.app.output_ready_signal.emit(response_text)
            return response_text
        except Exception as e:
            error_str = str(e)
            logging.error(f"Error during Ollama chat: {error_str}")
            if not return_response:
                self.app.output_ready_signal.emit(error_str)
            return error_str

    def get_response_stream(self, system_instruction: str, prompt: str, images: list = None):
        """
        Send a streaming chat request to the Ollama server.
        """
        self.close_requested = False
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
        if images:
            messages[-1]["images"] = images

        stream = self.client.chat(model=self.api_model, messages=messages, stream=True)
        for chunk in stream:
            if self.close_requested:
                break
            yield chunk['message']['content']

    def after_load(self):
        self.client = OllamaClient(host=self.api_base)

    def before_load(self):
        self.client = None

    def cancel(self):
        self.close_requested = True
