#!/bin/bash
# Run the Tier 3 workflow once without opening n8n, keeping the full run record.
#
#   ./run_headless.sh [run_dir] [phoneLookup] [maxSubstations]
#
#   run_dir         where the run record and lead CSV go (default output/run-YYYY-MM-DD)
#   phoneLookup     off | demo | sandbox | live   (default demo)
#   maxSubstations  0 = every Texas substation Line Watch has (default 0)
#
# Used by the weekly scheduled run; works on a Mac too. Uses its own throwaway n8n
# folder inside run_dir, so it never touches ~/.n8n or a running n8n.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="${1:-$HERE/output/run-$(date +%Y-%m-%d)}"
PHONE="${2:-demo}"
MAX="${3:-0}"
N8N_VERSION=1.123.85

N8N="${N8N_BIN:-}"
[ -z "$N8N" ] && [ -x "$HOME/.npm-global/bin/n8n" ] && N8N="$HOME/.npm-global/bin/n8n"
if [ -z "$N8N" ]; then
  CACHE="${K2_TIER3_N8N_CACHE:-$HOME/.cache/k2-tier3-n8n}"
  if [ ! -x "$CACHE/node_modules/.bin/n8n" ]; then
    echo "Installing n8n $N8N_VERSION into $CACHE (one time, a few minutes)..."
    mkdir -p "$CACHE"
    (cd "$CACHE" && npm install --no-audit --no-fund --loglevel=error "n8n@$N8N_VERSION" >/dev/null)
  fi
  N8N="$CACHE/node_modules/.bin/n8n"
fi

mkdir -p "$RUN_DIR"
RUN_DIR="$(cd "$RUN_DIR" && pwd)"
export N8N_USER_FOLDER="$RUN_DIR/.n8n" K2_TIER3_OUTPUT="$RUN_DIR" N8N_RESTRICT_FILE_ACCESS_TO="$RUN_DIR"
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false N8N_DIAGNOSTICS_ENABLED=false N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=false
export GENERIC_TIMEZONE=America/Chicago

python3 - "$HERE/workflows/line-watch-to-call-list.json" "$RUN_DIR/workflow.json" "$PHONE" "$MAX" <<'PY'
import json, sys
src, dst, phone, max_subs = sys.argv[1:5]
wf = json.load(open(src))
for n in wf["nodes"]:
    if n["name"] == "Settings":
        for a in n["parameters"]["assignments"]["assignments"]:
            if a["name"] == "phoneLookup": a["value"] = phone
            if a["name"] == "maxSubstations": a["value"] = int(max_subs)
            if a["name"] == "maxLeads": a["value"] = 5000
wf["id"], wf["name"] = "k2tier3headless1", "K2 Tier 3 (headless run)"
json.dump(wf, open(dst, "w"))
PY

"$N8N" import:workflow --input="$RUN_DIR/workflow.json" >/dev/null 2>&1
echo "Running the workflow (all substations take about 10 minutes)..."
rm -f "$RUN_DIR/run-record.json"
START=$(date +%s)
# The workflow saves its own compact run-record.json; n8n's printed log can be too big
# for a full run, so only its tail is kept for troubleshooting.
"$N8N" execute --id=k2tier3headless1 --rawOutput 2>&1 | tail -c 20000 > "$RUN_DIR/n8n.log" || true
if [ ! -s "$RUN_DIR/run-record.json" ]; then
  echo "n8n run failed, see $RUN_DIR/n8n.log"; exit 1
fi
echo "{\"seconds\": $(( $(date +%s) - START ))}" > "$RUN_DIR/timing.json"
rm -rf "$RUN_DIR/.n8n"
echo "Done: $RUN_DIR"
ls "$RUN_DIR"/*.csv
