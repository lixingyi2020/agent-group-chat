import sys
import os


def get_base_dir() -> str:
    """Directory for writable data (chat.db, .fernet_key, logs).

    When frozen by PyInstaller, returns the exe's directory.
    In dev mode, returns the project root (parent of app/)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_bundle_path(relative_path: str) -> str:
    """Path to a read-only resource bundled by PyInstaller.

    When frozen, resolves relative to sys._MEIPASS (the _internal/ folder).
    In dev mode, resolves relative to the project root."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)  # pyright: ignore[reportAny]
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
