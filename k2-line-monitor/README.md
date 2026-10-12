# K2 line monitor

Finds new Texas transmission lines while they are still early, and lists them in the
**Monitor Feed** tab of the *K2 Transmission Intel Plan* Google Sheet.

It watches the public signals that come before a route is approved, earliest first
(see the FIRST TO KNOW section on the sheet's Signal Ladder tab):

| Step | Source | What a new item means |
|---|---|---|
| 2 | ERCOT Regional Planning Group (RPG) meeting pages | A utility submitted a project, or ERCOT posted its scope or recommendation. Names the end substations, often 1 to 2 years before a route filing. |
| 3 | Oncor, AEP Texas and LCRA project-list pages | A new project page usually means open houses with preliminary route links are coming, 4 to 9 months before filing. |
| 4-5 | PUCT Interchange new electric cases | A utility opened a case to amend its CCN for a transmission line: a route filing is starting or has just been made. |

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

Useful options: `--only puct|rpg|util` to check one source, `--puct-days 30` for how far
back to look for new PUCT cases, `--rpg-seed URL` to point at a recent RPG meeting page.

## How a scheduled run works

The Monitor Feed tab is the memory. Its ID column holds every signal already reported.

1. Read `'Monitor Feed'!J2:J` from the sheet and save the IDs to `seen.txt`, one per line.
2. Run `python3 monitor.py --seen seen.txt --rows rows.json`.
3. Append the rows in `rows.json` to the Monitor Feed tab. Their Status is `New`.
4. For each High priority row, look at the source and decide whether it deserves an
   Opportunity Card.

## When something breaks

* **"no project links matched"** for a utility: the utility redesigned its page. Fix the
  prefix for that utility in `UTILITY_PAGES` in `monitor.py`.
* **"no RPG meeting page could be read"**: set `RPG_SEED` to any recent meeting page
  (ERCOT calendar, "RPG Meeting"). ERCOT's committee index blocks scripts from cloud
  servers, but the meeting pages and PDFs load fine.
* **PUCT finds nothing for weeks**: check that the search still works by opening
  interchange.puc.texas.gov, Filing Search, with Item Number 1 and a recent date range.

## Not covered yet

CenterPoint and CPS Energy project pages (their page addresses still need to be found),
utilities outside Texas, and county easement records.
