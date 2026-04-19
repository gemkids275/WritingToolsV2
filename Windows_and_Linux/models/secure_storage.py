"""
Secure storage cho per-command API keys.
Primary: keyring (Windows Credential Manager / libsecret).
Fallback: XOR+Base64 obfuscation lưu trong ~/.config/writingtools/cmd_keys.enc.json
"""
import json, os, base64, logging
# Sử dụng hằng số _XOR_KEY định nghĩa bên dưới để tránh phụ thuộc vào aiprovider

_SERVICE = "WritingTools"
# Đường dẫn fallback: ~/.config/writingtools/cmd_keys.enc.json
_FALLBACK_DIR = os.path.join(os.path.expanduser("~"), ".config", "writingtools")
_FALLBACK_PATH = os.path.join(_FALLBACK_DIR, "cmd_keys.enc.json")
_XOR_KEY = 0x5A  # Phải khớp với giá trị dùng trong aiprovider.py

try:
    import keyring as _keyring
    # Kiểm tra thực tế — một số môi trường có thư viện nhưng không có backend hoạt động
    try:
        _keyring.get_password("__probe__", "__probe__")
        _KEYRING_AVAILABLE = True
    except Exception:
        _KEYRING_AVAILABLE = False
        logging.warning("Keyring backend not available, using obfuscated local fallback")
except ImportError:
    _KEYRING_AVAILABLE = False
    logging.warning("keyring library not installed, using obfuscated local fallback")

def _obfuscate(key: str) -> str:
    xored = bytes([b ^ _XOR_KEY for b in key.encode()])
    return "enc:" + base64.b64encode(xored).decode()

def _deobfuscate(obfuscated: str) -> str:
    if not obfuscated.startswith("enc:"):
        return obfuscated
    try:
        xored = base64.b64decode(obfuscated[4:])
        return bytes([b ^ _XOR_KEY for b in xored]).decode()
    except Exception:
        return ""

def _load_fallback() -> dict:
    if not os.path.exists(_FALLBACK_PATH):
        return {}
    try:
        with open(_FALLBACK_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_fallback(data: dict):
    try:
        os.makedirs(_FALLBACK_DIR, exist_ok=True)
        with open(_FALLBACK_PATH, "w") as f:
            json.dump(data, f)
        # Chỉ owner mới có quyền đọc/ghi trên Linux
        if os.name != "nt":
            os.chmod(_FALLBACK_PATH, 0o600)
    except Exception as e:
        logging.error(f"Failed to save fallback secure storage: {e}")

def save_command_api_key(command_id: str, api_key: str):
    if not api_key:
        delete_command_api_key(command_id)
        return
    
    if _KEYRING_AVAILABLE:
        try:
            _keyring.set_password(_SERVICE, f"cmd_{command_id}", api_key)
            return
        except Exception as e:
            logging.error(f"Keyring set_password failed, falling back: {e}")
            
    # Fallback if keyring fails or not available
    data = _load_fallback()
    data[command_id] = _obfuscate(api_key)
    _save_fallback(data)

def get_command_api_key(command_id: str) -> str:
    if _KEYRING_AVAILABLE:
        try:
            key = _keyring.get_password(_SERVICE, f"cmd_{command_id}")
            if key: return key
        except Exception:
            pass
            
    # Check fallback
    data = _load_fallback()
    raw = data.get(command_id, "")
    return _deobfuscate(raw) if raw else ""

def delete_command_api_key(command_id: str):
    if _KEYRING_AVAILABLE:
        try:
            _keyring.delete_password(_SERVICE, f"cmd_{command_id}")
        except Exception:
            pass
            
    # Always try to clear from fallback too to be safe
    data = _load_fallback()
    if command_id in data:
        data.pop(command_id)
        _save_fallback(data)
