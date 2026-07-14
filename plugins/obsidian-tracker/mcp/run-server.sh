#!/bin/sh
# MCP server launcher: ensures deps + dist/ on first run so a fresh plugin
# install works without a manual `npm install && npm run build`.
# dist/ ships prebuilt but node_modules does NOT, and dist/index.js imports
# @modelcontextprotocol/sdk at runtime — so deps must exist even when dist/
# already does. Check the two independently, else a prebuilt-dist install
# skips `npm install` and crashes with ERR_MODULE_NOT_FOUND (MCP -32000).
# All build output goes to stderr — stdout is the MCP stdio channel.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -d node_modules ]; then
  echo "obsidian-tracker: node_modules missing, installing deps..." >&2
  npm ci --silent >&2 || npm install --silent >&2 || {
    echo "obsidian-tracker: npm install failed" >&2
    exit 1
  }
fi

if [ ! -f dist/index.js ]; then
  echo "obsidian-tracker: dist/ missing, building MCP server..." >&2
  npm run build --silent >&2 || {
    echo "obsidian-tracker: build failed" >&2
    exit 1
  }
fi

exec node dist/index.js
