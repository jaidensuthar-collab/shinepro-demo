# K2 Line Watch

One project: the **line monitor** (this folder) finds new high-voltage lines early, and the
**landowner search** (`landowners/`, an n8n workflow) finds the landowners near each line's end
substations every Monday. Both feed one page, **K2 Line Watch**
(https://claude.ai/artifact/FCARNQ1KQBr5r5DX9V6XfG): the watch list, a Landowners tab, utility plans
and help. Texas today; the landowner search is built to add other states (see `landowners/README.md`).

## Line monitor

Finds new Texas transmission lines while they are still early, and lists them in the
**Monitor Feed** tab of the *K2 Transmission Intel Plan* Google Sheet.

It watches the public signals that come before a route is approved, earliest first
(see the FIRST TO KNOW section on the sheet's Signal Ladder tab):

| Step | Source | What a new item means |
|---|---|---|
| 2 | ERCOT Regional Planning Group (RPG) meeting pages | A utility submitted a project, or ERCOT posted its scope or recommendation. Names the end substations, often 1 to 2 years before a route filing. |
| 3 | Oncor, AEP Texas, LCRA and CPS Energy project-list pages | A new project page usually means open houses with preliminary route links are coming, 4 to 9 months before filing. |
| 3+ | Google News searches (765 kV, open houses, routes, CenterPoint, ERCOT) | Local press and landowner news, often the first public word of an open house. Covers other states too. |
| 4-5 | PUCT Interchange new electric cases | A utility opened a case to amend its CCN for a transmission line: a route filing is starting or has just been made. |
| 5-6 | New filings inside every route case already in the feed, plus Docket 59475 | Orders, approvals, settlements, rehearing motions and the utility's own route filings. Letters, protests and procedural paperwork are skipped. Works like PUCT's email alerts without an account. |

Every signal gets a **Priority**: High for 345 kV and above (or 765 kV in the title),
Low for rebuilds, small lines and routine ERCOT status updates, Medium otherwise.

## Run it

Python 3.9 or newer. Nothing to install.

```
python3 monitor.py                                   # everything found right now
python3 monitor.py --seen seen.txt                   # only what is not in seen.txt
python3 monitor.py --seen seen.txt --rows rows.json  # also write sheet rows for the new items
python3 -m unittest test_monitor.py                  # offline parser tests
```

Useful options: `--only puct|rpg|util|news|dockets` to check one source, `--puct-days 30` for
how far back to look for new PUCT cases, `--watch-days 4` and `--news-days 3` for the filing and
news windows, `--watch 59475` to follow another case, `--rpg-seed URL` to point at a recent RPG
meeting page.

## What counts as "K2 cares"

`k2filter.py` keeps a signal only if it points at a new high-voltage line whose land is still in
play, and rewrites it in plain English (what happened, where, why K2 cares, what to do next).
It drops:

* work on existing lines: rebuilds, reconductoring, relocations, pole or cable swaps
* anything under 138 kV, and generator hookup lines (wind, solar, POI, collector)
* ERCOT planning documents under 345 kV, scope documents and meeting admin
* utility project pages under 345 kV, or pages that say the line is already energized
* routine case paperwork (procedural orders, counsel changes, discovery); route maps,
  amended applications and errata stay
* news that doesn't name a specific line or route

`--all` turns the filter off. On the first full run it kept 51 of 175 signals.

## Where results go

* **K2 Watch tab** in the sheet: one plain-English row per signal (`--rows`). Column L is the ID.
* **K2 Line Watch webpage** (https://claude.ai/artifact/FCARNQ1KQBr5r5DX9V6XfG): reads its own
  database. `signals` holds every kept signal (`--db-dir` writes them ready for a batch
  write), `projects` holds one card per line (seeded from `data/projects.json`, built by
  `data/build_projects.py`), `meta/status` has the last check, and `research` holds questions
  people asked the page's assistant that need a web lookup.
* **Maps**: each project card draws its study-area counties and end substations, and links to
  geojson.io with the same shapes. Pins were researched from utility pages, PUC filings and
  OpenStreetMap; `data/merge_geo.py` checks each pin sits in the county it names and writes
  `data/geo.json`. County outlines are `web/counties.json` (built by `data/build_counties.py`).
* **GIS export**: `data/export_gis.py` writes `web/exports/` (substations, study areas, straight
  lines, project table, Google Earth file, IRP table) and zips them with a readme as
  `k2-gis-export.zip`, downloadable from the page's "Data for GIS" section.
* **IRP pilot**: the "Utility plans (IRPs)" tab. Research records (one schema, every number
  sourced, confidence per section) are in `data/irp_research/`; `data/build_irps.py` merges them
  into `data/irps.json`, which is loaded into the page database's `irps` collection.
* **Monitor Feed tab**: the old raw log from before the filter. Kept as an archive.

## How a scheduled run works

A scheduled task runs this every day at about 7am and 5pm Central. The same run checks ERCOT's planning
page for a new Transmission Project and Information Tracking report and, when there is one, rebuilds the
Texas lines list (`data/build_catalog.py`) and republishes the page.

1. Read the IDs in `'K2 Watch'!L2:L` and `'Monitor Feed'!J2:J` into `seen.txt`, one per line.
2. Run `python3 monitor.py --seen seen.txt --rows rows.json --json report.json --db-dir db/`.
3. Append `rows.json` to `'K2 Watch'!A:M` (Status `New`).
4. Batch-write `db/writes.json` to the webpage database, update `meta/status`, and move a
   project card along the ladder when a new signal clearly belongs to it.
5. Answer any `research` documents with status `queued`, then mark them `answered`.

Signals the filter drops are not saved, so they are checked again on the next run. That is
on purpose: a case that later gets a route map comes back in.

## When something breaks

* **"no project links matched"** for a utility: the utility redesigned its page. Fix the
  prefix for that utility in `UTILITY_PAGES` in `monitor.py`.
* **"no RPG meeting page could be read"**: set `RPG_SEED` to any recent meeting page
  (ERCOT calendar, "RPG Meeting"). ERCOT's committee index blocks scripts from cloud
  servers, but the meeting pages and PDFs load fine.
* **PUCT finds nothing for weeks**: check that the search still works by opening
  interchange.puc.texas.gov, Filing Search, with Item Number 1 and a recent date range.

## Faster channels that need your own sign-up

These can't be automated from here because they need an account in your name.

* **ERCOT planning email list** (regplangroup@lists.ercot.com). New project submissions are
  emailed to the list weeks before the monthly meeting page this monitor reads. The list
  archive needs a subscriber login, so the emails themselves are the alert.
* **PUCT Filing Notification System.** Emails you the same day anything is filed in a case you
  watch. The monitor already checks those cases twice a day; email alerts are faster still.

## Not covered yet

CenterPoint has no single project-list page (the news search covers it), utilities outside
Texas (the news search and the webpage assistant cover them), county commissioners court agendas for data-center deals, and county easement records.
