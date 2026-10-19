# K2 Tier 3 prototype: Line Watch to call list

An n8n workflow that turns K2 Line Watch's substations into a scored list of
landowners, with each lead's next step: a letter, a human call, or a Wendy call.

```
Line Watch substations ─> land within 2 miles ─> owners ─> score ─> phone lookup ─> next step ─> CSV / Wendy
   (GitHub file)          (Texas parcel layer)              (0-100)   (off by default)
```

Test run on Oct 19, 2026, using the 8 best substations (all High, "Open now"): 128 map tiles,
4,887 parcels within 2 miles, 353 landowners with 20+ acres, 76,113 acres total. It took
about 75 seconds.

## What each step does

| Step | n8n node | What happens |
|---|---|---|
| 1 | Settings | All the knobs (table below). |
| 2 | Get Line Watch substations | Reads `data/substations.json` from GitHub: 51 substations from the Line Watch project cards, each with its projects, stage and timing. |
| 3 | Pick substations | Texas only, location exact or approximate, Medium or High projects, best first ("Open now" before "Late"). |
| 4 | Make map tiles | Cuts the 4 x 4 mile square around each substation into 1-mile tiles (the parcel service returns at most 2,000 parcels per call). |
| 5 | Look up parcels | Texas statewide parcel layer (TxGIO StratMap, from each county appraisal district): owner, mailing address, acres, value. Free and public. Failed tiles get a second, slower try. |
| 6 | Score parcels and owners | Keeps parcels within the radius, rolls them up by owner, skips public/utility/railroad land, flags energy companies, scores each owner. |
| 7 | Phone lookup on? / Find phones | Off by default. Looks up phones for landowners only (Tracerfy), with Do Not Call and TCPA litigator flags. `demo` mode fills in made-up 555-01xx numbers instead, so you can see the whole flow for free. |
| 8 | Pick next step | `mail-first`, `sales-call`, `wendy` or `skip: ...` (see below). |
| 9 | Make CSV / Save CSV | Writes `output/k2-tier3-leads-YYYY-MM-DD.csv`. |
| 10 | Send to Wendy | Off until Deepak shares Wendy's input format. Only gets `wendy` leads. |

**Lead score (0 to 100)** = acres (up to 35, full marks at 640+) + closeness to the substation
(up to 30) + project importance (High 15, Medium 8) + timing (Open now 15, Act fast 10, Late 3),
minus 5 when the substation location is only approximate.

## Next steps and the calling rules

The FCC ruled in February 2024 that AI-generated voices count as "artificial voice" under the
TCPA. An AI call (Wendy) to a home or cell phone needs the person's **prior consent**, and
telemarketing calls need written consent. So the workflow never sends a cold lead to Wendy:

| List | Who | What happens |
|---|---|---|
| `mail-first` | Every landowner without a clean phone | Letter asking them to call or reply if open to a lease. Replies become Wendy leads. |
| `sales-call` | Landowners with a phone that is not on Do Not Call and not a known litigator | A K2 salesperson dials by hand (no AI voice, no autodialer). |
| `wendy` | Owners who opted in (their parcel id is in `consentedParcelIds`) | Wendy calls to qualify and books a sales call. |
| `skip: public-or-utility` | City, county, state, school, utility, railroad, pipeline land | Not a lease target. |
| `skip: energy-company` | Solar, wind, storage, data-center owners | Probably already leased. Useful as a competition signal. |

This is a starting point, not legal advice. K2 should have a lawyer confirm the calling plan
before any real calls.

## Set up a Mac (once per Mac)

Works on this MacBook and the home desktop the same way. Node 20 to 24 is fine (no Homebrew needed).

```
git clone https://github.com/jaidensuthar-collab/shinepro-demo.git   # or git pull if you have it
cd shinepro-demo && git checkout claude/vibrant-euler-urtmp2
npm install --prefix ~/.npm-global n8n@1.123.85
cd k2-tier3
./start-n8n.sh
```

Open http://localhost:5679. The first time, n8n asks you to make a local owner account
(type it yourself). Open **K2 Tier 3: Line Watch to call list** and click **Execute workflow**.
The CSV appears in `k2-tier3/output/`.

This n8n uses **port 5679** and its own folder (`k2-tier3/.n8n-local`). It never touches another
n8n on the same Mac (port 5678, `~/.n8n`).

To see what each step produced, click any node in n8n after a run: its output shows on the right.

## Editing on two Macs

GitHub holds the master copy of the workflow.

```
./sync.sh load    # before you start editing: pull from GitHub and load into n8n
./sync.sh save    # after editing in n8n: write it to the repo and push to GitHub
./sync.sh key     # once per Mac, only when phone lookup is turned on
```

Save on one Mac, then load on the other. If you edit on both without syncing, the last save wins.
API keys live inside each Mac's n8n, never in git. Lead CSVs stay in `output/`, which git ignores:
they hold landowner names and addresses, and this repo is public.

## Keeping it running

A scheduled task runs every Monday at 8:52am CT (after the morning Line Watch check):

1. Refreshes `data/substations.json` from the Line Watch project cards, and adds cards for new
   High-priority lines when their substation locations can be sourced.
2. Runs the whole workflow for every Texas substation (`run_headless.sh`, about 10 minutes).
3. `report/build_report.py` compares owners against `data/seen-owners.txt` and lists what is new:
   new substations, new landowners, new acres. That file holds one-way fingerprints, not names.
4. Updates the group page and sends Jaiden the private list with full names.

To run the same thing by hand: `./run_headless.sh output/run-today demo 0` then
`python3 report/build_report.py output/run-today`.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `radiusMiles` | 2 | How far from the substation to look. |
| `tileMiles` | 1 | Tile size for parcel lookups. Make it smaller if the summary lists `truncatedTiles`. |
| `minAcres` | 20 | Owners with less land in the radius are dropped. |
| `minImportance` | Medium | `High` keeps only High projects. |
| `locationQuality` | exact,approx | Substation location quality to accept. |
| `onlySubstations` | (blank) | Comma list of ids or names, e.g. `solstice,longshore`. Blank means all. |
| `maxSubstations` | 8 | How many substations per run (all 43 Texas ones take about 6 minutes). |
| `maxLeads` | 500 | Cap on landowner rows. |
| `phoneLookup` | off | `off`, `demo` (made-up 555-01xx numbers, nothing leaves your Mac), `sandbox` (Tracerfy's free test server, fake numbers) or `live` (real numbers, paid, needs `./sync.sh key`). |
| `consentedParcelIds` | (blank) | Parcel ids of owners who opted in. Later this becomes a sheet or Wendy's own log. |

## Refreshing the substations

`data/substations.json` is built from the Line Watch project cards:

```
python3 data/export_substations.py ../k2-line-monitor/data/projects.json
```

## Known limits

* Texas only (the free statewide parcel layer). Other states need their own parcel source.
* Acres are whole parcels that reach within the radius, not just the part inside it.
* 26 of the 43 Texas substation locations are approximate. Those leads say "GIS team to confirm".
* Owner and address data is as fresh as the county appraisal roll (tax year 2026 in the test).
* Real phone numbers need a paid Tracerfy account. `demo` and `sandbox` numbers are fake: never dial them.
* Phone lookup was tested against a local fake server shaped like Tracerfy's documented
  responses, not against Tracerfy itself. Try `sandbox` first.
* n8n 1.123.85 is the last line that runs on Node 22. Moving to n8n 2.x later needs Node 24;
  the workflow imports as is.
