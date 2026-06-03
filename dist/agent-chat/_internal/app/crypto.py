import sys
import os
from cryptography.fernet import Fernet, InvalidToken

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_KEY_PATH = os.path.join(_get_base_dir(), ".fernet_key")


class KeyDecryptError(Exception):
    """Raised when decryption fails, likely due to key rotation or corruption."""


def _get_or_create_key() -> bytes:
    if os.path.exists(_KEY_PATH):
        with open(_KEY_PATH, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(_KEY_PATH, "wb") as f:
        f.write(key)
    return key


def encrypt(plaintext: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(encrypted: str) -> str:
    try:
        f = Fernet(_get_or_create_key())
        return f.decrypt(encrypted.encode()).decode()
    except InvalidToken as e:
        raise KeyDecryptError(
            "Failed to decrypt API key. "
            "The .fernet_key file may have been regenerated, rotated, or corrupted. "
            "Re-add your API keys in Settings."
        ) from e
