import os
from fastapi.templating import Jinja2Templates

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

templates = Jinja2Templates(directory=os.path.join(_BASE_DIR, "app", "templates"))
