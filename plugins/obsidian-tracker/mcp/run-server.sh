#!/bin/sh
# MCP server launcher: builds dist/ on first run so a fresh plugin install
# works without a manual `npm install && npm run build`.
# All build output goes to stderr — stdout is the MCP stdio channel.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -f dist/index.js ]; then
  echo "obsidian-tracker: dist/ missing, building MCP server..." >&2
  if [ ! -d node_modules ]; then
    npm ci --silent >&2 || npm install --silent >&2 || {
      echo "obsidian-tracker: npm install failed" >&2
      exit 1
    }
  fi
  npm run build --silent >&2 || {
    echo "obsidian-tracker: build failed" >&2
    exit 1
  }
fi

exec node dist/index.js
