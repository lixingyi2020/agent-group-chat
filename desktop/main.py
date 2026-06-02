"""Windows desktop application entry point.

Starts the FastAPI server in a daemon thread, creates a system tray icon,
and opens a pywebview window displaying the app.
"""

import os
import sys
import socket
import time
import threading
import urllib.request

# Ensure project root is on sys.path so 'app' and 'desktop' can be imported
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import webview
from desktop.tray import create_tray


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def run_server(port: int) -> None:
    """Start uvicorn server (blocking, runs in daemon thread)."""
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """Poll until the server responds, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    log_path = os.path.join(_project_root, "agent-chat.log")
    def log(msg):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"Starting AI Agent Chat...")
    log(f"Project root: {_project_root}")

    port = find_free_port()
    log(f"Port: {port}")

    # Start FastAPI server in daemon thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    log("Server thread started")

    url = f"http://127.0.0.1:{port}"

    # Create system tray icon
    try:
        tray_icon = create_tray()
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
        log("Tray icon created")
    except Exception as e:
        log(f"Tray error: {e}")

    # Wait for server to be ready before opening WebView
    log("Waiting for server...")
    if not wait_for_server(url):
        log(f"ERROR: Server did not start on {url}")
        sys.exit(1)
    log("Server is ready")

    # Open WebView window
    log("Creating WebView window...")
    window = webview.create_window(
        "AI Agent Chat",
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
    )

    # Close button hides to tray instead of exiting
    window.events.closing += lambda: window.hide()

    log("Starting WebView...")
    webview.start(gui='edgechromium')


if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        _log_dir = os.path.dirname(sys.executable)
    else:
        _log_dir = _project_root
    _log_path = os.path.join(_log_dir, "agent-chat.log")
    try:
        main()
    except Exception as e:
        with open(_log_path, "w", encoding="utf-8") as f:
            import traceback
            f.write(f"FATAL: {e}\n\n")
            traceback.print_exc(file=f)
        # Also try a message box
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Startup failed:\n\n{e}", "AI Agent Chat", 0x10)
        except Exception:
            pass
