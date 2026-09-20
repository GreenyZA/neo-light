#!/bin/bash
# Bridge script to sync files between local and server
SERVER_USER=warpuppy
SERVER_IP=192.168.1.10

if [ -z "$1" ]; then
  echo "Usage: $0 [local_file] [server_file]", exit 1
fi

LOCAL_FILE="$1"
SERVER_FILE="${2:-$LOCAL_FILE}"

# Sync to server
echo "Syncing $LOCAL_FILE to server as $SERVER_FILE..."
scp "$LOCAL_FILE" "${SERVER_USER}@${SERVER_IP}:$SERVER_FILE"

# Also verify sync
echo "Sync complete. Verifying..."
ssh "${SERVER_USER}@${SERVER_IP}" "test -f $SERVER_FILE && echo 'File exists on server' || echo 'MISSING on server'"