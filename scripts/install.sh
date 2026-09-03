#!/usr/bin/env bash
# Install Plaud Plus MCP onto this machine and optionally wire Grok.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if command -v uv >/dev/null 2>&1; then
  uv tool install --editable "$ROOT"
else
  python3 -m pip install --user --editable "$ROOT"
fi

echo "Installed plaud-plus and plaud-plus-mcp."
echo "Sign in:  plaud-plus login --desktop     # macOS Plaud Desktop"
echo "     or:  plaud-plus login --email you@example.com"
echo "Check:    plaud-plus doctor"

if command -v grok >/dev/null 2>&1; then
  grok mcp add plaud-plus -- plaud-plus-mcp || true
  echo "Grok: grok mcp add plaud-plus -- plaud-plus-mcp (done or already present)"
fi
if command -v claude >/dev/null 2>&1; then
  echo "Claude: claude mcp add plaud-plus -- plaud-plus-mcp"
fi
