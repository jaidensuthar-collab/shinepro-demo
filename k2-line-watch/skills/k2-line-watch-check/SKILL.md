---
name: k2-line-watch-check
description: Run the K2 Line Watch signal check (new Texas transmission line filings, ERCOT planning documents, utility project pages, Oncor's CCN map, news), store new signals, sync them to the K2 Watch Google Sheet when a Sheets tool is available, and report High signals. Use twice a day (7am and 5pm Central) or when asked "check Line Watch".
version: 1.0.0
metadata:
  hermes:
    tags: [k2-renew, transmission, monitoring]
    category: k2
    config:
      - key: k2.sheet_id
        description: "Google Sheet ID of the K2 Line Watch sheet (tab 'K2 Watch'). Ask Jaiden; never commit it."
        default: ""
        prompt: "K2 Line Watch Google Sheet ID (leave blank to skip the sheet sync)"
---

# K2 Line Watch check

## When to use
Twice a day, about 7am and 5pm US Central, or whenever someone asks for a Line Watch check.

## Procedure
1. Work in the `k2-line-watch` folder of the shinepro-demo repository (branch
   `claude/vibrant-euler-urtmp2`). Pull first: `git pull --ff-only`.
2. Run `python3 lw.py watch`. It checks every source, adds new K2 signals to `state/` and prints a
   Markdown summary. Exit code 0 is success even when nothing is new.
3. If the summary lists new signals and a Google Sheets tool is available (for example Composio's
   Google Sheets tools) and `k2.sheet_id` is set:
   * Append the rows in `state/runs/<time>/rows.json` (path printed in the summary) unchanged to
     `'K2 Watch'!A:M`. kV values start with an apostrophe on purpose, so they stay text.
   * Re-read column L and confirm each new ID appears exactly once.
4. If you are running inside Claude with the Line Watch page's database tools, batch-write
   `state/runs/<time>/db/writes.json` and update `meta/status` (see `../../README.md`, "How a scheduled
   run works"). Anywhere else, run `python3 lw.py export-page`.
5. Commit the new memory: `git add state && git commit -m "Line Watch check <date>"` and push, so the
   next run (on any machine or agent) starts from it.
6. Reply in a few lines: the number of new K2 signals and, for each High one, what happened, kV, state
   and link. If a new High signal is a 345 kV or larger Texas line, check whether its name is in
   `web/data/texas-lines.json`; if it is not, say so ("needs a card"). If nothing is new, reply with one
   line.

## Pitfalls
* Never edit or delete `state/seen.txt` by hand except to add IDs; losing it re-reports every old signal.
* A source that fails (for example ERCOT answering 403) is a report line, not a reason to stop.
* The same news story can come back under a reworded headline with a new ID; call it a repeat.
* Never send email or change sharing as part of this job.

## Verification
`python3 lw.py status` shows the new last-check time, and `git log -1 -- state` shows the commit.
