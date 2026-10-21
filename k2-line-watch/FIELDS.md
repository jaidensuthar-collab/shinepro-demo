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
Information Tracking report (TPIT, July 13, 2026 update: every planned ERCOT project with its end
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

