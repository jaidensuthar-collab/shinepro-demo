#!/bin/bash
# Keep the workflow the same on every Mac. GitHub holds the master copy.
#
#   ./sync.sh load    get the latest from GitHub and load it into this Mac's n8n
#   ./sync.sh save    copy this Mac's n8n version into the repo and push it to GitHub
#   ./sync.sh key     store the Tracerfy API key in this Mac's n8n (never in git)
#
# Run "save" after editing in n8n, and "load" before editing on the other Mac.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/n8n-env.sh"
cd "$HERE"

case "$1" in
  load|load-only)
    if [ "$1" = load ]; then
      if ! git diff --quiet -- "$WORKFLOW_FILE"; then
        echo "The workflow file has unsaved local changes. Commit them or run ./sync.sh save first."
        exit 1
      fi
      git pull --ff-only
    fi
    "$N8N" import:workflow --input="$WORKFLOW_FILE"
    echo "Loaded into n8n. Refresh the browser tab if n8n is open."
    ;;
  save)
    tmp="$(mktemp)"
    "$N8N" export:workflow --id="$WORKFLOW_ID" --output="$tmp" >/dev/null
    # Keep only the parts that matter, so diffs stay readable.
    python3 - "$tmp" "$WORKFLOW_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d = d[0] if isinstance(d, list) else d
keep = {k: d[k] for k in ("name", "nodes", "connections", "settings", "meta", "id") if k in d}
keep.update({"active": False, "pinData": {}, "tags": []})
json.dump(keep, open(sys.argv[2], "w"), indent=2)
PY
    rm -f "$tmp"
    if git diff --quiet -- "$WORKFLOW_FILE"; then
      echo "No changes to save."
      exit 0
    fi
    git add "$WORKFLOW_FILE"
    git commit -m "${2:-Update Tier 3 workflow from $(hostname -s)}"
    git push
    echo "Saved and pushed. Run ./sync.sh load on the other Mac."
    ;;
  key)
    # The workflow looks for a credential with this fixed id, so it works on every Mac.
    read -r -s -p "Paste the Tracerfy API key (or type sandbox for the free test server): " KEY; echo
    [ "$KEY" = sandbox ] && KEY=sandbox_test_token
    umask 077
    tmp="$(mktemp)"
    python3 - "$tmp" "$KEY" <<'PY'
import json, sys
json.dump([{"id": "k2Tier3Tracerfy", "name": "Tracerfy API", "type": "httpHeaderAuth",
            "data": {"name": "Authorization", "value": "Bearer " + sys.argv[2]}}], open(sys.argv[1], "w"))
PY
    "$N8N" import:credentials --input="$tmp" >/dev/null
    rm -f "$tmp"
    echo "Saved in this Mac's n8n as 'Tracerfy API'."
    ;;
  *)
    sed -n '2,8p' "$0"
    exit 1
    ;;
esac
