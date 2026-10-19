#!/bin/bash
# Start the K2 Tier 3 n8n on http://localhost:5679
#
# Uses its own folder (k2-line-watch/landowners/.n8n-local) and port 5679 so it never touches another
# n8n on this Mac (~/.n8n, port 5678). Stop it with Ctrl+C.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/n8n-env.sh"

if [ ! -x "$N8N" ]; then
  echo "n8n not found at $N8N"
  echo "Install it once with:  npm install --prefix ~/.npm-global n8n@$N8N_VERSION"
  exit 1
fi
if lsof -iTCP:"$N8N_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $N8N_PORT is already in use. Is the Tier 3 n8n already running?"
  exit 1
fi
if [ ! -d "$N8N_USER_FOLDER/.n8n" ]; then
  echo "First start: loading the workflow from the repo."
  "$HERE/sync.sh" load-only
fi
echo "Open http://localhost:$N8N_PORT  (lead CSVs go to $K2_TIER3_OUTPUT)"
exec "$N8N" start
