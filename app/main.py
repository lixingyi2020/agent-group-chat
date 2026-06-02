import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db.migrations import migrate
from app.db.queries import DB_PATH
from app.routes import pages, fragments, stream, settings

# Resolve static directory: sys._MEIPASS is the PyInstaller bundle root
if getattr(sys, 'frozen', False):
    _static_dir = os.path.join(sys._MEIPASS, "static")  # pyright: ignore[reportAny]
else:
    _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _static_dir = os.path.join(_base, "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await migrate(DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(pages.router)
app.include_router(fragments.router)
app.include_router(stream.router)
app.include_router(settings.router)
