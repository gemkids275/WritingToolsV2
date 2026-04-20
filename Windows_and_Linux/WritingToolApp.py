import base64
import gettext
import json
import logging
import os
import signal
import sys
import threading
import time

import darkdetect
import pyperclip
import ui.CustomPopupWindow
import ui.OnboardingWindow
import ui.ResponseWindow
import ui.SettingsWindow
from aiprovider import (AnthropicProvider, GeminiProvider, MistralProvider,
                        OllamaProvider, OpenAICompatibleProvider,
                        OpenRouterProvider, obfuscate_api_key)
from models.attachment import Attachment, AttachmentType
from models.command_manager import CommandManager
from models.secure_storage import get_command_api_key
from models.shortcut_manager import ShortcutManager
import copy
from pynput import keyboard as pykeyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QLocale, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox
from update_checker import UpdateChecker

_ = gettext.gettext


class WritingToolApp(QtWidgets.QApplication):
    """
    The main application class for AI Shortcuts.
    """
    output_ready_signal = Signal(str)
    show_message_signal = Signal(str, str)  # a signal for showing message boxes
    hotkey_triggered_signal = Signal()
    followup_response_signal = Signal(str)
    streaming_token_signal = Signal(str)
    
    # Map attribute names to correspond with aiprovider.py classes
    _PROVIDER_ATTR_MAP = {
        "Gemini (Recommended)": {"model": "model_name", "api_key": "api_key"},
        "Anthropic":            {"model": "model_name", "api_key": "api_key"},
        "Mistral":              {"model": "model_name", "api_key": "api_key"},
        "OpenRouter":           {"model": "model_name", "api_key": "api_key"},
        "OpenAI Compatible (For Experts)": {"model": "api_model", "api_key": "api_key", "base_url": "api_base"},
        "Ollama (For Experts)":            {"model": "api_model", "api_key": None, "base_url": "api_base"},
    }


    def __init__(self, argv):
        super().__init__(argv)
        self.current_response_window = None
        logging.debug('Initializing WritingToolApp')
        self.output_ready_signal.connect(self.replace_text)
        self.show_message_signal.connect(self.show_message_box)
        self.hotkey_triggered_signal.connect(self.on_hotkey_pressed)
        self.config = None
        self.config_path = None
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.load_config()


        # Initialize Command Manager (replaces load_options)
        self.command_manager = CommandManager(self.config_dir)
        self.command_manager.load()
        
        self.onboarding_window = None
        self.popup_window = None
        self.tray_icon = None
        self.tray_menu = None
        self.settings_window = None
        self.about_window = None
        self.registered_hotkey = None
        self.output_queue = ""
        self.last_replace = 0
        self.hotkey_listener = None
        self.shortcut_manager = ShortcutManager()
        self.paused = False
        self.toggle_action = None

        # Initialize update checker early so it's always available
        self.update_checker = UpdateChecker(self)

        self._ = gettext.gettext

        # Initialize the ctrl+c hotkey listener
        self.ctrl_c_timer = None
        self.setup_ctrl_c_listener()

        # Setup available AI providers
        self.providers = [
            GeminiProvider(self),
            AnthropicProvider(self),
            MistralProvider(self),
            OpenRouterProvider(self),
            OpenAICompatibleProvider(self),
            OllamaProvider(self)
        ]

        if not self.config:
            logging.debug('No config found, showing onboarding')
            self.show_onboarding()
        else:
            logging.debug('Config found, setting up hotkey and tray icon')

            # Initialize the current provider, defaulting to Gemini
            provider_name = self.config.get('provider', 'Gemini')

            self.current_provider = next((provider for provider in self.providers if provider.provider_name == provider_name), None)
            if not self.current_provider:
                logging.warning(f'Provider {provider_name} not found. Using default provider.')
                self.current_provider = self.providers[0]

            self.current_provider.load_config(self.config.get("providers", {}).get(provider_name, {}))

            self.create_tray_icon()
            self.register_hotkey()

            try:
                lang = self.config['locale']
            except KeyError:
                lang = None
            self.change_language(lang)

            self.update_checker.check_updates_async()

        self._active_provider = None  # Track the provider currently handling a request
        self.recent_triggers = []  # Track recent hotkey triggers
        self.TRIGGER_WINDOW = 1.5  # Time window in seconds
        self.MAX_TRIGGERS = 3  # Max allowed triggers in window

    def setup_translations(self, lang=None):
        if not lang:
            lang = QLocale.system().name().split('_')[0]

        try:
            translation = gettext.translation(
                'messages',
                localedir=os.path.join(os.path.dirname(__file__), 'locales'),
                languages=[lang]
            )
        except FileNotFoundError:
            translation = gettext.NullTranslations()

        translation.install()
        # Update the translation function for all UI components.
        self._ = translation.gettext
        ui.SettingsWindow._ = self._
        ui.ResponseWindow._ = self._
        ui.OnboardingWindow._ = self._
        ui.CustomPopupWindow._ = self._

    def retranslate_ui(self):
        self.update_tray_menu()

    def change_language(self, lang):
        self.setup_translations(lang)
        self.retranslate_ui()

        # Update all other windows
        for widget in QApplication.topLevelWidgets():
            if widget != self and hasattr(widget, 'retranslate_ui'):
                widget.retranslate_ui()

    def check_trigger_spam(self):
        """
        Check if hotkey is being triggered too frequently (3+ times in 1.5 seconds).
        Returns True if spam is detected.
        """
        current_time = time.time()
        
        # Add current trigger
        self.recent_triggers.append(current_time)
        
        # Remove old triggers outside the window
        self.recent_triggers = [t for t in self.recent_triggers 
                            if current_time - t <= self.TRIGGER_WINDOW]
        
        # Check if we have too many triggers in the window
        return len(self.recent_triggers) >= self.MAX_TRIGGERS

    def load_config(self):
        """
        Load the configuration file.
        """
        self.config_path = os.path.join(os.path.dirname(sys.argv[0]), 'config.json')
        logging.debug(f'Loading config from {self.config_path}')
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
                logging.debug('Config loaded successfully')
        else:
            logging.debug('Config file not found')
            self.config = None

    def load_options(self):
        """
        Load the options file.
        """
        self.options_path = os.path.join(os.path.dirname(sys.argv[0]), 'options.json')
        logging.debug(f'Loading options from {self.options_path}')
        if os.path.exists(self.options_path):
            with open(self.options_path, 'r') as f:
                self.options = json.load(f)
                logging.debug('Options loaded successfully')
        else:
            logging.debug('Options file not found')
            self.options = None

    def save_config(self, config):
        """
        Save the configuration file.
        """
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)
            logging.debug('Config saved successfully')
        self.config = config

    def show_onboarding(self):
        """
        Show the onboarding window for first-time users.
        """
        logging.debug('Showing onboarding window')
        self.onboarding_window = ui.OnboardingWindow.OnboardingWindow(self)
        self.onboarding_window.close_signal.connect(self.exit_app)
        self.onboarding_window.show()

    def register_hotkey(self):
        """Register app hotkey + all per-command shortcuts via ShortcutManager."""
        app_shortcut = self.config.get('shortcut', 'ctrl+space')
        self.registered_hotkey = app_shortcut

        def on_app_hotkey():
            if self.paused:
                return
            logging.debug('triggered app hotkey')
            self.hotkey_triggered_signal.emit()

        self.shortcut_manager.set_app_shortcut(app_shortcut, on_app_hotkey)
        self._register_command_shortcuts()
        self.shortcut_manager.restart()
        logging.debug('Hotkey registered')

    def _register_command_shortcuts(self):
        self.shortcut_manager.unregister_all_commands()
        for cmd in self.command_manager.commands:
            if cmd.keyboard_shortcut:
                def _make_cb(c):
                    def cb():
                        if self.paused:
                            return
                        QtCore.QMetaObject.invokeMethod(
                            self, '_trigger_command_shortcut',
                            QtCore.Qt.ConnectionType.QueuedConnection,
                            QtCore.Q_ARG(str, c.id)
                        )
                    return cb
                self.shortcut_manager.register(cmd.keyboard_shortcut, _make_cb(cmd))

    def refresh_command_shortcuts(self):
        """Gọi sau khi user thay đổi commands để re-register shortcuts."""
        self._register_command_shortcuts()
        self.shortcut_manager.restart()

    @Slot(str)
    def _trigger_command_shortcut(self, command_id: str):
        """Execute command từ keyboard shortcut — chạy trên main thread."""
        cmd = self.command_manager.get_command(command_id)
        if not cmd:
            return
        selected_text = self.get_selected_text()
        if not selected_text:
            selected_text = self.get_selected_text(sleep_duration=0.5)
        self.process_option(command_id, selected_text)

    def on_hotkey_pressed(self):
        """
        Handle the hotkey press event.
        """
        logging.debug('Hotkey pressed')
        
        # Check for spam triggers
        if self.check_trigger_spam():
            logging.warning('Hotkey spam detected - quitting application')
            self.exit_app()
            return
            
        # Original hotkey handling continues...
        if self._active_provider:
            logging.debug("Cancelling active provider's request")
            self._active_provider.cancel()
        elif self.current_provider:
            logging.debug("Cancelling current provider's request")
            self.current_provider.cancel()
        self.output_queue = ""

        # noinspection PyTypeChecker
        QtCore.QMetaObject.invokeMethod(self, "_show_popup", QtCore.Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _show_popup(self):
        """
        Show the popup window when the hotkey is pressed.
        """
        logging.debug('Showing popup window')
        # First attempt with default sleep
        selected_text = self.get_selected_text()

        # Retry with longer sleep if no text captured
        if not selected_text:
            logging.debug('No text captured, retrying with longer sleep')
            selected_text = self.get_selected_text(sleep_duration=0.5)

        logging.debug(f'Selected text: "{selected_text}"')
        try:
            if self.popup_window is not None:
                logging.debug('Existing popup window found')
                if self.popup_window.isVisible():
                    logging.debug('Closing existing visible popup window')
                    self.popup_window.close()
                self.popup_window = None
            logging.debug('Creating new popup window')
            self.popup_window = ui.CustomPopupWindow.CustomPopupWindow(self, selected_text)

            # Set the window icon
            icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
            if os.path.exists(icon_path): self.setWindowIcon(QtGui.QIcon(icon_path))
            # Get the screen containing the cursor
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos)
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            screen_geometry = screen.geometry()
            logging.debug(f'Cursor is on screen: {screen.name()}')
            logging.debug(f'Screen geometry: {screen_geometry}')
            # Show the popup to get its size
            self.popup_window.show()
            self.popup_window.adjustSize()
            # Ensure the popup it's focused, even on lower-end machines
            self.popup_window.activateWindow()
            QtCore.QTimer.singleShot(100, self.popup_window.custom_input.setFocus)

            popup_width = self.popup_window.width()
            popup_height = self.popup_window.height()
            # Calculate position
            x = cursor_pos.x()
            y = cursor_pos.y() + 20  # 20 pixels below cursor
            # Adjust if the popup would go off the right edge of the screen
            if x + popup_width > screen_geometry.right():
                x = screen_geometry.right() - popup_width
            # Adjust if the popup would go off the bottom edge of the screen
            if y + popup_height > screen_geometry.bottom():
                y = cursor_pos.y() - popup_height - 10  # 10 pixels above cursor
            self.popup_window.move(x, y)
            logging.debug(f'Popup window moved to position: ({x}, {y})')
        except Exception as e:
            logging.error(f'Error showing popup window: {e}', exc_info=True)

    def get_selected_text(self, sleep_duration=0.2):
        """
        Get the currently selected text from any application.
        Args:
            sleep_duration (float): Time to wait for clipboard update
        """
        # Backup the clipboard
        clipboard_backup = pyperclip.paste()
        logging.debug(f'Clipboard backup: "{clipboard_backup}" (sleep: {sleep_duration}s)')

        # Clear the clipboard
        self.clear_clipboard()

        # Simulate Ctrl+C
        logging.debug('Simulating Ctrl+C')
        kbrd = pykeyboard.Controller()

        def press_ctrl_c():
            kbrd.press(pykeyboard.Key.ctrl.value)
            kbrd.press('c')
            kbrd.release('c')
            kbrd.release(pykeyboard.Key.ctrl.value)

        press_ctrl_c()

        # Wait for the clipboard to update
        time.sleep(sleep_duration)
        logging.debug(f'Waited {sleep_duration}s for clipboard')

        # Get the selected text
        selected_text = pyperclip.paste()

        # Restore the clipboard
        pyperclip.copy(clipboard_backup)

        return selected_text

    def _resolve_provider(self, command=None):
        """
        Returns the appropriate provider instance for a command.
        Never mutates self.current_provider.
        """
        if not command or not command.provider_override:
            return self.current_provider

        # Custom Mode: User-configured OpenAI-compatible endpoint
        if command.provider_override == "custom":
            base_url = (command.custom_provider_base_url or "").strip()
            model    = (command.custom_provider_model or "").strip()
            api_key  = get_command_api_key(command.id)
            
            if not base_url or not model:
                raise ValueError(
                    f"Command '{command.name}': custom provider is missing Base URL or Model."
                )
            
            from aiprovider import OpenAICompatibleProvider
            tmp = OpenAICompatibleProvider(self)
            tmp.load_config({"api_base": base_url, "api_model": model, "api_key": api_key})
            return tmp

        # Standard Mode: Use an existing configured provider
        provider = next(
            (p for p in self.providers if p.provider_name == command.provider_override),
            None,
        )
        if not provider:
            logging.warning(f"Provider '{command.provider_override}' not found, using default provider")
            return self.current_provider

        model_override    = command.model_override
        api_key_override  = get_command_api_key(command.id)
        base_url_override = command.custom_provider_base_url

        # No overrides needed -> use the original instance
        if not model_override and not api_key_override and not base_url_override:
            return provider

        # Overrides exist -> create a shallow copy and re-initialize
        attrs         = self._PROVIDER_ATTR_MAP.get(command.provider_override, {})
        model_attr    = attrs.get("model")
        key_attr      = attrs.get("api_key")
        base_url_attr = attrs.get("base_url")

        tmp = copy.copy(provider)
        if model_override and model_attr:
            setattr(tmp, model_attr, model_override)
        if api_key_override and key_attr:
            setattr(tmp, key_attr, api_key_override)
        if base_url_override and base_url_attr:
            setattr(tmp, base_url_attr, base_url_override)

        tmp.after_load()  # Re-initialize API client with new config
        return tmp

    @staticmethod
    def clear_clipboard():
        """
        Clear the system clipboard.
        """
        try:
            pyperclip.copy('')
        except Exception as e:
            logging.error(f'Error clearing clipboard: {e}')

    def process_option(self, option_id_or_name, selected_text, custom_change=None, attachments=None):
        """
        Process the selected writing option in a separate thread.
        """
        logging.debug(f'Processing option: {option_id_or_name}')

        # Get command details from manager (try ID first, then name for backward compatibility)
        command = self.command_manager.get_command(option_id_or_name)
        if not command:
            command = self.command_manager.get_by_name(option_id_or_name)
        
        if not command and option_id_or_name != 'Custom':
            logging.error(f"Command not found: {option_id_or_name}")
            return

        # Check if we should open in window
        use_window = False
        if option_id_or_name == 'Custom' and not selected_text.strip():
            use_window = True
        elif command:
            use_window = command.use_response_window

        if use_window:
            window_title = "Chat" if (option_id_or_name == 'Custom' and not selected_text.strip()) else (command.name if command else option_id_or_name)
            self.current_response_window = self.show_response_window(window_title, selected_text, command.id if command else None)
            
            # Initialize chat history with text/prompt
            if option_id_or_name == 'Custom' and not selected_text.strip():
                # For direct AI queries, don't include empty text
                self.current_response_window.chat_history = []
            else:
                # For other options, include the original text
                self.current_response_window.chat_history = [
                    {
                        "role": "user",
                        "content": f"Original text to {(command.name if command else option_id_or_name).lower()}:\n\n{selected_text}"
                    }
                ]
        else:
            # Clear any existing response window reference for non-window options
            if hasattr(self, 'current_response_window'):
                delattr(self, 'current_response_window')
                
        threading.Thread(target=self.process_option_thread, args=(option_id_or_name, selected_text, custom_change, attachments or []), daemon=True).start()

    def process_option_thread(self, option_id_or_name, selected_text, custom_change=None, attachments=None):
            """
            Thread function to process the selected writing option using the AI model.
            """
            logging.debug(f'Starting processing thread for option: {option_id_or_name}')
            try:
                attachments = attachments or []
                images = [(a.mime_type, base64.b64encode(a.data).decode()) for a in attachments if a.type == AttachmentType.IMAGE and a.data]
                text_context = "\n\n".join(
                    f"[{a.label}]:\n{a.text}"
                    for a in attachments
                    if a.type == AttachmentType.TEXT and a.text
                )

                command = None  # khởi tạo sớm để _resolve_provider không UnboundLocalError
                # Default custom instruction prompt if no text is selected
                DEFAULT_PROMPT = "You are a friendly, helpful, compassionate, and endearing AI conversational assistant. Avoid making assumptions or generating harmful, biased, or inappropriate content. When in doubt, do not make up information. Ask the user for clarification if needed. Try not be unnecessarily repetitive in your response. You can, and should as appropriate, use Markdown formatting to make your response nicely readable."

                if selected_text.strip() == '':
                    # No selected text
                    if option_id_or_name == 'Custom':
                        prompt = custom_change or ""
                        if text_context:
                            prompt = f"{prompt}\n\nAdditional Context:\n{text_context}" if prompt else text_context
                        chat_cmd = self.command_manager.get_command('ChatNoSelection')
                        if chat_cmd:
                            system_instruction = chat_cmd.prompt
                        else:
                            system_instruction = self.config.get("custom_instruction_prompt", DEFAULT_PROMPT)
                    else:
                        self.show_message_signal.emit('Error', 'Please select text to use this option.')
                        return
                else:
                    command = self.command_manager.get_command(option_id_or_name)
                    if not command:
                        command = self.command_manager.get_by_name(option_id_or_name)

                    if not command:
                        prompt_prefix = "Make this change to the following text:\n\n"
                        system_instruction = "You are a writing assistant."
                    else:
                        prompt_prefix = command.prefix
                        system_instruction = command.prompt

                    if option_id_or_name == 'Custom':
                        prompt = f"{prompt_prefix}Described change: {custom_change}\n\nText: {selected_text}"
                    else:
                        prompt = f"{prompt_prefix}{selected_text}"

                    if text_context:
                        prompt += f"\n\nAdditional Context:\n{text_context}"

                self.output_queue = ""

                # Resolve provider for this specific command
                try:
                    active_provider = self._resolve_provider(command)
                    self._active_provider = active_provider
                except ValueError as e:
                    self.show_message_signal.emit("Provider Error", str(e))
                    return

                logging.debug(f'Getting response from provider for option: {option_id_or_name}')

                # Check if we should open in window
                use_window = False
                if option_id_or_name == 'Custom' and not selected_text.strip():
                    use_window = True
                elif command and command.use_response_window:
                    use_window = True

                if use_window:
                    logging.debug('Getting response for window display')
                    
                    img_arg = images or None
                    if self.config.get('streaming', True):  # Default to True for better UX
                        logging.debug('Using streaming response')
                        full_response = ""
                        try:
                            for chunk in active_provider.get_response_stream(system_instruction, prompt, images=img_arg):
                                if chunk:
                                    full_response += chunk
                                    # noinspection PyTypeChecker
                                    QtCore.QMetaObject.invokeMethod(
                                        self, 'emit_streaming_token',
                                        QtCore.Qt.ConnectionType.QueuedConnection,
                                        QtCore.Q_ARG(str, chunk)
                                    )
                            response = full_response
                        except Exception as e:
                            logging.error(f"Streaming error: {e}")
                            try:
                                response = active_provider.get_response(system_instruction, prompt, images=img_arg, return_response=True)
                            except Exception as e2:
                                response = str(e2)
                    else:
                        try:
                            response = active_provider.get_response(system_instruction, prompt, images=img_arg, return_response=True)
                        except Exception as e:
                            response = str(e)
                    
                    logging.debug(f'Got response of length: {len(response) if response else 0}')
                    
                    # For custom prompts with no text, add question to chat history
                    if option_id_or_name == 'Custom' and not selected_text.strip():
                        self.current_response_window.chat_history.append({
                            "role": "user",
                            "content": custom_change
                        })
                    
                    # Set initial response using QMetaObject.invokeMethod to ensure thread safety
                    if hasattr(self, 'current_response_window'):
                        # noinspection PyTypeChecker
                        QtCore.QMetaObject.invokeMethod(
                            self.current_response_window,
                            'set_text',
                            QtCore.Qt.ConnectionType.QueuedConnection,
                            QtCore.Q_ARG(str, response)
                        )
                        logging.debug('Invoked set_text on response window')
                else:
                    logging.debug('Getting response for direct replacement')
                    active_provider.get_response(system_instruction, prompt, images=images or None)
                    logging.debug('Response processed')

            except Exception as e:
                logging.error(f'An error occurred: {e}', exc_info=True)

                if "Resource has been exhausted" in str(e):
                    self.show_message_signal.emit('Error - Rate Limit Hit', 'Whoops! You\'ve hit the per-minute rate limit of the Gemini API. Please try again in a few moments.\n\nIf this happens often, simply switch to a Gemini model with a higher usage limit in Settings.')
                else:
                    self.show_message_signal.emit('Error', f'An error occurred: {e}')

    @Slot(str, str)
    def show_message_box(self, title, message):
        """
        Show a message box with the given title and message.
        """
        QMessageBox.warning(None, title, message)

    def show_response_window(self, window_title, text, command_id=None):
        """
        Show the response in a new window instead of pasting it.
        """
        response_window = ui.ResponseWindow.ResponseWindow(self, f"{window_title} Result", command_id)
        response_window.selected_text = text  # Store the text for regeneration
        response_window.show()
        return response_window

    def replace_text(self, new_text):
        """
        Replaces the text by pasting in the LLM generated text. With "Key Points" and "Summary", invokes a window with the output instead.
        """
        error_message = 'ERROR_TEXT_INCOMPATIBLE_WITH_REQUEST'

        # Confirm new_text exists and is a string
        if new_text and isinstance(new_text, str):
            self.output_queue += new_text
            current_output = self.output_queue.strip()  # Strip whitespace for comparison

            # If the new text is the error message, show a message box
            if current_output == error_message:
                self.show_message_signal.emit('Error', 'The text is incompatible with the requested change.')
                return

            # Check if we're building up to the error message (to prevent partial pasting)
            if len(current_output) <= len(error_message):
                clean_current = ''.join(current_output.split())
                clean_error = ''.join(error_message.split())
                if clean_current == clean_error[:len(clean_current)]:
                    return

            logging.debug('Processing output text')
            try:
                # For Summary and Key Points, show in response window
                if hasattr(self, 'current_response_window'):
                    self.current_response_window.append_text(new_text)
                    
                    # If this is the initial response, add it to chat history
                    if len(self.current_response_window.chat_history) == 1:  # Only original text exists
                        self.current_response_window.chat_history.append({
                            "role": "assistant",
                            "content": self.output_queue.rstrip('\n')
                        })
                else:
                    # For other options, use the original clipboard-based replacement
                    clipboard_backup = pyperclip.paste()
                    cleaned_text = self.output_queue.rstrip('\n')
                    pyperclip.copy(cleaned_text)
                    
                    kbrd = pykeyboard.Controller()
                    def press_ctrl_v():
                        kbrd.press(pykeyboard.Key.ctrl.value)
                        kbrd.press('v')
                        kbrd.release('v')
                        kbrd.release(pykeyboard.Key.ctrl.value)

                    press_ctrl_v()
                    time.sleep(0.2)
                    pyperclip.copy(clipboard_backup)

                if not hasattr(self, 'current_response_window'):
                    self.output_queue = ""

            except Exception as e:
                logging.error(f'Error processing output: {e}')
        else:
            logging.debug('No new text to process')

    @Slot(str)
    def emit_streaming_token(self, token):
        """
        Slot to emit a streaming token to the current response window.
        """
        if hasattr(self, 'current_response_window') and self.current_response_window:
            # noinspection PyTypeChecker
            QtCore.QMetaObject.invokeMethod(
                self.current_response_window,
                'append_token',
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, token)
            )

    def create_tray_icon(self):
        """
        Create the system tray icon for the application.
        """
        if self.tray_icon:
            logging.debug('Tray icon already exists')
            return

        logging.debug('Creating system tray icon')
        icon_path = os.path.join(os.path.dirname(sys.argv[0]), 'icons', 'app_icon.png')
        if not os.path.exists(icon_path):
            logging.warning(f'Tray icon not found at {icon_path}')
            # Use a default icon if not found
            self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        else:
            self.tray_icon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(icon_path), self)
        # Set the tooltip (hover name) for the tray icon
        self.tray_icon.setToolTip("AI Shortcuts")
        self.tray_menu = QtWidgets.QMenu()
        self.tray_icon.setContextMenu(self.tray_menu)

        self.update_tray_menu()
        self.tray_icon.show()
        logging.debug('Tray icon displayed')

    def update_tray_menu(self):
        """
        Update the tray menu with all menu items, including pause functionality
        and proper translations.
        """
        self.tray_menu.clear()

        # Apply dark mode styles using darkdetect
        self.apply_dark_mode_styles(self.tray_menu)

        # Settings menu item
        settings_action = self.tray_menu.addAction(self._('Settings'))
        settings_action.triggered.connect(self.show_settings)

        # Pause/Resume toggle action 
        self.toggle_action = self.tray_menu.addAction(self._('Resume') if self.paused else self._('Pause'))
        self.toggle_action.triggered.connect(self.toggle_paused)

        # About menu item
        about_action = self.tray_menu.addAction(self._('About'))
        about_action.triggered.connect(self.show_about)

        # Exit menu item
        exit_action = self.tray_menu.addAction(self._('Exit'))
        exit_action.triggered.connect(self.exit_app)
        
    def toggle_paused(self):
        """Toggle the paused state of the application."""
        logging.debug('Toggle paused state')
        self.paused = not self.paused
        self.toggle_action.setText(self._('Resume') if self.paused else self._('Pause'))
        logging.debug('App is paused' if self.paused else 'App is resumed')

    @staticmethod
    def apply_dark_mode_styles(menu):
        """
        Apply styles to the tray menu based on system theme using darkdetect.
        """
        is_dark_mode = darkdetect.isDark()
        palette = menu.palette()

        if is_dark_mode:
            logging.debug('Tray icon dark')
            # Dark mode colors
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#2d2d2d"))  # Dark background
            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#ffffff"))  # White text
        else:
            logging.debug('Tray icon light')
            # Light mode colors
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#ffffff"))  # Light background
            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#000000"))  # Black text

        menu.setPalette(palette)


    """
    The function below (process_followup_question) processes follow-up questions in the chat interface for Summary, Key Points, and Table operations.

    This method handles the complex interaction between the UI, chat history, and AI providers:

    1. Chat History Management:
    - Maintains a list of all messages (original text, summary, follow-ups)
    - Properly formats roles (user/assistant) for each message
    - Preserves conversation context across multiple questions (until the Window is closed)

    2. Provider-Specific Handling:
    a) Gemini:
        - Converts internal roles to Gemini's user/model format
        - Uses chat sessions with proper history formatting
        - Maintains context through chat.send_message()
    
    b) OpenAI-compatible:
        - Uses standard OpenAI message array format
        - Includes system instruction and full conversation history
        - Properly maps internal roles to OpenAI roles

    3. Flow:
    a) User asks follow-up question
    b) Question is added to chat history
    c) Full history is formatted for the current provider
    d) Response is generated while maintaining context
    e) Response is displayed in chat UI
    f) New response is added to history for future context

    4. Threading:
    - Runs in a separate thread to prevent UI freezing
    - Uses signals to safely update UI from background thread
    - Handles errors too

    Args:
        response_window: The ResponseWindow instance managing the chat UI
        question: The follow-up question from the user

    This implementation is a bit convoluted, but it allows us to manage chat history & model roles across both providers! :3
    """

    def process_followup_question(self, response_window, question, attachments: list[Attachment] | None = None):
        """
        Process a follow-up question in the chat window.
        """
        logging.debug(f'Processing follow-up question: {question}')
        attachments = attachments or []

        def process_thread():
            logging.debug('Starting follow-up processing thread')
            try:
                if not response_window.chat_history:
                    logging.error("No chat history found")
                    self.show_message_signal.emit('Error', 'Chat history not found')
                    return

                # Extract images và text context từ attachments
                images = [(a.mime_type, base64.b64encode(a.data).decode()) for a in attachments if a.type == AttachmentType.IMAGE and a.data]
                text_context = "\n\n".join(
                    f"[{a.label}]:\n{a.text}"
                    for a in attachments
                    if a.type == AttachmentType.TEXT and a.text
                )
                full_question = question
                if text_context:
                    full_question = f"{question}\n\nAdditional Context:\n{text_context}" if question else text_context

                # Add current question to chat history (với full context)
                response_window.chat_history.append({
                    "role": "user",
                    "content": full_question or "(see attachments)"
                })

                # System instruction based on original option
                system_instruction = "You are a helpful AI assistant. Provide clear and direct responses, maintaining the same format and style as your previous responses. If appropriate, use Markdown formatting to make your response more readable."

                # Resolve provider for this specific window/command
                command = None
                if response_window.command_id:
                    command = self.command_manager.get_command(response_window.command_id)

                try:
                    active_provider = self._resolve_provider(command)
                except ValueError as e:
                    self.show_message_signal.emit("Provider Error", str(e))
                    return

                logging.debug('Sending request to AI provider')

                # Decide whether to stream
                if self.config.get('streaming', True):
                    logging.debug('Using streaming for follow-up')
                    full_response = ""
                    try:
                        for chunk in active_provider.get_response_stream(system_instruction, full_question, images=images or None):
                            if chunk:
                                full_response += chunk
                                # noinspection PyTypeChecker
                                QtCore.QMetaObject.invokeMethod(
                                    self, 'emit_streaming_token',
                                    QtCore.Qt.ConnectionType.QueuedConnection,
                                    QtCore.Q_ARG(str, chunk)
                                )
                        response_text = full_response
                    except Exception as e:
                        logging.error(f"Streaming follow-up error: {e}")
                        response_text = active_provider.get_response(system_instruction, full_question, images=images or None, return_response=True)
                else:
                    response_text = active_provider.get_response(system_instruction, full_question, images=images or None, return_response=True)

                logging.debug(f'Got response of length: {len(response_text)}')
                
                # Add response to chat history
                response_window.chat_history.append({
                    "role": "assistant",
                    "content": response_text
                })
                
                # Emit response via signal
                self.followup_response_signal.emit(response_text)

            except Exception as e:
                logging.error(f'Error processing follow-up question: {e}', exc_info=True)

                if "Resource has been exhausted" in str(e):
                    self.show_message_signal.emit('Error - Rate Limit Hit', 'Whoops! You\'ve hit the per-minute rate limit of the Gemini API. Please try again in a few moments.\n\nIf this happens often, simply switch to a Gemini model with a higher usage limit in Settings.')
                    self.followup_response_signal.emit("Sorry, an error occurred while processing your question.")
                else:
                    self.show_message_signal.emit('Error', f'An error occurred: {e}')
                    self.followup_response_signal.emit("Sorry, an error occurred while processing your question.")

        # Start the thread
        threading.Thread(target=process_thread, daemon=True).start()

    def show_settings(self, providers_only=False, initial_tab=None):
        """
        Show the settings window.
        """
        logging.debug('Showing settings window')
        # Always create a new settings window to handle providers_only and initial_tab correctly
        self.settings_window = ui.SettingsWindow.SettingsWindow(self, providers_only=providers_only, initial_tab=initial_tab)
        self.settings_window.close_signal.connect(self.exit_app)
        self.settings_window.retranslate_ui()
        self.settings_window.show()

    def show_about(self):
        """
        Show the about section within settings window.
        """
        logging.debug('Showing about via settings')
        self.show_settings(initial_tab="about")

    def setup_ctrl_c_listener(self):
        """
        Listener for Ctrl+C to exit the app.
        """
        signal.signal(signal.SIGINT, lambda signum, frame: self.handle_sigint(signum, frame))
        # This empty timer is needed to make sure that the sigint handler gets checked inside the main loop:
        # without it, the sigint handle would trigger only when an event is triggered, either by a hotkey combination
        # or by another GUI event like spawning a new window. With this we trigger it every 100ms with an empy lambda
        # so that the signal handler gets checked regularly.
        self.ctrl_c_timer = QtCore.QTimer()
        self.ctrl_c_timer.start(100)
        self.ctrl_c_timer.timeout.connect(lambda: None)
    def handle_sigint(self, signum, frame):
        """
        Handle the SIGINT signal (Ctrl+C) to exit the app gracefully.
        """
        logging.info("Received SIGINT. Exiting...")
        self.exit_app()

    def exit_app(self):
        """
        Exit the application.
        """
        logging.debug('Stopping the listener')
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        logging.debug('Exiting application')
        self.quit()
