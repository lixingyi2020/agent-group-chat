# macOS Desktop App — Design Spec

> **Status:** Approved | **Date:** 2026-06-03

**Goal:** Adapt the existing Windows desktop app code to also build and run on macOS, reusing all existing cross-platform Python code.

**Context:** pywebview, pystray, and PyInstaller all support macOS. Only ~10 lines need to change.

---

## Changes

### 1. `desktop/main.py` — platform-aware GUI backend

```python
import platform

if platform.system() == 'Windows':
    GUI_BACKEND = 'edgechromium'
else:
    GUI_BACKEND = 'cocoa'
```

Guard the `ctypes.windll` exception handler with `platform.system() == 'Windows'`.

### 2. `build.sh` — new macOS build script

Same as `build.bat` but using Unix shell syntax and `--windowed` (macOS equivalent of `--noconsole`).

### 3. `requirements.txt` — no changes needed

`pywebview` and `pystray` already support macOS via `pyobjc` (auto-installed as optional dependency).

---

## Files

| File | Change |
|------|--------|
| `desktop/main.py` | Platform-aware `GUI_BACKEND`, guard Windows-only code |
| `build.sh` | New: macOS PyInstaller build script |

## Build (on Mac)

```bash
git clone https://github.com/lixingyi2020/agent-group-chat.git
cd agent-group-chat
pip install -r requirements.txt pyobjc
bash build.sh
# Output: dist/agent-chat/agent-chat
```
