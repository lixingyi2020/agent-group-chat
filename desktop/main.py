"""Desktop application entry point.

Starts the FastAPI server in a daemon thread, creates a system tray icon,
and opens a pywebview window displaying the app.
"""

import os
import sys
import socket
import time
import platform
import threading
import urllib.request

import webview
from app.utils import get_base_dir
from desktop.tray import create_tray

# Windows uses Edge WebView2 (pre-installed on Win11); macOS uses native WKWebView
GUI_BACKEND = 'edgechromium' if platform.system() == 'Windows' else None

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_server(port: int) -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


def wait_for_server(url: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    delay = 0.05
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(delay)
            delay = min(delay * 1.5, 0.5)
    return False


def main(log_path: str) -> None:
    def log(msg: str) -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log("Starting AI Agent Chat...")

    port = find_free_port()
    log(f"Port: {port}")

    threading.Thread(target=run_server, args=(port,), daemon=True).start()
    log("Server thread started")

    url = f"http://127.0.0.1:{port}"

    try:
        tray_icon = create_tray()
        threading.Thread(target=tray_icon.run, daemon=True).start()
        log("Tray icon created")
    except Exception as e:
        log(f"Tray error: {e}")

    log("Waiting for server...")
    if not wait_for_server(url):
        log(f"ERROR: Server did not start on {url}")
        sys.exit(1)
    log("Server is ready")

    log("Creating WebView window...")
    window = webview.create_window(
        "AI Agent Chat", url,
        width=1200, height=800, min_size=(800, 600),
    )

    # Minimize to tray instead of exiting on close
    window.events.closing += lambda: window.hide()

    log("Starting WebView...")
    webview.start(gui=GUI_BACKEND)


if __name__ == "__main__":
    # Ensure project root on sys.path when running from source
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    _log_path = os.path.join(get_base_dir(), "agent-chat.log")
    try:
        main(_log_path)
    except Exception as e:
        with open(_log_path, "w", encoding="utf-8") as f:
            import traceback
            f.write(f"FATAL: {e}\n\n")
            traceback.print_exc(file=f)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Startup failed:\n\n{e}", "AI Agent Chat", 0x10)
        except Exception:
            pass
