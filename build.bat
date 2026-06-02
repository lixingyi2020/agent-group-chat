@echo off
echo Building agent-chat Windows desktop app...

python -m PyInstaller ^
  --onedir ^
  --name "agent-chat" ^
  --add-data "app;app" ^
  --hidden-import fastapi ^
  --hidden-import starlette ^
  --hidden-import pydantic ^
  --hidden-import uvicorn ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import anyio ^
  --hidden-import httpx ^
  --hidden-import aiosqlite ^
  --hidden-import pystray._win32 ^
  --hidden-import PIL._imaging ^
  --hidden-import cryptography.fernet ^
  --collect-all fastapi ^
  --collect-all starlette ^
  --collect-all pydantic ^
  --collect-all anyio ^
  --collect-all httpx ^
  --collect-all jinja2 ^
  --hidden-import app ^
  --hidden-import app.main ^
  --hidden-import app.crypto ^
  --hidden-import app.orchestrator ^
  --hidden-import app.templates ^
  --hidden-import app.db ^
  --hidden-import app.db.models ^
  --hidden-import app.db.migrations ^
  --hidden-import app.db.queries ^
  --hidden-import app.i18n ^
  --hidden-import app.i18n.en ^
  --hidden-import app.i18n.zh ^
  --hidden-import app.providers ^
  --hidden-import app.providers.base ^
  --hidden-import app.providers.openai ^
  --hidden-import app.providers.anthropic ^
  --hidden-import app.providers.google ^
  --hidden-import app.routes ^
  --hidden-import app.routes.pages ^
  --hidden-import app.routes.fragments ^
  --hidden-import app.routes.stream ^
  --hidden-import app.routes.settings ^
  --collect-all cryptography ^
  desktop/main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful! Output: dist\agent-chat\
    echo Distribute the entire dist\agent-chat\ folder.
) else (
    echo.
    echo Build FAILED. Check errors above.
)

pause
