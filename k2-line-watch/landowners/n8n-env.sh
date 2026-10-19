# Settings shared by start-n8n.sh and sync.sh. Same on every Mac.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export N8N_VERSION=1.123.85                       # runs on Node 20 to 24
export N8N="${N8N_BIN:-$HOME/.npm-global/bin/n8n}"
export N8N_USER_FOLDER="$HERE/.n8n-local"         # never ~/.n8n
export N8N_PORT=5679                              # 5678 belongs to another project
export K2_TIER3_OUTPUT="$HERE/output"             # lead CSVs land here (not in git)
export N8N_RESTRICT_FILE_ACCESS_TO="$K2_TIER3_OUTPUT"
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false         # the workflow reads K2_TIER3_OUTPUT
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_PERSONALIZATION_ENABLED=false
export N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
export GENERIC_TIMEZONE=America/Chicago
export WORKFLOW_FILE="$HERE/workflows/line-watch-to-call-list.json"
export WORKFLOW_ID=k2tier3linewatch
mkdir -p "$K2_TIER3_OUTPUT"
