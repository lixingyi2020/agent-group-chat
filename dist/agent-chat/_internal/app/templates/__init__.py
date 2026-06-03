import sys
import os
from fastapi.templating import Jinja2Templates

if getattr(sys, 'frozen', False):
    _template_dir = os.path.join(sys._MEIPASS, "app", "templates")  # pyright: ignore[reportAny]
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _template_dir = os.path.join(_BASE_DIR, "app", "templates")

templates = Jinja2Templates(directory=_template_dir)
