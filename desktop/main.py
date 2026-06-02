"""Windows desktop application entry point.

Starts the FastAPI server in a daemon thread, creates a system tray icon,
and opens a pywebview window displaying the app.
"""

import os
import sys
import socket
import threading

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


def main() -> None:
    port = find_free_port()

    # Start FastAPI server in daemon thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{port}"

    # Create system tray icon
    tray_icon = create_tray()
    tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
    tray_thread.start()

    # Open WebView window
    window = webview.create_window(
        "AI Agent Chat",
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
    )

    # Close button hides to tray instead of exiting
    window.events.closing += lambda: window.hide()

    webview.start(gui='edgechromium')


if __name__ == "__main__":
    main()
