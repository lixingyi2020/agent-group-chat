# Windows Desktop Application — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing FastAPI multi-agent chat app into a standalone Windows desktop app with embedded WebView, system tray, and portable folder distribution.

**Architecture:** Add a `desktop/` package with a main entry point that starts uvicorn in a daemon thread, creates a system tray icon, and opens a pywebview window. Make DB and crypto paths portable (relative to exe directory). Package with PyInstaller `--onedir`.

**Tech Stack:** pywebview, pystray, Pillow, PyInstaller, existing FastAPI/uvicorn/aiosqlite

---

## File Map

| File | Responsibility |
|------|---------------|
| `desktop/main.py` | Entry point: find port, start server, create tray, open WebView |
| `desktop/tray.py` | System tray icon with Open/Exit menu |
| `desktop/__init__.py` | Empty package marker |
| `desktop/icon.png` | App icon (256×256) |
| `build.bat` | PyInstaller build script |
| `app/db/queries.py` | `DB_PATH` → portable (relative to exe) |
| `app/crypto.py` | `_KEY_PATH` → portable (relative to exe) |
| `requirements.txt` | Add pywebview, pystray, Pillow |

---

### Task 1: Portable path resolution

**Files:**
- Modify: `app/db/queries.py:5`
- Modify: `app/crypto.py:1-4`

Make `DB_PATH` and `_KEY_PATH` resolve relative to the executable directory (when packaged with PyInstaller) or the project root (when running from source).

- [ ] **Step 1: Add path helper to queries.py**

Replace the hardcoded `DB_PATH = "chat.db"` line:

```python
import sys
import os

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(_get_base_dir(), "chat.db")
```

- [ ] **Step 2: Update crypto.py key path**

Replace lines 1-4:

```python
import sys
import os
from cryptography.fernet import Fernet, InvalidToken

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_KEY_PATH = os.path.join(_get_base_dir(), ".fernet_key")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -q`
Expected: 44 PASS

- [ ] **Step 4: Commit**

```bash
git add app/db/queries.py app/crypto.py
git commit -m "feat: make DB and crypto paths portable (relative to exe directory)"
```

---

### Task 2: Desktop entry point — main.py

**Files:**
- Create: `desktop/__init__.py`
- Create: `desktop/main.py`
- Create: `desktop/tray.py`

- [ ] **Step 1: Create desktop/__init__.py**

```python
# desktop package
```

- [ ] **Step 2: Create desktop/main.py**

```python
"""Windows desktop application entry point.

Starts the FastAPI server in a daemon thread, creates a system tray icon,
and opens a pywebview window displaying the app.
"""

import socket
import threading
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

    # Close button → minimize to tray instead of exiting
    window.events.closing += lambda: window.hide()

    webview.start(gui='edgechromium')


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create desktop/tray.py**

```python
"""System tray icon for the desktop app."""

import os
import pystray
from PIL import Image, ImageDraw


def _make_icon() -> Image.Image:
    """Generate a simple app icon at runtime (blue square with AI text)."""
    img = Image.new('RGBA', (64, 64), (0, 113, 227, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 18), "AI", fill='white')
    return img


def create_tray() -> pystray.Icon:
    """Create the system tray icon with Open/Exit menu."""

    def on_open(icon, item):
        """Restore or recreate the WebView window."""
        import webview
        windows = webview.windows
        if windows:
            windows[0].show()
            windows[0].restore()

    def on_exit(icon, item):
        """Stop tray and exit the process."""
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open / 打开", on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit / 退出", on_exit),
    )

    return pystray.Icon("agent-chat", _make_icon(), "AI Agent Chat", menu)
```

- [ ] **Step 4: Install new dependencies**

Run: `pip install pywebview pystray Pillow`

- [ ] **Step 5: Verify manual run**

Run: `python desktop/main.py`
Expected: WebView window opens, connects to the app, tray icon appears. Close window → hides to tray. Click tray "Open" → window restores.

- [ ] **Step 6: Commit**

```bash
git add desktop/
git commit -m "feat: add desktop entry point with WebView window and system tray"
```

---

### Task 3: Build script and packaging

**Files:**
- Create: `build.bat`
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
httpx>=0.27.0
aiosqlite>=0.20.0
jinja2>=3.1.0
cryptography>=43.0.0
pywebview>=5.0
pystray>=0.19
Pillow>=10.0

# dev
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Create build.bat**

```batch
@echo off
echo Building agent-chat Windows desktop app...

pyinstaller ^
  --onedir ^
  --name "agent-chat" ^
  --add-data "app;app" ^
  --add-data "app/templates;app/templates" ^
  --hidden-import uvicorn ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import pystray._win32 ^
  --hidden-import PIL._imaging ^
  --hidden-import jinja2 ^
  --hidden-import aiosqlite ^
  --hidden-import cryptography.fernet ^
  --collect-all jinja2 ^
  --noconsole ^
  desktop/main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful! Output: dist\agent-chat\
    echo Distribute the entire dist\agent-chat\ folder.
) else (
    echo.
    echo Build FAILED. Check errors above.
)

pause
```

- [ ] **Step 3: Run build.bat**

Run: `build.bat`
Expected: Output in `dist/agent-chat/`. Launch `dist/agent-chat/agent-chat.exe` — app starts with WebView window.

- [ ] **Step 4: Test packaged app**

Run: `dist/agent-chat/agent-chat.exe`
Expected:
- WebView window opens, connects to app, all pages work
- Close window → hides to tray
- `chat.db` and `.fernet_key` created alongside exe
- Settings → API keys → LLM Configs → Agents all functional
- Chat messaging works

- [ ] **Step 5: Commit**

```bash
git add build.bat requirements.txt
git commit -m "feat: add PyInstaller build script and update dependencies"
```

---

### Task 4: Final verification and cleanup

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: 44 PASS

- [ ] **Step 2: Verify source-mode desktop run**

Run: `python desktop/main.py`
Expected: WebView opens, all functionality works

- [ ] **Step 3: Verify packaged exe**

Run: `dist/agent-chat/agent-chat.exe`
Expected: Identical behavior to source-mode

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final verification of desktop packaging"
```
