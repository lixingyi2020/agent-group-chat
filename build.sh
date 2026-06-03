#!/bin/bash
echo "Building agent-chat macOS desktop app..."

python -m PyInstaller \
  --onedir \
  --name "agent-chat" \
  --add-data "app:app" \
  --add-data "static:static" \
  --hidden-import fastapi \
  --hidden-import starlette \
  --hidden-import pydantic \
  --hidden-import uvicorn \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import anyio \
  --hidden-import httpx \
  --hidden-import aiosqlite \
  --hidden-import PIL._imaging \
  --hidden-import cryptography.fernet \
  --collect-all fastapi \
  --collect-all starlette \
  --collect-all pydantic \
  --collect-all anyio \
  --collect-all httpx \
  --collect-all jinja2 \
  --collect-all cryptography \
  --hidden-import app \
  --hidden-import app.utils \
  --hidden-import app.main \
  --hidden-import app.crypto \
  --hidden-import app.orchestrator \
  --hidden-import app.templates \
  --hidden-import app.db \
  --hidden-import app.db.models \
  --hidden-import app.db.migrations \
  --hidden-import app.db.queries \
  --hidden-import app.i18n \
  --hidden-import app.i18n.en \
  --hidden-import app.i18n.zh \
  --hidden-import app.providers \
  --hidden-import app.providers.base \
  --hidden-import app.providers.openai \
  --hidden-import app.providers.anthropic \
  --hidden-import app.providers.google \
  --hidden-import app.routes \
  --hidden-import app.routes.pages \
  --hidden-import app.routes.fragments \
  --hidden-import app.routes.stream \
  --hidden-import app.routes.settings \
  --windowed \
  desktop/main.py

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful! Output: dist/agent-chat/"
else
    echo ""
    echo "Build FAILED. Check errors above."
fi
