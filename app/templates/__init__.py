from fastapi.templating import Jinja2Templates
from app.utils import get_bundle_path

templates = Jinja2Templates(directory=get_bundle_path("app/templates"))
