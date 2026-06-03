# macOS Desktop App — Design Spec

> **Status:** Approved | **Date:** 2026-06-03

**Goal:** Add macOS desktop app support alongside the existing Windows desktop app, reusing the same `desktop/main.py` entry point and sharing all cross-platform code.

## Platform Differences

| Aspect | Windows | macOS |
|--------|---------|-------|
| WebView backend | `edgechromium` (Edge WebView2) | `None` (native WKWebView via Cocoa) |
| Build script | `build.bat` | `build_mac.sh` |
| Console | `--noconsole` flag | `--windowed` flag (equivalent) |
| Output | `dist/agent-chat/` portable folder | Same portable folder |

## Changes

### `desktop/main.py` — platform-aware GUI backend

```python
import platform
GUI_BACKEND = 'edgechromium' if platform.system() == 'Windows' else None
```

`None` on macOS makes pywebview use the default Cocoa/WKWebView backend.

### `build_mac.sh` — new build script

Identical to `build.bat` but:
- Shell syntax instead of batch
- `python3` instead of `python`
- `--windowed` instead of `--noconsole`
- Unix-style line endings

### No other changes

All existing code (`app/*`, `desktop/tray.py`, `build.bat`) is unchanged and platform-agnostic.
