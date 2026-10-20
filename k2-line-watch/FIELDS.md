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
