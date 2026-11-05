---
name: k2-texas-lines
description: Refresh K2 Line Watch's Texas lines list (every ERCOT line built in the last 3 years or due in the next 5, in five stages, with substations and developers) when ERCOT's TPIT report or Oncor's CCN viewer changes, run the data checks, and summarize what changed. Use weekly (Monday) and after a Line Watch check finds a new Texas line.
version: 1.0.0
metadata:
  hermes:
    tags: [k2-renew, transmission, gis]
    category: k2
---

# Texas lines list refresh

## When to use
Every Monday, when someone asks for the Texas list to be refreshed, or when a new ERCOT TPIT edition is
posted (usually monthly).

## Procedure
1. In the `k2-line-watch` folder, `git pull --ff-only`, then run `python3 lw.py texas`.
2. Read the exit code:
   * `0`: done. Either nothing changed (no rebuild) or the list was rebuilt and every data check passed.
   * `1`: a data check failed or the build broke. Do not publish. If the cause is clearly a bug in
     `data/build_catalog.py`, fix it and rerun; otherwise report the failing check and stop.
   * `3`: a new TPIT edition was downloaded to `data/sources/`. Point `data/build_catalog.py` (default
     TPIT path near the end of the file and the "October 1, 2026 update" source text) and
     `data/check_catalog.py` (the edition list near the top) at the new file and month, keep the older
     editions, then run `python3 lw.py texas --force`. Use a strong model for this step.
3. To force a rebuild (for example after editing a project card in `state/projects/`), run
   `python3 lw.py texas --force`.
4. If the list changed and the checks passed: run `python3 lw.py export-page`, commit `data/`, `web/`
   and `state/`, and push. Inside Claude, also republish the Line Watch page (see `../../README.md`).
5. Reply with: lines added (especially 345 kV and 765 kV), stage changes, new or expanding substations,
   the data-check result and anything listed to review.

## Pitfalls
* Never commit landowner data; this job doesn't need it.
* Never guess substation coordinates. A line without a public location is "needs a card".
* Lines move between stages by date alone (for example "approved" to "in construction" once the planned
  in-service month passes); say when a change is an estimate.

## Verification
`python3 data/check_catalog.py` ends with "6 of 6 checks passed" (or more checks, all passed).
