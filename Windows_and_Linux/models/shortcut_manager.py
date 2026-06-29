import logging
from typing import Callable
from pynput import keyboard as pykeyboard


def _to_pynput_format(shortcut: str) -> str:
    """'ctrl+shift+p' → '<ctrl>+<shift>+p'"""
    parts = shortcut.lower().split("+")
    return "+".join(f"<{p}>" if len(p) > 1 else p for p in parts)


class ShortcutManager:
    """
    Quản lý tất cả global hotkeys (app hotkey + per-command) trong 1 Listener duy nhất.
    """

    def __init__(self):
        self._listener: pykeyboard.Listener | None = None
        self._callbacks: dict[str, Callable] = {}   # normalized shortcut → callback
        self._app_shortcut: str = ""

    def set_app_shortcut(self, shortcut: str, callback: Callable) -> None:
        """Đăng ký app hotkey. Phải gọi trước register_command_shortcuts."""
        old = self._app_shortcut
        if old and old in self._callbacks:
            del self._callbacks[old]
        self._app_shortcut = shortcut.lower()
        self._callbacks[self._app_shortcut] = callback

    def register(self, shortcut: str, callback: Callable) -> None:
        self._callbacks[shortcut.lower()] = callback

    def unregister(self, shortcut: str) -> None:
        self._callbacks.pop(shortcut.lower(), None)

    def unregister_all_commands(self) -> None:
        """Xóa tất cả command shortcuts, giữ lại app hotkey."""
        app_cb = self._callbacks.get(self._app_shortcut)
        self._callbacks = {}
        if self._app_shortcut and app_cb is not None:
            self._callbacks[self._app_shortcut] = app_cb

    def restart(self) -> None:
        """Stop listener cũ, build lại tất cả HotKey, start listener mới."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

        if not self._callbacks:
            return

        hotkeys: dict[str, pykeyboard.HotKey] = {}
        for shortcut_str, cb in self._callbacks.items():
            try:
                pynput_fmt = _to_pynput_format(shortcut_str)
                hotkeys[shortcut_str] = pykeyboard.HotKey(
                    pykeyboard.HotKey.parse(pynput_fmt), cb
                )
            except Exception as e:
                logging.warning(f"ShortcutManager: invalid shortcut '{shortcut_str}': {e}")

        # Capture listener ref in closures to avoid accessing stale self._listener
        listener_ref: list[pykeyboard.Listener | None] = [None]

        def on_press(key):
            lst = listener_ref[0]
            if lst is None:
                return
            try:
                canonical = lst.canonical(key)
                for hk in hotkeys.values():
                    hk.press(canonical)
            except Exception:
                pass

        def on_release(key):
            lst = listener_ref[0]
            if lst is None:
                return
            try:
                canonical = lst.canonical(key)
                for hk in hotkeys.values():
                    hk.release(canonical)
            except Exception:
                pass

        self._listener = pykeyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        listener_ref[0] = self._listener
        self._listener.start()
        logging.debug(f"ShortcutManager: started with {len(hotkeys)} hotkey(s): {list(hotkeys.keys())}")

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def registered_shortcuts(self) -> list[str]:
        return list(self._callbacks.keys())
