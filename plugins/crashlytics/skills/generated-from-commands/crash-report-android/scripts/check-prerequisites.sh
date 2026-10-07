#!/bin/bash
# Check prerequisites for Crashlytics plugin
echo "=== Crashlytics Prerequisites ==="

# 1. Node.js
if command -v node &>/dev/null; then
  echo "OK node $(node --version)"
else
  echo "MISSING node"
fi

# 2. firebase-tools (check binary exists, don't launch Node.js)
if command -v firebase &>/dev/null; then
  echo "OK firebase"
else
  echo "MISSING firebase"
fi

# 3. Firebase auth (token file with valid refresh_token)
TOKEN_FILE="$HOME/.config/configstore/firebase-tools.json"
if [ -f "$TOKEN_FILE" ] && grep -q "refresh_token" "$TOKEN_FILE" 2>/dev/null; then
  echo "OK firebase-auth"
elif [ -f "$TOKEN_FILE" ]; then
  echo "MISSING firebase-auth (token file exists but no refresh_token)"
else
  echo "MISSING firebase-auth"
fi

# 4. python3
if command -v python3 &>/dev/null; then
  echo "OK python3 $(python3 --version 2>&1)"
else
  echo "MISSING python3"
fi
