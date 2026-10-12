# K2 line monitor

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

## Faster channels that need your own sign-up

These can't be automated from here because they need an account in your name.

* **ERCOT planning email list** (regplangroup@lists.ercot.com). New project submissions are
  emailed to the list weeks before the monthly meeting page this monitor reads. The list
  archive needs a subscriber login, so the emails themselves are the alert.
* **PUCT Filing Notification System.** Emails you the same day anything is filed in a case you
  watch. The monitor already checks those cases twice a day; email alerts are faster still.

## Not covered yet

CenterPoint has no single project-list page (the news search covers it), utilities outside
Texas, county commissioners court agendas for data-center deals, and county easement records.
