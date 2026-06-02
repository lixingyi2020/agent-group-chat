# Windows Standalone Desktop Application — Design Spec

> **Status:** Approved | **Date:** 2026-06-02

**Goal:** Package the existing FastAPI + HTMX multi-agent chat app into a standalone Windows desktop application with an embedded WebView window, system tray support, and portable folder distribution.

**Context:** The app currently runs via `python run.py` on the command line. The user wants a double-click-to-run experience on Windows without requiring Python knowledge.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              agent-chat.exe                   │
│                                               │
│  ┌─ Main Thread ───────────────────────────┐ │
│  │ 1. Find free port                        │ │
│  │ 2. Spawn uvicorn in daemon thread        │ │
│  │ 3. Create system tray icon               │ │
│  │ 4. Open pywebview window → localhost:port│ │
│  │ 5. Run event loop (blocking)             │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│  ┌─ Background Thread ─────────────────────┐ │
│  │ FastAPI via uvicorn                      │ │
│  │ http://127.0.0.1:{random_port}           │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### Key design decisions

- **Random port**: Avoid conflicts with other apps or existing uvicorn instances. WebView navigates to the dynamically assigned port.
- **Daemon thread**: uvicorn runs in a daemon thread so it terminates when the main process exits.
- **pywebview**: Uses Windows' built-in Edge WebView2 runtime, which is pre-installed on Windows 11 (our target OS). No Chromium bundle needed.
- **Tray minimize**: Closing the WebView window hides it to tray; the tray is the lifecycle owner. Exit only via tray "退出" menu item.

---

## File Structure

### New files

```
desktop/
├── __init__.py
├── main.py          # Desktop entry point
├── tray.py          # System tray icon + menu
├── icon.png         # 256x256 app icon (tray + window)
build.bat            # PyInstaller build script
```

### Modified files

| File | Change |
|------|--------|
| `app/db/queries.py` | `DB_PATH` resolved relative to exe dir (portable mode) |
| `app/crypto.py` | `_KEY_PATH` resolved relative to exe dir |
| `requirements.txt` | Add `pywebview`, `pystray`, `Pillow`; remove `python-dotenv` |

---

## Component Details

### `desktop/main.py`

```python
import socket
import threading
import uvicorn
import webview
from desktop.tray import create_tray

def find_free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_server(port):
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")

def main():
    port = find_free_port()
    
    # Start server in daemon thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    
    url = f"http://127.0.0.1:{port}"
    
    # Create tray icon
    tray = create_tray(port)
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()
    
    # Open WebView window
    window = webview.create_window("AI Agent Chat", url, width=1200, height=800, min_size=(800, 600))
    
    # Override close → minimize to tray
    window.events.closing += lambda: window.hide()
    
    webview.start()
    # webview.start() blocks until window is destroyed
    # When user clicks "Exit" in tray, tray.stop() is called which calls os._exit()

if __name__ == "__main__":
    main()
```

### `desktop/tray.py`

```python
import os
import pystray
from PIL import Image, ImageDraw

def create_icon():
    """Generate a simple colored square icon at runtime."""
    img = Image.new('RGBA', (64, 64), (0, 113, 227, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 16), "AI", fill='white')
    return img

def create_tray(port=None):
    def on_open(icon, item):
        import webview
        windows = webview.windows
        if windows:
            windows[0].show()
        else:
            webview.create_window("AI Agent Chat", f"http://127.0.0.1:{port}", 
                                  width=1200, height=800, min_size=(800, 600))
            # Need to re-enter webview loop — simplified: just show existing

    def on_exit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open / 打开", on_open, default=True),
        pystray.MenuItem("Exit / 退出", on_exit),
    )
    icon = create_icon()
    return pystray.Icon("agent-chat", icon, "AI Agent Chat", menu)
```

### Portable Path Resolution

Both `app/db/queries.py` and `app/crypto.py` need to resolve paths relative to the executable location when running as a packaged app:

```python
import sys, os

def _get_base_dir():
    """Get the directory containing the executable or script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _get_base_dir()
DB_PATH = os.path.join(BASE_DIR, "chat.db")
_KEY_PATH = os.path.join(BASE_DIR, ".fernet_key")
```

---

## Packaging

### `build.bat`

```batch
pyinstaller ^
  --onedir ^
  --name "agent-chat" ^
  --add-data "app;app" ^
  --add-data "app/templates;app/templates" ^
  --hidden-import uvicorn ^
  --hidden-import pystray ^
  --hidden-import PIL._imaging ^
  --collect-all jinja2 ^
  desktop/main.py
```

Output: `dist/agent-chat/` folder containing `agent-chat.exe` and all dependencies.

### Distribution

Zip the `dist/agent-chat/` folder. User extracts and double-clicks `agent-chat.exe`. The `chat.db` and `.fernet_key` files are created alongside the exe on first run.

---

## Window Behavior

| Action | Result |
|--------|--------|
| Double-click exe | Server starts, tray icon appears, WebView window opens |
| Close window (X) | Window hides → tray icon remains, server keeps running |
| Click tray icon | "Open / 打开" — restores the window |
| Right-click tray → Exit | Server stops, process exits |

---

## Dependencies

### Added
- `pywebview` — native WebView window (uses Edge WebView2 on Windows)
- `pystray` — system tray icon and menu
- `Pillow` — generate tray icon image at runtime

### Removed
- `python-dotenv` — not needed for desktop deployment

---

## Testing

- Unit tests unchanged (44 existing tests) — they test the web app, which runs identically
- Manual desktop verification:
  1. `python desktop/main.py` — app starts, WebView opens, tray appears
  2. Close WebView → hides to tray
  3. Click "Open" in tray → window restores
  4. Click "Exit" → process exits cleanly
  5. `build.bat` produces working `dist/agent-chat/` folder
  6. `chat.db` and `.fernet_key` created alongside exe
