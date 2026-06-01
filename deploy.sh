#!/bin/bash
set -e

echo "🔨 Building project..."
pnpm run build

echo "📦 Preparing files for deployment..."

# Create temporary directory for deploy
TEMP_DIR=$(mktemp -d)
PLUGIN_DIR="$TEMP_DIR/deckray"

mkdir -p "$PLUGIN_DIR"

# Required for import HTTPS server: backend/src/*.py (cert_utils, import_server, …), backend/static (import.html, import.css)
if [ ! -d backend/static ]; then
  echo "❌ backend/static missing (import page). Aborting."
  exit 1
fi

echo "📋 Copying files..."
cp -r dist "$PLUGIN_DIR/"
cp package.json plugin.json main.py LICENSE "$PLUGIN_DIR/"
mkdir -p "$PLUGIN_DIR/backend/src"
cp backend/__init__.py "$PLUGIN_DIR/backend/"
cp backend/src/__init__.py "$PLUGIN_DIR/backend/src/"
cp backend/src/*.py "$PLUGIN_DIR/backend/src/"
cp -r backend/static "$PLUGIN_DIR/backend/"

echo "📋 Copying binaries..."
if [ -d backend/out ] && [ "$(ls -A backend/out 2>/dev/null)" ]; then
  mkdir -p "$PLUGIN_DIR/bin"
  cp -r backend/out/* "$PLUGIN_DIR/bin/"
fi
# Allow overriding host via env variables
DECK_HOST="${DECK_HOST:-steamdeck}"

RSYNC_PATH=""
if [ "$DECK_USE_SUDO" = "1" ]; then
  if [ -n "$DECK_PASS" ]; then
    RSYNC_PATH="bash -c 'echo $DECK_PASS | sudo -S rsync \"\$@\"' --"
  else
    RSYNC_PATH="sudo rsync"
  fi
fi

echo "🚀 Deploying to $DECK_HOST..."
SSH_CMD="ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=10 -o ServerAliveCountMax=3"
if [ -n "$DECK_PASS" ]; then
  SSH_CMD="sshpass -p $DECK_PASS $SSH_CMD"
fi

if [ "$DECK_USE_SUDO" = "1" ]; then
  echo "📤 Syncing files to remote temporary directory..."
  rsync -avz --no-owner --no-group --delete --progress \
    --timeout=30 \
    --partial \
    -e "$SSH_CMD" \
    "$PLUGIN_DIR/" "$DECK_HOST:/tmp/deckray-deploy/"

  echo "🛡️  Moving files to plugin directory with sudo..."
  if [ -n "$DECK_PASS" ]; then
    $SSH_CMD "$DECK_HOST" "echo '$DECK_PASS' | sudo -S mkdir -p /home/deck/homebrew/plugins && echo '$DECK_PASS' | sudo -S rm -rf /home/deck/homebrew/plugins/deckray && echo '$DECK_PASS' | sudo -S cp -r /tmp/deckray-deploy /home/deck/homebrew/plugins/deckray && echo '$DECK_PASS' | sudo -S rm -rf /tmp/deckray-deploy"
  else
    $SSH_CMD "$DECK_HOST" "sudo mkdir -p /home/deck/homebrew/plugins && sudo rm -rf /home/deck/homebrew/plugins/deckray && sudo cp -r /tmp/deckray-deploy /home/deck/homebrew/plugins/deckray && sudo rm -rf /tmp/deckray-deploy"
  fi
else
  echo "📤 Syncing files directly..."
  rsync -avz --no-owner --no-group --delete --progress \
    --timeout=30 \
    --partial \
    -e "$SSH_CMD" \
    "$PLUGIN_DIR/" "$DECK_HOST:~/homebrew/plugins/deckray/"
fi
echo "✅ Deployment complete!"
rm -rf "$TEMP_DIR"

