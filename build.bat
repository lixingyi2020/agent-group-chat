@echo off
echo Building agent-chat Windows desktop app...

pyinstaller ^
  --onedir ^
  --name "agent-chat" ^
  --add-data "app;app" ^
  --add-data "app/templates;app/templates" ^
  --hidden-import uvicorn ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import pystray._win32 ^
  --hidden-import PIL._imaging ^
  --hidden-import jinja2 ^
  --hidden-import aiosqlite ^
  --hidden-import cryptography.fernet ^
  --collect-all jinja2 ^
  --noconsole ^
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
