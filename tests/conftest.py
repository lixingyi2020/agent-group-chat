import pytest_asyncio
import tempfile
import os
from app.db.migrations import migrate
from app.db import queries


@pytest_asyncio.fixture
async def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    queries.DB_PATH = path
    await migrate(path)
    yield
    queries.DB_PATH = "chat.db"
    try:
        os.unlink(path)
    except OSError:
        pass
