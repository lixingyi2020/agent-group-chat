"""System tray icon for the desktop app."""

import sys
import pystray
from PIL import Image, ImageDraw

ICON_SIZE = 64
ICON_BG = (0, 113, 227, 255)  # Apple Blue
ICON_TEXT = "AI"
ICON_TEXT_POS = (14, 18)
ICON_TEXT_COLOR = "white"


def _make_icon() -> Image.Image:
    img = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), ICON_BG)
    d = ImageDraw.Draw(img)
    d.text(ICON_TEXT_POS, ICON_TEXT, fill=ICON_TEXT_COLOR)
    return img


def create_tray() -> pystray.Icon:

    def on_open(icon, _):
        import webview
        windows = webview.windows
        if windows:
            windows[0].show()
            windows[0].restore()

    def on_exit(icon, _):
        icon.stop()
        # Graceful: destroy WebView windows, unblock webview.start(), let main() return
        import webview
        for w in webview.windows:
            w.destroy()
        sys.exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open / 打开", on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit / 退出", on_exit),
    )

    return pystray.Icon("agent-chat", _make_icon(), "AI Agent Chat", menu)
