import os
from cryptography.fernet import Fernet

_KEY_PATH = ".fernet_key"


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
    f = Fernet(_get_or_create_key())
    return f.decrypt(encrypted.encode()).decode()
