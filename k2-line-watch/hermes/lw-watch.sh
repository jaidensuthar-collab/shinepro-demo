#!/usr/bin/env bash
# K2 Line Watch signal check for a Hermes no-agent cron job (no AI model, no tokens).
# Copy this file to ~/.hermes/scripts/ and set LW_DIR to the k2-line-watch folder.
# Prints nothing when nothing is new (Hermes treats empty output as a silent tick);
# otherwise prints the summary, which Hermes delivers verbatim (Telegram, Slack, email...).
set -euo pipefail
LW_DIR="${LW_DIR:-$HOME/shinepro-demo/k2-line-watch}"
cd "$LW_DIR"
git pull -q --ff-only >/dev/null 2>&1 || true
python3 lw.py watch --quiet
if [ -n "$(git status --porcelain -- state)" ]; then
  git add state && git commit -q -m "Line Watch check $(date +%Y-%m-%d)" && git push -q >/dev/null 2>&1 || true
fi
