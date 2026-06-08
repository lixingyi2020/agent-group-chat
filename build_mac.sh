#!/bin/bash
set -e

echo "Building agent-chat macOS desktop app..."

python3 -m PyInstaller agent-chat.spec

echo ""
echo "Build complete. Output: dist/agent-chat/"
echo "App bundle: dist/agent-chat.app"
echo "Run: open dist/agent-chat.app"
