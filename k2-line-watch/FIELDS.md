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
    the 5-year window (window confirmed Nov 12, 2026: built in the last 3 years to due within 5).
  - MISO's MTEP25 Appendix A (Nov 13, 2026), `data/sources/miso-mtep25-appendix-a.xlsx` (Jaiden downloaded it from
    MISO's site), ids `mtep25-<facility id>`: the new local projects MISO's board approved in Dec 2025 (data as of
    Oct 2025), new and upgraded lines 138 kV+ and new 345 kV+ substations in the window. Stages: M4 in service = built;
    M3 = in construction; past its date = in construction (estimated); upgrade of an existing line or due within 18
    months = approved; otherwise planned. Rows that repeat an Entergy Texas project are skipped. Earlier MTEP cycles
    still being built (MTEP21-24) are in MISO's Appendix A status report, not in this file.
  - Researched MISO projects (Nov 13, 2026), `data/sources/miso-research-2026.json`, ids `misor-<key>`: about 350
    projects in three passes (first by region; second a sweep of each state's regulator cases, utility plans and
    status reports, FERC filings, seams projects and data-center hookups; third targeted at what the second could
    not reach). Each pass found fewer new projects (about 200, 120, 30), and the third found 60-70% of what it
    checked already listed. The file's "swept" list names every case list and document set checked. Projects from utility project pages, state commission dockets and transmission owners' published plans (ATC's
    10-Year Assessment, Entergy's quarterly status reports, the Minnesota Biennial Report, Ameren Missouri's IRP), in
    four passes: MISO South (LA, AR, MS); Wisconsin and Michigan; Minnesota, Dakotas, Iowa; Illinois, Missouri,
    Indiana, Kentucky. This covers earlier MTEP cycles still being built, data-center and generator hookups, and
    projects not in MISO's list yet. Each project keeps its own stage, reason and sources. Skipped: projects already
    listed (same end substations or MTEP id), built projects with no in-service date, and two left out on review
    (a DC line upgrade, a Tranche 1 relocation), Minnkota (not a MISO member), and items with no stated voltage.
    misoenergy.org was not used. Known gap: projects from MISO's 2021-2024 plans (MTEP21-24) that only MISO's site
    lists, mostly ITC/METC in Michigan; MISO's Appendix A spreadsheets for those years would close it.
  - Corrections (`data/sources/miso-corrections-2026.json`): rows withdrawn or cancelled since MISO's list, each
    with the source that says so.
- **PJM (Nov 13, 2026)** (`data/fetch_pjm.py` -> `data/sources/pjm-upgrades.json`, `data/build_pjm.py`, market `PJM`,
  ids `pjm-<upgrade id>`): every upgrade in PJM's Project Construction data (the XML behind
  pjm.com/planning/m/project-construction: baseline, supplemental and generator-interconnection network upgrades)
  that is a new or upgraded line at 138 kV+ (by the line's own voltage in the description, else PJM's voltage field)
  or a new substation / switching station at 230 kV+. Equipment-only work (breakers, relays, fiber, terminal
  equipment) is left out, as are cancelled, withdrawn and on-hold upgrades. Stages: IS = built; UC = in
  construction; EP = approved for an upgrade or anything due within 18 months, else planned; PL = planned for a
  baseline project, proposed for a supplemental one (the utility's own plan, reviewed but not board-approved);
  Active (generator upgrade not yet under agreement) = proposed; past its date and not in service = in construction
  (estimated). PJM gives a state and a location name but no county: ends are placed by name on HIFLD /
  OpenStreetMap, else at the town they are named for (Census places now cover every MISO and PJM state).
  Researched projects PJM's list does not carry (generator ties, merchant lines, announced data-center hookups,
  state siting cases) are in `data/sources/pjm-research-2026.json`, ids `pjmr-<key>`.
- **Texas and SPP sweep (Nov 14, 2026)**: lines the official lists (ERCOT TPIT, Oncor CCN map, SPP STEP and ITP,
  El Paso Electric, Entergy Texas) do not carry, from PUC of Texas CCN cases and monthly construction reports, ERCOT
  RPG reviews and Regional Transmission Plans, SPP quarterly project tracking and NTCs, Oklahoma Corporation Commission
  cases, utility status reports and news: `data/sources/texas-research-2026.json`, built by `data/build_txr.py`, ids
  `txr-` (ERCOT), `sppr-` (SPP), `etrr-` (Entergy Texas), `eper-` (El Paso). A project is skipped when a listed line
  has the same end substations (names compared by their identifying words, so 'Tiger Solar POI' = 'Tiger Solar
  collector'), the same docket at the same voltage, or when ERCOT's report already lists the pair (its own date and
  rules win). Ties to one generator are `generator hookup`. Newer stages or dates for listed lines (and lines
  cancelled since their list) are in `data/sources/texas-corrections-2026.json`; such a line's stage basis starts
  "Line Watch research:" and the checker reports its difference from the official list for review, not as an error.
  The same sweep found that the ERCOT reader dropped any project whose description mentioned equipment (an
  autotransformer, breakers) even when it built miles of line; equipment words now only rule out records with no
  line miles, which added 19 ERCOT-listed lines (Del Sol - Frontera 345 kV, RELLIS - TNP One 345 kV, ...).
- **Rest of SPP (Nov 14, 2026)**: SPP's STEP list is now read for all 15 SPP states (region `spp`), not only Texas and
  Oklahoma, with HIFLD substations and Census towns added for Nebraska, Montana, Wyoming and Colorado. Researched SPP
  lines outside Texas and Oklahoma (state siting cases, SPP NTCs, the Q4 2026 quarterly project tracking report, the
  2026 ITP Northern Stage, utility pages and news) are in `data/sources/spp-research-2026.json` (ids `sppr-`), with
  stage and date changes in `spp-corrections-2026.json`; a correction that moves a line past the window removes it.
  Black Hills Energy is not an SPP RTO member (SPP's Apr 2026 member list), so its Wyoming and Colorado lines are left out.
- **CAISO (Nov 14, 2026)**: market `CAISO`, region `caiso`, ids `caisor-`. CAISO's own tracking list (Transmission
  Development Forum Attachment 1 and 2, July 2026; keys `tdf-<TP project id>`, `caiso_id` set) read row by row for 230 kV+
  lines, HVDC and new 230 kV+ substations (most rows are breakers, short-circuit duty, reactors or 115 kV and below),
  plus PG&E, SCE, SDG&E, GridLiance West / VEA (Nevada) and competitively built projects from CPUC CPCN/PTC cases,
  GO 131 reports, CEC and BLM generator-tie cases, WECC progress reports and news, in
  `data/sources/caiso-research-2026.json` (projects sharing a CAISO project id are kept once). LADWP, IID, SMUD/BANC
  and TID are not CAISO. Left out (listed in the file): TransWest Express AC and Silver Rock (not CAISO-planned), and the
  Suncrest 230 kV loop-in (SDG&E's application dates it 2032).
- **New York and New England (Nov 14, 2026)**: markets `NYISO` (ids `nyr-`) and `ISO-NE` (ids `isner-`), regions `nyiso` and
  `iso-ne`. NYISO's 2026 Gold Book Table VII (as of Mar 15, 2026) and ISO-NE's RSP Project List and Asset Condition List
  (Oct 2026; asset-condition rows only for 345 kV line rebuilds) read row by row, plus NY PSC Article VII and ORES
  permits, the six New England states' siting cases, offshore-wind export cables and merchant lines, in
  `data/sources/northeast-research-2026.json`. U.S. parts only: Champlain Hudson Power Express and NECEC start at the
  Canadian border. Projects are matched by end substations, not by queue number (NYISO gives one queue number to a whole
  program, e.g. all 13 Smart Path Connect lines). Left out (listed in the file): NYSEG's SCATE Lines 68/69/72 (NYSEG now
  dates them Q4 2032), Knickerbocker - Pleasant Valley (energized summer 2023), Twin States and Clean Path NY (cancelled).
- **West outside CAISO and SPP (Nov 14, 2026)**: market `West` (ids `westr-`, region `west`): Arizona, New Mexico,
  Nevada, Colorado, Utah, Wyoming, Idaho, Montana, Oregon and Washington. WestConnect's Transmission Plan Project List
  (all 389 rows, keys `wc-<wcprojectID>`) and NorthernGrid's 2024-2025 Regional Transmission Plan and 2026-2027 study
  scope (keys `ng-`), BPA and PacifiCorp plans, plus every western state's siting cases, utility pages and news, in
  `data/sources/west-research-2026.json`. Lines owned by SPP RTO members (Tri-State, Basin, WAPA Rocky Mountain and
  Upper Great Plains, Colorado Springs, Platte River, ...), CAISO participants (GridLiance West / VEA) and El Paso
  Electric are skipped: they are in their own regions. Black Hills (not an SPP member) is here.
- **Southeast (Nov 16, 2026)**: market `Southeast` (ids `ser-`, region `southeast`): Georgia, Alabama, Mississippi
  (Mississippi Power and TVA), Tennessee, Kentucky (LG&E/KU, TVA), North and South Carolina (Duke, Santee Cooper,
  Dominion SC) and Florida. Researched from SERTP's 2024-2026 regional plans, the Georgia ITS 2025 ten-year plan, the
  NC Transmission Planning Collaborative, NCUC and SC PSC siting cases, TVA project pages and environmental reviews,
  Florida utilities' Ten-Year Site Plans, FRCC and Florida Transmission Line Siting Act cases, and Alabama,
  Mississippi and Kentucky commission cases, in `data/sources/southeast-research-2026.json` (its `left_out` says
  why three projects were dropped). TVA's 161 kV lines count. PJM members (Dominion NC, EKPC, AEP Kentucky Power,
  Duke Energy Kentucky) and MISO members (Entergy Mississippi, Cooperative Energy, Big Rivers) are in their own regions.
  A researched project's `state` may name several states ("GA, AL").
- **Every state's line-approval process (Nov 16, 2026)**: a sweep of each state's siting / certificate case list
  (2023-2026), utilities' open-house and project pages, large-load and generator hookups and news, in
  `data/sources/us-process-research-2026.json` (its `process_notes` say who approves lines in each state and where the
  case list is; `left_out` says why some finds were not added) and `data/sources/us-process-corrections-2026.json`
  (newer stages and dates for listed lines, with sources; a line moved past the window comes off, and the PJM check
  lists those as left out on purpose). New ids: `pjms-` for PJM-area finds; other markets reuse their research
  prefixes. Lines built to 230 kV but run at 115 kV (Alaska's Kenai rebuilds) do not count. Most Nevada finds are
  generator-tie applications from the PUCN's UEPA case list, marked proposed: their decisions were not checked.
- **KML layers** leave out `geometry_note`, `check_link` and `recommendation_reason` (the GeoJSON and CSV keep them)
  so the all-regions KML stays under the 16 MB per-file publish limit.
- **Data fixes (Nov 16, 2026 audit)**: when a list's voltage column disagrees with the voltage its own title states
  (ERCOT "Rockhound - Connell 345 kV" with 138 in the kV column, SPP "Finstad - Vanhook 115 kV" with 345), the title
  wins (`stated_kv` in build_catalog.py; a "345/138" or "345-138" title counts both, a conversion keeps the higher);
  SCE's 220 kV lines stay 220 kV. A researched line that is approved or planned and past its due date shows as in
  construction (estimated) until a source says it is finished. SPP rows marked in service but carrying a future date
  get no date. PJM rows with a blank state are placed by their transmission owner's states (not Pennsylvania by
  default), and rows with no location are "Unnamed station (PJM id)". One station spelled two ways (Sand Lake /
  Sandlake, Peach Bottom / Peach Botton, ...) is one site, a station listed as both ends of a line is one end, and a
  line with no builder in its source says "Not named in the source". Substation wording no longer says ERCOT outside
  Texas.
- **U.S. only**: the checker fails if any line or substation is outside a U.S. state; a line that runs to the national
  border is listed for its U.S. part, and the check lists those for review.
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
