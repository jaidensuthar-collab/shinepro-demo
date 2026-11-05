# Running K2 Line Watch on Hermes Agent (or any other agent)

Everything Line Watch does is a plain command (`lw.py`) plus a skill file in `skills/` written in the open
SKILL.md format (agentskills.io), which Hermes, Claude Code and other agents read. Nothing is tied to one
AI model or one company, so moving it is mostly configuration.

## The pieces

| Piece | What it is | Used for |
| --- | --- | --- |
| Hermes Agent (Nous Research) | the always-on "employee": memory, skills, cron jobs, chat by Telegram/Slack | running the jobs on a schedule and talking to you |
| OpenRouter (or Nous Portal) | one key for hundreds of models | a cheap model for routine jobs, a strong one for code changes |
| Composio | logins to Gmail, Google Sheets, Slack... for agents (MCP) | the sheet sync and the inbox watcher |
| `lw.py` + `state/` | the Line Watch jobs and their memory | the actual work, no model needed |

## Step by step (Hermes Cloud, nothing installed on the Mac mini)

1. Create a Nous Portal account and deploy one Hermes Cloud agent (it needs a paid plan, from $20 a
   month, or at least $2 of pay-as-you-go credits). Pick a cheap default model (for example DeepSeek or
   Claude Haiku via OpenRouter).
2. In a chat with the agent, have it clone the repository:
   `git clone -b claude/vibrant-euler-urtmp2 https://github.com/jaidensuthar-collab/shinepro-demo ~/shinepro-demo`
   and check that `python3 ~/shinepro-demo/k2-line-watch/lw.py status` prints a status line. Pushing
   needs a GitHub token with access to the repository; add it as a secret, never in a file.
3. Add the Line Watch skills to `~/.hermes/config.yaml`:
   ```yaml
   skills:
     external_dirs:
       - ~/shinepro-demo/k2-line-watch/skills
   ```
   Then `hermes skills list` should show `k2-line-watch-check`, `k2-texas-lines` and `k2-inbox-watch`.
   The check skill asks once for the K2 Watch sheet ID (kept in your Hermes config, not in git).
4. Connect Telegram (or Slack) so results reach your phone.
5. Schedule the jobs. Hermes accepts natural language or cron expressions; confirm the times with
   `hermes cron list`, since they follow the agent machine's clock (Hermes Cloud may run in UTC: 7am
   Central is 13:00 UTC in winter, 12:00 in summer).
   First set `LW` to the absolute folder path, for example `LW=$(cd ~/shinepro-demo/k2-line-watch && pwd)`
   (`--workdir` must be absolute; it also loads `AGENTS.md`).
   * Signal watch, no AI model at all (cheapest): copy `hermes/lw-watch.sh` to `~/.hermes/scripts/`,
     set `LW_DIR` in it if the repo is elsewhere, then
     `hermes cron create "0 7,17 * * *" --no-agent --script lw-watch.sh --deliver telegram --name line-watch`
     It is silent when nothing is new and sends the summary when something is.
   * Signal watch with the sheet sync (an agent run, cheap model):
     `hermes cron create "0 7,17 * * *" "Run the Line Watch check and report." --skill k2-line-watch-check --workdir $LW --deliver telegram --name line-watch-sync`
     Use one of the two watch jobs, not both.
   * Texas list, weekly:
     `hermes cron create "every monday 9am" "Refresh the Texas lines list." --skill k2-texas-lines --workdir $LW --deliver telegram --name texas-lines`
   * Inbox watch (needs Gmail through Composio; drafts only):
     `hermes cron create "every 1h" "Check for new K2 replies." --skill k2-inbox-watch --workdir $LW --deliver telegram --name k2-inbox`
6. Composio: connect only what a job needs (Google Sheets for the sync, Gmail for the inbox). Keep
   K2's own accounts out unless John or Richard agree.

## What stays Claude-only today, and the replacement

| Today (Claude) | Outside Claude |
| --- | --- |
| The live Line Watch page and its database | `python3 lw.py export-page`, then serve `web/` from any static host (GitHub Pages works). The page detects that it is outside Claude and reads `web/data/line-watch-state.json`; downloads become plain links. |
| The page's "Ask" box and research questions | Ask the agent in Telegram or Slack instead. |
| Claude scheduled tasks | Hermes cron jobs above (or GitHub Actions / crontab running `lw.py`). |
| Claude's Gmail and Sheets connectors | Composio (or any Gmail/Sheets MCP server). |

## Bringing the old signals along

`state/seen.txt` already holds every signal ID reported so far (Nov 4, 2026), so nothing old comes back
as new. To copy the full signal history too, download the K2 Watch tab as CSV (File > Download > CSV)
and run `python3 lw.py import-sheet ~/Downloads/<file>.csv`. Do not commit that CSV itself.

## Other agents

* Claude Code: copy or link `skills/*` into `.claude/skills/` and run the same commands.
* Any agent that reads SKILL.md files (OpenClaw and others): point it at `skills/`.
* No agent at all: `crontab` with `cd .../k2-line-watch && python3 lw.py watch --quiet`.

## Running on the Mac mini instead

Possible, but ask Jaiden first: it installs a long-running service. Keep away from ports 5678 (n8n),
8477 (helper) and 9222 (Opera), and never touch `~/.n8n`, `~/Projects/moto-scout` or `~/.config/moto-scout`.
