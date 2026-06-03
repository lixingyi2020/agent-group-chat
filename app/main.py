from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db.migrations import migrate
from app.db.queries import DB_PATH
from app.routes import pages, fragments, stream, settings
from app.utils import get_bundle_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    await migrate(DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=get_bundle_path("static")), name="static")

app.include_router(pages.router)
app.include_router(fragments.router)
app.include_router(stream.router)
app.include_router(settings.router)
