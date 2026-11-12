# K2 Line Watch: fields per line

What each line record holds today, and what phase 1 adds (from the Oct 20, 2026 call with Richard).
Phase 1 scope: every new or upgraded transmission line in Texas (ERCOT), from proposed to recently
built. No parcel or county-records digging yet.

## Fields today

| Field | What it holds | Example |
|---|---|---|
| `id` | Stable id | `hillje-blu-lacy` |
| `name` | Line name | Hillje to Blu Lacy |
| `kv` | Voltage | 765 |
| `utility` | Utility or owner | CenterPoint and AEP Texas |
| `region` | Grid | Texas (ERCOT) |
| `stage`, `stage_label` | Step on the Signal Ladder: 2 ERCOT review, 3 open houses / project page, 4 docket requested, 5 route case at PUC, 6 route approved, 7 land buying / construction | 3, Open houses / project page |
| `window` | Timing for K2: Open now (2-3), Act fast (4-5), Late (6-7) | Open now |
| `importance` | High (345 kV+) or Medium | High |
| `status` | Latest status in plain English | Open houses ran late July to Aug 1, 2026... |
| `next_step` | What happens next in the process | Route filing expected early 2027 |
| `why_k2`, `k2_action` | Why it matters, what K2 could do | |
| `miles` | Length | about 155 |
| `endpoints` | End substations in words | Hillje (Wharton Co.) to Blu Lacy (Nueces Co.) |
| `geo.endpoints[]` | Each end substation: `name`, `lat`, `lon`, `county`, `confidence` (exact / approx / town / county), `basis` (how it was placed), `source` | 29.0296, -96.236, approx |
| `counties`, `geo.counties[]` | Counties the line may cross, with `counties_basis` | Wharton, Jackson, Victoria... |
| Route options | Route links filed in the PUC case (GeoJSON), when public | Dockets 59475, 60319... |
| `docket`, `rpg` | PUCT docket, ERCOT RPG project number | 59475, 25RPG025 |
| `links[]` | Sources | ERCOT Board item 14.1 |
| `checked`, `updated` | Date facts were checked against a primary source, last update | checked 2026-10-09 |
| Landowners (add-on) | Per end substation: landowners with 20+ acres within 2 miles, acres, best lead score | 60 landowners, 9,805 acres |

GIS files (WGS84): end substation pins, study-area counties, straight lines between substations,
project table, Google Earth file. Download from the page's "Data for GIS" section.

## Fields phase 1 adds

Built into the **Texas lines** tab and `web/exports/k2-texas-lines.csv` / `.geojson` (one row per line or new
substation, 732 on Oct 20, 2026). Made by `data/build_catalog.py` from ERCOT's Transmission Project and
Information Tracking report (TPIT, October 1, 2026 update, posted Oct 23, 2026: every planned ERCOT project with its end
substations, counties, voltage, new and upgraded miles, status and in-service date), the Line Watch cards,
and for substation locations: the Line Watch cards, hand-researched points from utility filings and maps
(`data/sources/substation-locations.json`), the HIFLD substation map and OpenStreetMap (each point says how it was placed). Not in TPIT yet: construction start and MW capacity (TPIT gives
transformer MVA only), so those stay blank until a source publishes them.

| Field | Values |
|---|---|
| `project_type` | new line / upgrade (rebuild, reconductor, voltage upgrade) / new substation |
| `lifecycle` | proposed / planned / about to enter construction / in construction / operating (recently built). The detailed regulatory step stays in `stage`. |
| `construction_start`, `in_service` | Expected year (or quarter), with the source |
| `capacity_mw` | Capacity or transfer capability added, when published |
| `purpose` | network (shared grid) / dedicated (one generator or one large load) |
| `program` | Program or portfolio, e.g. ERCOT 765 kV STEP Eastern Backbone, a DOE grant |
| `route_status` | none / study area / preliminary routes / filed routes / approved route |
| `tap_note` | 500 kV and above: projects go at the substations; 345 kV and below: the line itself can be tapped |
| `recommended_next_step` | substation campaign / line campaign / follow updates / informational, plus a one-line reason |

### Recommended next step: draft rules

1. **Substation campaign**: an end substation has an exact or approximate location and the line is
   planned or further along (endorsed, approved, in construction). Always the choice for 500 and 765 kV.
2. **Line campaign**: the exact route is known (approved, in construction or recently built) and the
   line is 345 kV or below.
3. **Follow updates**: proposed, or the substations are only known to the town or county.
4. **Informational**: a dedicated-purpose line, or a line that adds no new opportunity.

Lines further along and coming online sooner rank higher (2027-2028 before 2032), but every line is kept.

## Fields added Oct 21, 2026 (developers and checking substations)

K2's focus for the rest of 2026 is developers and partners, and the team asked for a way to check the
substations and tell what is new. Each line in the Texas lines list now also has:

| Field | What it holds |
|---|---|
| `queue_projects`, `queue_mw` | Generation and battery projects already in ERCOT's interconnection queue at the line's end substations, and their total MW (from ERCOT's monthly Generator Interconnection Status report, September 2026) |
| `queue_developers` | Up to five developers there, biggest first, as filed with ERCOT (often a project company such as "Amerada Solar, LLC", not the parent developer) |
| `from_status`, `to_status` (`endpoints[].in_place`) | Whether the end substation exists today: on public maps (HIFLD or OpenStreetMap) / new or expanding (per ERCOT) / not on public maps |
| `endpoints[].check_link` | Satellite view of the substation point, to check it by eye |
| `first_seen` | Date the line first appeared in the list (the first list is Oct 20, 2026), so new entries stand out |

`web/exports/k2-texas-developers.csv` has one row per queued project at a catalog substation: substation,
county, location, status, the lines there, ERCOT queue number (INR), project, developer, fuel, MW, expected
online date, study stage, interconnection agreement signed or not, construction start, and how it connects
(at the substation or tapping a line to another station). Matching is by station name and county (or within
15 miles of it), so a project ERCOT lists only by a bus code may be missing.

Not yet: the parent company behind each project company, and a contact person. Those need research beyond
ERCOT's report (state business filings, developer websites, press releases).

## How the list is cleaned (Oct 22, 2026)

- **Dates**: ERCOT's placeholder year 9999 counts as no date. An "actual" in-service date that is still in the future
  counts as projected. A planned line whose in-service date has passed, and that ERCOT has not marked in service yet,
  shows as "in construction" (estimated, with the reason in `lifecycle_basis`) until ERCOT's next report confirms it.
- **Purpose**: "POI" alone marks a generator hookup only when the project is not part of an ERCOT planning project
  (RPG number), the Permian Basin Reliability Plan, or a hookup to another utility ("POI with CenterPoint").
  Capacitor-only records are equipment and are left out; a new line that also adds capacitors stays.
- **Miles**: a rebuild that reports the same miles as both new and rebuilt reuses the existing corridor, so it is an
  upgrade with those miles under `miles_upgraded` only.
- **Station names**: when ERCOT's terminal columns are blank or bus numbers, the names come from the project title or
  description, or from bus numbers named in ERCOT's interconnection queue. The bus number stays in parentheses:
  "Helotes (5200)". ERCOT's "Morley"/"Morely" is Hillje and "Clearfork" is Mascho.
- **Cards**: a Line Watch card merges into the ERCOT line that names both its end substations (also when the card is one
  segment of a longer ERCOT line); `card_ids` lists every merged card. Miles and in-service dates for cards ERCOT does not
  list yet come from `data/sources/card-facts.json` (each with its source), the card, or the recommended route filed in
  the PUC case.
- **Utilities**: one spelling per utility, ERCOT's codes ("ONCOR", "LCRATSC").


## Changes from the Oct 26, 2026 team call (Richard, John, Steve)

Phase 1 is the research layer only: where new lines are going, not routes or parcels. K2's GIS team (Steve) and
map (John) take the layer in; routes, county records and parcels are phase 2 for lines K2 picks.

- **Time window**: "3 down, 5 up": every line built in the last 3 years (since October 2023, because Landgate may not
  have them yet) through everything in construction, approved, planned or proposed that is due in service within the
  next 5 years (through October 2031). Lines due later are left out; a line with no date yet stays in. Lines built
  before this year come from the completed-project lists in ERCOT's October 2024 and October 2025 TPIT updates
  (`data/sources/ercot-tpit-2024-10.xlsx`, `ercot-tpit-2025-10.xlsx`).
- **Stage** (`lifecycle`, `stage` in the exports): Richard's five steps.

| Stage | Meaning | How it is set |
|---|---|---|
| built | In service in the last 3 years | ERCOT actual in-service date |
| in construction | Being built | ERCOT "under construction", a card at land buying, or a planned date that has passed (estimated) |
| approved | Approved and the route is final, waiting to build | PUC route approval (card), an upgrade in its existing corridor, or planned to be in service within 18 months (estimated) |
| planned | Approved to build, route or site not final | ERCOT "planned" otherwise |
| proposed | Someone wants to build it, not approved yet | ERCOT "conceptual", or a card still in ERCOT review |

- **Builder**: `utility` (`builder` in the exports), the transmission owner ERCOT lists.
- **Tap rule** (`tappable`, `tap_note`): yes for 345 kV and below, maybe for 500 kV, no for 765 kV (substations only).
- **Substation status** (`endpoints[].station_status`, `from_status` / `to_status`, and the substations table):
  new (ERCOT's project builds it), existing, expanding (there today and a new line, new substation work or a
  transformer is coming), existing (on public maps, or an existing line to it is being upgraded, or a line built in
  the last 3 years ends there), unconfirmed (not on public maps by this name and ERCOT doesn't call it new).
  `status_reason` lists the evidence.
- **Substation stage** (substations table and `endpoints[]`; `from_` / `to_` columns in the line table):
  `there_now` (yes / no, being built / unknown), `work` (building a new substation / adding to it: a new line,
  transformer or expansion / upgrading lines to it / no new work), `work_stage` (built, in construction, approved,
  planned or proposed: the furthest-along project doing that work), `work_in_service` and `work_project`.
  A substation built new in the last 3 years counts as there now.
- **Rough location for every line**: a substation that isn't on public maps by name is placed at the center of its
  county (`location_quality` = county), since Richard said a rough location is enough for now.
- **One GIS layer**: `web/exports/k2-all-layer.geojson` (and `.kml`) holds every line and every substation in every
  region with all fields, as Steve asked. Per region: `k2-texas-layer`, `k2-ercot-texas-layer`, `k2-spp-texas-layer`,
  `k2-el-paso-layer`, `k2-oklahoma-layer`, `k2-miso-texas-layer`, `k2-miso-layer` (each with `-lines.csv` and
  `-substations.csv`). `market` (ERCOT, SPP, WECC, MISO) and `state` are on every feature.
- **Outside ERCOT (Nov 9, 2026)**: SPP's 2026 STEP project list (`data/build_spp.py` reads
  `data/sources/spp-step-2026.xlsx`: the Texas Panhandle, South Plains, Northeast Texas and Oklahoma; ids `spp-<upgrade id>`)
  and El Paso Electric's 2027-2036 System Expansion Plan (`data/build_epe.py`, curated in `data/sources/epe-plan-2026.json`;
  ids `epe-...`). SPP stages: complete / in service = built; identified = proposed; notice to construct issued = planned,
  or approved for an upgrade or a line due within 18 months; past its date and not complete = in construction. SPP gives no
  county, so its substations are placed by name on HIFLD / OpenStreetMap (Texas, Oklahoma and neighbors, via
  `data/fetch_substations.py`), else at the town they are named for (`location_quality` = town, Census places).
- **MISO (Nov 12, 2026)** (`data/build_miso.py`, market `MISO`). MISO's own site refuses automated downloads, so both
  lists are kept by hand from public copies:
  - Entergy Texas (MISO's part of Texas, Southeast Texas), `data/sources/miso-etr-2026.json`, ids `etr-...`: Entergy's
    monthly construction report to the PUC (June 2025, the last on the public Interchange; later reports go to the PUC's
    Compliance Reporting Portal) plus its project pages (SETEX, Cypress - Legend, Southline - Jacinto, War Eagle,
    Sabine Pass). Stages: energized = built; past the planned finish by 6+ months with no energized date = built
    (estimated); construction started = in construction; PUC route approved = approved; route case pending = proposed.
  - MISO's LRTP Tranche 1, `data/sources/miso-lrtp-2026.json`, ids `miso-lrtp-<1-18>`: the 18 345 kV backbone projects
    (North Dakota to Michigan) from MISO's dashboard (June 30, 2026). MISO approved them all in 2022, so planned;
    in construction where MISO's construction column says so. Tranche 2.1 (2032-2034) is listed in the file but past
    the 5-year window (window confirmed Nov 12, 2026: built in the last 3 years to due within 5). MISO's local project list (MTEP Appendix A) is on MISO's site only and not included.
  Stations are placed by name on HIFLD / OpenStreetMap in the state given (and the county, when the source gives one),
  new stations beside the station the source names (`approx`) or at the county center.
- **SPP 2026 ITP 765 kV lines (Nov 11, 2026)**: `data/sources/spp-itp-2026.json`, kept by hand from SPP's draft 2026 ITP
  report (Table 3.1, Southern Stage): six lines recommended for construction plus Holcomb - Potter County (deferred),
  ids `sppitp26-...`, stage proposed until SPP's board votes (Nov 17, 2026). When the board approves, set `"approved": true`
  in that file and rebuild: the recommended lines become planned. The Northern Stage (Dakotas, Nebraska, Kansas) is
  outside Line Watch's regions.
- **New vs already on the map** (`on_public_map`, `nearest_mapped`, `nearest_mapped_miles` per substation): any substation,
  by any name, on HIFLD or OpenStreetMap within 0.2 mi counts as already mapped, the way John compared the layer with
  K2's map (the two maps put one substation up to about 0.2 mi apart, under different names, so match by distance,
  not name). "can't tell" when the point is only a town or county center.
- **New-only layers** (`exports/k2-<region>-new-only.geojson` and `.kml.xml`, John's ask Nov 12): what is not already
  there. Lines not yet built (every stage but built), substations not on HIFLD or OpenStreetMap, mapped substations being
  expanded (more power coming), and substations the source calls new whose location is too rough to check. Each
  substation carries `new_only_reason`. The full layers stay the complete dataset; new-only is a filter of them.
- **Earlier signals: Oncor's CCN Public Viewer** (`data/fetch_oncor_ccn.py` -> `data/sources/oncor-ccn.json`). Oncor posts a
  study area and its end stations before the open houses, months before ERCOT's TPIT report lists the line. The catalog
  adds viewer projects it doesn't already have (ids `oncor-ccn-<project id>`, stage planned) and uses the viewer's station
  points as exact locations. The twice-daily monitor alerts on new viewer projects (`oncorccn:<id>`) and on CenterPoint's
  project pages too.
- **Data checks** (`data/check_catalog.py`, run after every build; results in `texas-lines.json` "checks" and on the
  page): every ERCOT line against its TPIT row (voltage, in-service date, stage), the time window, every substation
  point inside Texas and its listed county, substation status consistent between lines and substations, downloads
  matching the page data, and every Oncor viewer project present. A failed check blocks publishing.
- **Market** (`market`): "ERCOT (Texas)" for now, so lines can be sorted by market once other regions are added.
