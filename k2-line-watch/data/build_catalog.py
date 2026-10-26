"""Build the phase 1 Texas line catalog for K2 Line Watch.

Every new or upgraded ERCOT transmission line (138 kV and up), plus new 345 kV+ substations, from
ERCOT's Transmission Project and Information Tracking report (TPIT), joined to the Line Watch project
cards. Each line gets the phase 1 fields (FIELDS.md): project type, lifecycle, in-service date,
purpose, program, route status, located end substations and K2's recommended next step.

    python3 build_catalog.py [projects.json | dir of project JSON] [tpit.xlsx] [queue.xlsx]

Writes ../web/data/texas-lines.json (read by the page) and ../web/exports/k2-texas-lines.csv / .geojson.
Developers already queued at each end substation come from ERCOT's monthly Generator Interconnection Status
report (queue.xlsx) and go to ../web/exports/k2-texas-developers.csv.
Substation points come from the Line Watch cards first, then the HIFLD substation layer
(sources/hifld-tx-substations.json), matched by name and county.
"""
import csv
import datetime
import glob
import json
import math
import os
import re
import shutil
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")
TPIT_URL = "https://www.ercot.com/gridinfo/planning"
HIFLD_URL = "https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/Electric_Substations/FeatureServer/0"
QUEUE_URL = "https://www.ercot.com/misapp/GetReports.do?reportTypeId=15933"
TODAY = datetime.date.today()
# Richard (Oct 26 team call): every line built in the last 3 years, plus everything in construction, approved, planned or proposed.
CUTOFF = TODAY.replace(year=TODAY.year - 3, day=1)
HORIZON = TODAY.replace(year=TODAY.year + 5).strftime("%Y-%m")   # window: built in the last 3 years to in service within 5 years
STAGES = ["built", "in construction", "approved", "planned", "proposed"]
STAGE_HELP = {"built": "In service within the last 3 years",
              "in construction": "Being built now",
              "approved": "Approved and the route is final (or it stays in its existing corridor); waiting to build",
              "planned": "Approved to build, but the route or site is not final",
              "proposed": "Someone wants to build it; not approved yet"}
# Older TPIT editions: their Completed tabs cover lines energized before this year's report starts.
HISTORY = [("ercot-tpit-2025-10.xlsx", "October 1, 2025"), ("ercot-tpit-2024-10.xlsx", "October 1, 2024")]
MARKET = "ERCOT (Texas)"

PROGRAMS = {"25RPG025": "ERCOT 765 kV STEP: Eastern Backbone", "H.B. 5066": "Permian Basin Reliability Plan (HB 5066)"}
GENERATOR = re.compile(r"GEN[ -]?TIE|\bGEN\b|GENERATION|BESS|SOLAR|WIND|STORAGE|\bESR\b|\d{2}INR\d{3,4}|\bG?INR\b|POWER PLANT", re.I)
# 'POI' alone is weaker: it also names a hookup to another utility or a co-op delivery point inside a grid plan.
POI = re.compile(r"\bPOI\b", re.I)
GRID_PLAN = re.compile(r"RELIABILITY PLAN|\d{2}RPG\d{3}|\bPOI\)? WITH\b", re.I)
# Rebuilds that report the same miles as new and rebuilt reuse the existing corridor.
CAPACITOR = re.compile(r"CAPACITOR", re.I)   # capacitor-only records are equipment; a new line that also adds capacitors stays
REUSE = re.compile(r"REBUILD|RECONDUCT|UPGRADE|OVERHAUL|CONVER", re.I)
BOILERPLATE = "This models"   # ERCOT's generic title for load-addition upgrade sets; the description says what it is
# ERCOT's names for stations the Line Watch cards call something else.
ALIASES = {"MORLEY": "HILLJE", "MORELY": "HILLJE", "CLEARFORK": "MASCHO"}
BIG_LOAD = re.compile(r"DATA ?CENTER|LARGE LOAD|NEW LOAD|ALPHA LOAD|CUSTOMER|LNG|CRYPTO|MINING|REFINERY|HYDROGEN|\bLOAD\b.{0,25}INTERCONNECT|INTERCONNECT.{0,40}\bLOAD\b", re.I)
EQUIPMENT = re.compile(r"^MODELS|LOAD RECORD|CAP(ACITOR)? BANK|REACTOR|AUTO ?TRANSFORMER|CONDENSER|DYNAMIC REACTIVE|BREAKER|RELAY|METER|STATCOM|SVC\b", re.I)
NEW_STATION = re.compile(r"(NEW|CONSTRUCT|ESTABLISH|ADDITION|\bADD\b).{0,60}(STATION|SWITCH|SUBSTATION)|(STATION|SWITCH|SUBSTATION).{0,30}(ADDITION)", re.I)
UPGRADE_KIND = [("reconductor", re.compile(r"RECONDUCT", re.I)), ("rebuild", re.compile(r"REBUILD", re.I)),
                ("voltage upgrade", re.compile(r"CONVERT|CONVERSION|VOLTAGE UPGRADE", re.I)),
                ("second circuit", re.compile(r"SECOND CIRCUIT|2ND CIRCUIT|DOUBLE CIRCUIT", re.I))]
STAGE_ROUTE = {3: "preliminary routes", 4: "preliminary routes", 5: "filed routes", 6: "approved route", 7: "approved route"}


def clean(v):
    """TPIT cells carry Excel line-break codes (_x000D_) and stray whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"_x000D_", " ", str(v or ""))).strip()


def base(name):
    """'New Martin Lake 765/345 kV Switch' -> 'MARTIN LAKE'; 'Howard (Howard Road) Substation' -> 'HOWARD'.
    Bus numbers ('5400', '5133, 5915') are not names and come back empty."""
    n = re.sub(r"\(.*?\)", " ", clean(name)).upper()
    if re.fullmatch(r"[\d ,;]+", n):
        return ""
    n = re.sub(r"\b\d+(/\d+)?\s*-?\s*KV\b", " ", n)
    n = re.sub(r"\b(NEW|EAST(?= WATERMILL)|SUBSTATION|SUBSTA|SWITCHING|SWITCHYARD|SWITCH|STATION|SUB|SS|SW|SWS|POI|TAP|LCRA TSC|CPS|ONCOR|AEP)\b", " ", n)
    n = re.sub(r"[^A-Z0-9 ]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def ym(v):
    return v.strftime("%Y-%m") if isinstance(v, (datetime.date, datetime.datetime)) else ""


def load_projects(src):
    if os.path.isdir(src):
        out = []
        for f in sorted(glob.glob(os.path.join(src, "*.json"))):
            d = json.load(open(f))
            d = d.get("data", d)
            d.setdefault("id", os.path.basename(f)[:-5])
            out.append(d)
        return out
    return json.load(open(src))


def queue_label(path):
    m = re.search(r"(\d{4})-(\d{2})", os.path.basename(path or ""))
    return datetime.date(int(m[1]), int(m[2]), 1).strftime("%B %Y") if m else ""


def real_date(v):
    """A TPIT date cell as a datetime, or None for blanks and ERCOT's placeholder years (9999-01-01, 1900)."""
    if isinstance(v, datetime.date) and not isinstance(v, datetime.datetime):
        v = datetime.datetime(v.year, v.month, v.day)
    return v if isinstance(v, datetime.datetime) and 1950 <= v.year <= 2100 else None


def read_tpit(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows, seen = [], set()
    for ws in wb.worksheets:
        tab = next((t for t in ("Future", "Planned", "Completed") if ws.title.startswith(t)), None)
        if not tab:
            continue
        it = ws.iter_rows(values_only=True)
        next(it)
        hdr = [str(h or "").strip() for h in next(it)]
        col = lambda key: next(i for i, h in enumerate(hdr) if h.lower().startswith(key.lower()))
        C = {k: col(h) for k, h in {"id": "ERCOT Project Number", "title": "Project Title", "desc": "Project Description",
             "comment": "Comments", "from": 'Terminal "from"', "to": 'Terminal "to"', "status": "Transmission Status",
             "owner": "Transmission Owner (text)", "isd": "Projected In-Service", "actual": "Actual In-Service",
             "kv": "Service Level kV", "new_mi": "Trans Circuit Miles New", "upg_mi": "Trans Circuit Miles Rebuilt",
             "mva": "Autotransformer", "county_from": "County Location for Substation", "county_to": "County Location for Ending",
             "tier": "Planning Charter Tier", "rpg": "RPG Number", "rpg_done": "Date RPG Review Completed",
             "board": "Date ERCOT BOD"}.items()}
        for r in it:
            if r[C["id"]] is None or str(r[C["id"]]) in seen:
                continue
            seen.add(str(r[C["id"]]))
            d = {k: (clean(r[i]) if isinstance(r[i], str) else r[i]) for k, i in C.items()}
            d["tab"] = tab
            d["isd"], d["actual"] = real_date(d["isd"]), real_date(d["actual"])
            if d["actual"] and d["actual"].date() > TODAY:
                d["isd"], d["actual"] = d["isd"] or d["actual"], None
            rows.append(d)
    return rows


ONCOR_CCN_URL = "https://services6.arcgis.com/4U8AckBJXzVfzxBF/arcgis/rest/services/CCN_Data_AGOL/FeatureServer"
ONCOR_ALIASES = {"BELL COUNTY": "BELL EAST"}   # the viewer's short names for stations ERCOT names in full


def oncor_projects():
    path = os.path.join(HERE, "sources", "oncor-ccn.json")
    return json.load(open(path))["projects"] if os.path.exists(path) else []


def station_key(name):
    k = alias(base(name))
    return ONCOR_ALIASES.get(k, k)


def oncor_lines(out, places):
    """Oncor CCN Public Viewer projects (open houses or filed routes) that ERCOT's report and the cards don't list yet.
    They are the earliest Oncor signal: a study area goes up before the open houses."""
    have = [{station_key(e["name"]) for e in x["endpoints"]} for x in out]
    recs = []
    for pr in oncor_projects():
        keys = {station_key(st["name"]) for st in pr["stations"]}
        if len(keys) < 2 or any(len(keys & h) >= 2 for h in have):
            continue
        ends = []
        for st in pr["stations"]:
            if any(station_key(e["name"]) == station_key(st["name"]) for e in ends):
                continue
            county = next((k.split("|")[1] for k, bx in places.boxes.items() if k.startswith("TX|")
                           and bx[0] <= st["lon"] <= bx[2] and bx[1] <= st["lat"] <= bx[3] and in_county(places, k, st)), "")
            ends.append({"name": st["name"], "county": county, "lat": st["lat"], "lon": st["lon"], "confidence": "exact",
                         "basis": "Oncor CCN Public Viewer station point", "source": ONCOR_CCN_URL})
        name = pr["name"] or " - ".join(e["name"] for e in ends)
        filed = pr["status"] == "Filed"
        rec = {"id": f"oncor-ccn-{pr['project_id']}", "ercot_project": "", "name": name + f" {pr.get('kv') or ''} kV".rstrip(" kV") + (" kV" if pr.get("kv") else ""),
               "description": f"Oncor CCN Public Viewer project {pr['project_id']}: " + ("route case filed at the PUC" if filed else "study area / open houses, route not filed yet"),
               "kv": pr.get("kv") or 138, "project_type": "new line", "upgrade_kind": "", "lifecycle": "planned",
               "lifecycle_basis": "Oncor CCN viewer: " + ("route filed at the PUC, not approved yet" if filed else "open houses / study area, route not filed yet; not in ERCOT's report yet"),
               "tpit_status": "", "utility": "ONCOR", "from": ends[0]["name"], "to": ends[-1]["name"], "county_from": ends[0]["county"], "county_to": ends[-1]["county"],
               "miles_new": 0, "miles_upgraded": 0, "transformer_mva": 0, "in_service": "", "in_service_kind": "", "construction_start": "", "capacity_mw": None,
               "purpose": "generator hookup" if GENERATOR.search(name) else "shared grid", "program": "", "rpg": "", "tier": "", "ercot_board": "", "docket": "",
               "route_status": "filed routes" if filed else "preliminary routes", "card_id": "", "card_ids": [], "endpoints": ends,
               "source": "Oncor CCN Public Viewer (" + ONCOR_CCN_URL + ")", "checked": "Oncor CCN viewer " + TODAY.isoformat(), "market": MARKET}
        rec["tappable"], rec["tap_note"] = tap(rec["kv"])
        rec["recommended_next_step"], rec["recommendation_reason"] = recommend(rec)
        rec["priority_score"] = priority(rec)
        recs.append(rec)
    return recs


def in_county(places, key, pt):
    ring = max(places.rings[key], key=len)
    x, y, inside = pt["lon"], pt["lat"], False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def centroid(ring):
    """Area centroid of one polygon ring of [lon, lat] points."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        f = x0 * y1 - x1 * y0
        a, cx, cy = a + f, cx + (x0 + x1) * f, cy + (y0 + y1) * f
    if abs(a) < 1e-12:
        return sum(x for x, _ in ring) / len(ring), sum(y for _, y in ring) / len(ring)
    return cx / (3 * a), cy / (3 * a)


def history_rows(skip):
    """Lines energized since CUTOFF that this year's report no longer lists, from older TPIT editions (newest first)."""
    out = []
    for fname, label in HISTORY:
        path = os.path.join(HERE, "sources", fname)
        if not os.path.exists(path):
            continue
        m = re.search(r"(\d{4})-(\d{2})", fname)
        asof = datetime.date(int(m[1]), int(m[2]), 1)
        for r in read_tpit(path):
            rid, when = str(r["id"]), r["actual"] or r["isd"]
            if rid in skip or r["tab"] != "Completed" or not when or not CUTOFF <= when.date() <= asof:
                continue
            skip.add(rid)
            r["src"] = label + " update (completed projects)"
            out.append(r)
    return out


class Places:
    """Substation points: Line Watch card pins first, then HIFLD by name + county."""
    def __init__(self, projects):
        self.cards = {}
        for p in projects:
            for e in (p.get("geo") or {}).get("endpoints") or []:
                if e.get("lat") is None:
                    continue
                st, _, cty = (e.get("county") or "|").partition("|")
                self.cards.setdefault((alias(base(e["name"])), st), {**e, "basis": e.get("basis", ""), "from": "Line Watch card"})
        # Hand-researched points for new stations the HIFLD map doesn't have (sources/substation-locations.json).
        loc = os.path.join(HERE, "sources", "substation-locations.json")
        self.researched = {}
        for k, v in (json.load(open(loc))["stations"].items() if os.path.exists(loc) else []):
            if v.get("lat") is not None and v.get("confidence") in ("exact", "approx"):
                self.researched[clean(k).upper()] = v   # exact name, so bus numbers like "5400" work too
                self.researched.setdefault(base(k), v)
        h = json.load(open(os.path.join(HERE, "sources", "hifld-tx-substations.json")))
        self.hifld, self.by_name = {}, {}
        for s in h["substations"]:
            if re.match(r"(UNKNOWN|TAP)\d+$", s["name"]):
                continue
            self.hifld.setdefault((base(s["name"]), str(s["county"]).upper()), []).append(s)
            self.by_name.setdefault(base(s["name"]), []).append(s)
        self.boxes, self.centers = {}, {}
        for k, rings in json.load(open(os.path.join(WEB, "counties.json"))).items():
            xs = [x for r in rings for x, _ in r]
            ys = [y for r in rings for _, y in r]
            self.boxes[k] = (min(xs), min(ys), max(xs), max(ys))
            self.centers[k] = centroid(max(rings, key=len))
        self.rings = json.load(open(os.path.join(WEB, "counties.json")))
        # Named OpenStreetMap substations (sources/osm-tx-substations.json): many stations HIFLD leaves unnamed.
        osm = os.path.join(HERE, "sources", "osm-tx-substations.json")
        # Oncor's CCN Public Viewer (sources/oncor-ccn.json): exact points for Oncor's project stations.
        self.oncor = {}
        for pr in oncor_projects():
            for st in pr["stations"]:
                self.oncor.setdefault(alias(base(st["name"])), {**st, "project": pr["name"]})
        self.osm = {}
        for s in (json.load(open(osm))["substations"] if os.path.exists(osm) else []):
            self.osm.setdefault(base(s["name"]), []).append(s)

    def county_point(self, name, county):
        """A substation that isn't on public maps by name: place it at its county's center, so every line has a rough location."""
        c = self.centers.get("TX|" + str(county or "").strip().title())
        if not c:
            return {"name": name, "county": county or "", "confidence": "unknown", "basis": "Not on public maps by this name, and ERCOT gives no county"}
        return {"name": name, "county": county, "lat": round(c[1], 4), "lon": round(c[0], 4), "confidence": "county",
                "basis": f"Center of {str(county).strip().title()} County: ERCOT gives the county, but this substation is not on public maps by this name",
                "source": TPIT_URL}

    def near_county(self, pt, county, miles=20):
        """A name-only match must fall within about 20 miles of the county ERCOT gives (when it gives one)."""
        box = self.boxes.get("TX|" + str(county or "").strip().title())
        if not box:
            return True
        d = miles / 69.0
        return box[0] - d <= pt["lon"] <= box[2] + d and box[1] - d <= pt["lat"] <= box[3] + d

    def find(self, name, county):
        """Try the name as given, then its parts ('Wolf/Moss', 'Bitter Creek and Champion Creek', '7052 Gooseneck')."""
        hit = self._find(name, county)
        if hit:
            return hit
        clean_name = re.sub(r"^(ONCOR|AEP|CPS|LCRA)'?S\s+|^\d+\s+", "", clean(name), flags=re.I)
        for part in [clean_name] + re.split(r"\s*(?:/|,|;|\band\b)\s*", clean_name):
            if part and part != name:
                hit = self._find(part, county)
                if hit:
                    hit["name"] = str(name).strip()
                    if part != clean_name:
                        hit["basis"] = f"Located by '{part}', one of the stations named in '{clean(name)}'. " + hit["basis"]
                    return hit
        return None

    def _find(self, name, county):
        b = alias(base(name))
        r = self.researched.get(clean(name).upper()) or (self.researched.get(b) if b else None)
        if not b and not r:
            return None
        if r:
            return {"name": str(name).strip(), "county": r.get("county") or county, "lat": r["lat"], "lon": r["lon"],
                    "confidence": r["confidence"], "basis": r["basis"], "source": r["source"]}
        c = self.cards.get((b, "TX"))
        if c:
            return {"name": str(name).strip(), "county": county or c["county"].split("|")[1], "lat": c["lat"], "lon": c["lon"],
                    "confidence": c.get("confidence", "approx"), "basis": c.get("basis", ""), "source": c.get("source", "")}
        o = self.oncor.get(b)
        if o and self.near_county(o, county):
            return {"name": str(name).strip(), "county": county, "lat": o["lat"], "lon": o["lon"], "confidence": "exact",
                    "basis": f"Oncor CCN Public Viewer station point ({o['project']} project)", "source": ONCOR_CCN_URL}
        hits = self.hifld.get((b, str(county or "").upper())) or []
        if len(hits) == 1 or (hits and len({(round(x["lat"], 2), round(x["lon"], 2)) for x in hits}) == 1):
            s = hits[0]
            return {"name": str(name).strip(), "county": county, "lat": s["lat"], "lon": s["lon"], "confidence": "exact",
                    "basis": f"HIFLD substation {s['name']} ({s['county'].title()} County, {s['max_kv']} kV max, {s['status'].lower()})",
                    "source": HIFLD_URL}
        # OpenStreetMap: prefer transmission-level stations (tagged transmission or 115 kV and up) with that name.
        def high(s):
            volts = [int(v) for v in re.findall(r"\d+", s.get("voltage") or "")]
            return s.get("kind") == "transmission" or any(v >= 115000 for v in volts)
        cands = self.osm.get(b) or []
        tx = [s for s in cands if high(s)]
        pick = tx if tx else cands
        spread = {(round(s["lat"], 1), round(s["lon"], 1)) for s in pick}
        if pick and len(spread) == 1 and self.near_county(pick[0], county):
            s = pick[0]
            return {"name": str(name).strip(), "county": county, "lat": s["lat"], "lon": s["lon"],
                    "confidence": "exact" if tx else "approx",
                    "basis": f"OpenStreetMap substation '{s['name']}'" + (f", {s['voltage']} V" if s.get("voltage") else "")
                             + (f", {s['operator']}" if s.get("operator") else "") + ("" if tx else "; not tagged as transmission, so check it"),
                    "source": "https://www.openstreetmap.org/" + s["osm"]}
        # TPIT sometimes gives one county for both ends; a name that appears once in Texas is still a match.
        hits = [s for s in self.by_name.get(b) or [] if self.near_county(s, county)]
        if len(hits) == 1:
            s = hits[0]
            return {"name": str(name).strip(), "county": s["county"].title(), "lat": s["lat"], "lon": s["lon"], "confidence": "approx",
                    "basis": f"HIFLD substation {s['name']} ({s['county'].title()} County), the only Texas substation with this name; ERCOT lists {county or 'no'} County",
                    "source": HIFLD_URL}
        return None


OWNER_TAGS = re.compile(r"\b(TNMP|TNP|TN|CNP|CEHE|LCRA|AEN|BEC|STEC)\b")
FUELS = {"SOL": "solar", "WIN": "wind", "GAS": "gas", "NUC": "nuclear", "HYD": "hydro", "WAT": "hydro", "OIL": "oil"}


def poi_names(poi):
    """ERCOT queue hookup point -> station names, and whether the project taps the line between them.
    '59903 Bearkat 345kV' -> ['BEARKAT'], False; 'Tap 345kV 1444 Brown - 3422 Killeen' -> ['BROWN', 'KILLEEN'], True."""
    t = clean(poi)
    tap = bool(re.search(r"\btap", t, re.I))
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"(?i)\b(POI[AB]?( is)?:?|tap(ping)?( of| on| into)?|the|from|connecting|existing|bus( no\.?| number)?|psse|position \S+|"
               r"ckt\.?\s*\d*|circuit\s*#?\d*|d?ckt|double circuit|transmission line|line|owned by.*)\b", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*-?\s*kv\b", " ", t, flags=re.I)
    t = re.sub(r"(?i)#?\b\d{2,6}\b|\b(kv|double|single)\b", " ", t)
    t = re.sub(r"^\W*to\b", " ", t, flags=re.I)
    names = []
    for part in re.split(r"\s+(?:-|to|&|and)\s+|,|;|\s-\s|\u2013", t, flags=re.I):
        part = re.sub(r"_?(POI)?_?\d*$", "", part.strip(), flags=re.I)
        b = alias(re.sub(r"\s+", " ", OWNER_TAGS.sub(" ", base(part))).strip())
        if b and b not in names:
            names.append(b)
    return names, tap or len(names) > 1


def read_queue(path):
    """Projects in ERCOT's Generator Interconnection Status report (large generators that asked for a full study)."""
    rows = list(openpyxl.load_workbook(path, read_only=True, data_only=True)["Project Details - Large Gen"].iter_rows(values_only=True))
    head = next(i for i, r in enumerate(rows) if r and r[0] == "INR")
    col = {}
    for i, v in enumerate(rows[head]):
        col.setdefault(clean(v), i)
    out = []
    for r in rows[head + 1:]:
        if not re.match(r"\d{2}INR\d", str(r[0] or "")):
            continue
        g = lambda k: r[col[k]]
        names, tap = poi_names(g("POI Location"))
        ia = g("IA Signed")
        fuel, tech = clean(g("Fuel")), clean(g("Technology"))
        out.append({"inr": clean(r[0]), "project": clean(g("Project Name")), "developer": clean(g("Interconnecting Entity")),
                    "fuel": "battery" if tech == "BA" else FUELS.get(fuel, fuel.lower()), "mw": round(num(g("Capacity (MW)")), 1),
                    "cod": ym(g("Projected COD")), "phase": clean(g("GIM Study Phase")),
                    "ia_signed": ("signed" if ia.year < 1950 else ym(ia)) if isinstance(ia, (datetime.date, datetime.datetime)) else "",
                    "construction_start": ym(g("Construction Start")), "county": clean(g("County")).title(),
                    "poi": clean(g("POI Location")), "names": names, "tap": tap})
    return out


def in_place(e, rec):
    """Whether an end substation exists today, for K2 to check against what it already knows."""
    basis = e.get("basis") or ""
    if e.get("confidence") in ("exact", "approx") and re.search(r"\b(HIFLD|OpenStreetMap) (\d+ kV )?substation", basis, re.I) \
            and not re.search(r"not (in|on) (HIFLD|the HIFLD)", basis, re.I):
        return "on public maps"
    return "not on public maps"


def attach_queue(lines, places, path):
    """Join queue projects to catalog end substations by station name and county (or within 15 miles of it)."""
    idx = {}
    for x in lines:
        for e in x["endpoints"]:
            e["in_place"] = in_place(e, x)
            if e.get("lat") is not None:
                e["check_link"] = f"https://www.google.com/maps/@?api=1&map_action=map&center={e['lat']:.5f},{e['lon']:.5f}&zoom=16&basemap=satellite"
            b = alias(base(re.sub(r"^\d+\s+", "", clean(e["name"]))))
            if b:
                idx.setdefault(b, []).append((x, e))
        x["queue"] = {"projects": 0, "mw": 0, "developers": [], "stations": []}
    if not path or not os.path.exists(path):
        return []
    stations = {}
    for q in read_queue(path):
        for n in q["names"]:
            for x, e in idx.get(n, []):
                c = str(e.get("county") or "").title()
                if c != q["county"] and not (e.get("lat") is not None and places.near_county(e, q["county"], 15)):
                    continue
                st = same_station(stations, n, c, e, places)
                if not st:
                    sid = re.sub(r"[^a-z0-9]+", "-", f"{n} {c}".lower()).strip("-")
                    st = stations[sid] = {"id": sid, "base": n, "name": subname(e["name"]), "county": c, "lat": e.get("lat"), "lon": e.get("lon"),
                                          "confidence": e.get("confidence", ""), "in_place": e["in_place"], "lines": [], "projects": {}}
                elif st["lat"] is None and e.get("lat") is not None:
                    st.update(lat=e["lat"], lon=e["lon"], confidence=e.get("confidence", ""), in_place=e["in_place"])
                sid = st["id"]
                if x["id"] not in st["lines"]:
                    st["lines"].append(x["id"])
                other = [m for m in q["names"] if m != n]
                st["projects"][q["inr"]] = {k: q[k] for k in ("inr", "project", "developer", "fuel", "mw", "cod", "phase", "ia_signed", "construction_start", "poi")} | {
                    "connection": ("taps the line to " + other[0].title()) if q["tap"] and other else "taps a line here" if q["tap"] else "at the substation"}
                e["station_id"] = sid
    for st in stations.values():
        st.pop("base")
        st["projects"] = sorted(st["projects"].values(), key=lambda p: -p["mw"])
        st["mw"] = round(sum(max(p["mw"], 0) for p in st["projects"]), 1)
    by_id = {x["id"]: x for x in lines}
    for st in stations.values():
        for lid in st["lines"]:
            by_id[lid]["queue"]["stations"].append(st["id"])
    for x in lines:
        ps = {p["inr"]: p for sid in x["queue"]["stations"] for p in stations[sid]["projects"]}.values()
        devs = {}
        for p in ps:
            devs[p["developer"]] = devs.get(p["developer"], 0) + max(p["mw"], 0)
        x["queue"] = {"projects": len(ps), "mw": round(sum(max(p["mw"], 0) for p in ps), 1),
                      "developers": [d for d, _ in sorted(devs.items(), key=lambda kv: -kv[1])][:5], "stations": x["queue"]["stations"]}
    return sorted(stations.values(), key=lambda s: -s["mw"])


def same_station(stations, n, county, e, places):
    """One station that ERCOT lists under two counties (it sits near a county line) stays one station."""
    for st in stations.values():
        if st["base"] != n:
            continue
        if st["county"] == county:
            return st
        a, b = (st if st["lat"] is not None else None), (e if e.get("lat") is not None else None)
        if a and b and abs(a["lat"] - b["lat"]) < 0.15 and abs(a["lon"] - b["lon"]) < 0.15:
            return st
        if (a and places.near_county(a, county, 10)) or (b and places.near_county(b, st["county"], 10)):
            return st
    return None


RANK = {"exact": 0, "approx": 1, "town": 2, "county": 3, "unknown": 4}
STATUS_WHY = {"on maps": "on public maps (HIFLD or OpenStreetMap)", "existing line": "an existing line is being upgraded to it",
              "built line": "a line built in the last 3 years ends here", "new name": "ERCOT calls it new",
              "new per ERCOT": "ERCOT's project describes it as new", "expands": "ERCOT's project expands it", "more coming": "a new line, new substation work or transformer is planned here"}


def station_sites(lines, stations):
    """One record per end substation across every line: where it is, whether it exists today (existing, existing and
    expanding, new, or unconfirmed) and what is coming to it. Richard asked for existing vs new on the Oct 26 call."""
    sites, qst = [], {s["id"]: s for s in stations}

    def same(st, b, county, e):
        if st["_b"] != b:
            return False
        if st["county"] and county:
            if st["county"] == county:
                return True
        good = ("exact", "approx")
        if st["lat"] is not None and e.get("lat") is not None and st["confidence"] in good and e.get("confidence") in good:
            return abs(st["lat"] - e["lat"]) < 0.15 and abs(st["lon"] - e["lon"]) < 0.15
        return not (st["county"] and county)

    for x in lines:
        desc = " " + re.sub(r"[^A-Z0-9 ]+", " ", (x.get("description") or "").upper()) + " "
        title = " " + re.sub(r"[^A-Z0-9 ]+", " ", x["name"].upper()) + " "
        for e in x["endpoints"]:
            b = alias(base(re.sub(r"^\d+\s+", "", clean(e["name"])))) or clean(e["name"]).upper()
            if not b:
                continue
            county = str(e.get("county") or "").title()
            st = next((s for s in sites if same(s, b, county, e)), None)
            if not st:
                st = {"_b": b, "name": subname(e["name"]) or e["name"], "county": county, "lat": e.get("lat"), "lon": e.get("lon"),
                      "confidence": e.get("confidence") or "unknown", "basis": e.get("basis", ""), "_ev": set(), "lines": [], "_q": set(), "_roles": []}
                sites.append(st)
            elif RANK.get(e.get("confidence"), 4) < RANK.get(st["confidence"], 4):
                st.update(lat=e.get("lat"), lon=e.get("lon"), confidence=e.get("confidence"), basis=e.get("basis", ""), county=county or st["county"])
            if x["id"] not in st["lines"]:
                st["lines"].append(x["id"])
            ev = st["_ev"]
            if e.get("in_place") == "on public maps":
                ev.add("on maps")
            if x["project_type"] == "upgrade":
                ev.add("existing line")
            if x["lifecycle"] == "built":
                ev.add("built line")
            if re.match(r"new\b|.*newsub", e["name"], re.I):
                ev.add("new name")
            named = f" {b} " in title or f" {b} " in desc
            role = "upgrade" if x["project_type"] == "upgrade" else "other"
            if x["project_type"] in ("new line", "new substation") or x["transformer_mva"] or x["upgrade_kind"] == "voltage upgrade":
                role = "add"
            if named and re.search(r"\bEXPAN(D|DS|DING|SION)\b", title + desc):
                ev.update({"expands"} | ({"more coming"} if x["lifecycle"] != "built" else set()))
                role = "add"
            elif re.search(r"\b(NEW|GREENFIELD)\b(?: \w+){0,4} " + re.escape(b) + r"\b", desc) or re.match(r"new\b|.*newsub", e["name"], re.I) or \
                    (x["project_type"] == "new substation" and f" {b} " in title and re.search(r"\b(NEW|ESTABLISH)\b", title + desc)):
                ev.add("new per ERCOT")
                role = "new"
            if x["lifecycle"] != "built" and role == "add":
                ev.add("more coming")
            st["_roles"].append((x, role))
            if e.get("station_id"):
                st["_q"].add(e["station_id"])
            e["_site"] = st

    by_id, used = {x["id"]: x for x in lines}, set()
    for st in sites:
        ev = st.pop("_ev")
        existing, new = ev & {"on maps", "existing line", "built line", "expands"}, ev & {"new name", "new per ERCOT"} if "expands" not in ev else set()
        roles = st.pop("_roles")
        pick = lambda r: [x for x, role in roles if role == r]
        new_built = [x for x in pick("new") if x["lifecycle"] == "built"]
        new_open = [x for x in pick("new") if x["lifecycle"] != "built"]
        if new and "on maps" not in ev and new_open:
            status, why = "new", [STATUS_WHY[k] for k in sorted(new)]
            work = new_open
        elif existing or (new and new_built):
            work = [x for x in pick("add") + pick("new") if x["lifecycle"] != "built"]
            status = "existing, expanding" if work else "existing"
            why = [STATUS_WHY[k] for k in sorted(existing)] + ([f"built as a new substation, in service {new_built[0]['in_service']}"] if new_built else []) \
                + ([STATUS_WHY["more coming"]] if work else [])
            if not work:
                work = [x for x in pick("upgrade") if x["lifecycle"] != "built"]
        else:
            status, why = "unconfirmed", ["not on public maps by this name, and ERCOT doesn't say it is new; could be new or renamed"]
            work = [x for x, _ in roles if x["lifecycle"] != "built"]
        # Substation stage: what is happening at it, how far along, and whether it is there today.
        best = min(work, key=lambda x: (STAGES.index(x["lifecycle"]), x["in_service"] or "9999"), default=None)
        if status == "new":
            there, doing = "no", "building a new substation"
        elif status == "unconfirmed":
            adds = [x for x in work if x["project_type"] != "upgrade"]
            there, doing = "unknown", "new line or substation work planned" if adds else "upgrading lines to it" if work else "no new work"
        else:
            there = "yes"
            doing = ("adding to it (new line, transformer or expansion)" if status == "existing, expanding"
                     else "upgrading lines to it" if work else "no new work")
        sid = re.sub(r"[^a-z0-9]+", "-", f"{st['name']} {st['county']}".lower()).strip("-") or "station"
        n = 2
        while sid in used:
            sid, n = re.sub(r"-\d+$", "", sid) + f"-{n}", n + 1
        used.add(sid)
        ls = [by_id[i] for i in st["lines"]]
        future = sorted(x["in_service"] for x in ls if x["lifecycle"] != "built" and x["in_service"])
        qs = {p["inr"]: p for q in st.pop("_q") for p in qst.get(q, {}).get("projects", [])}.values()
        devs = {}
        for p in qs:
            devs[p["developer"]] = devs.get(p["developer"], 0) + max(p["mw"], 0)
        st.pop("_b")
        st.update(id=sid, status=status, status_reason="; ".join(why), there_now=there, work=doing,
                  work_stage=best["lifecycle"] if best else "", work_in_service=best["in_service"] if best else "",
                  work_project=best["name"] if best else "", max_kv=max(x["kv"] for x in ls),
                  stages={k: sum(x["lifecycle"] == k for x in ls) for k in STAGES if any(x["lifecycle"] == k for x in ls)},
                  next_in_service=future[0] if future else "", builders=sorted({x["utility"] for x in ls if x["utility"]}),
                  queue_projects=len(qs), queue_mw=round(sum(max(p["mw"], 0) for p in qs), 1),
                  queue_developers=[d for d, _ in sorted(devs.items(), key=lambda kv: -kv[1])][:5])
        if st["lat"] is not None:
            st["check_link"] = f"https://www.google.com/maps/@?api=1&map_action=map&center={st['lat']:.5f},{st['lon']:.5f}&zoom=16&basemap=satellite"
    for x in lines:
        for e in x["endpoints"]:
            st = e.pop("_site", None)
            if st:
                e.update(site_id=st["id"], station_status=st["status"], there_now=st["there_now"], work=st["work"],
                         work_stage=st["work_stage"], work_in_service=st["work_in_service"])
    return sorted(sites, key=lambda s: (-s["max_kv"], s["name"]))


def subname(n):
    return re.sub(r"\s*\(.*", "", re.sub(r"\s+", " ", str(n or ""))).strip()


def first_seen(lines):
    """Date each line first appeared in the catalog (sources/catalog-first-seen.json), so new entries stand out.
    A line ERCOT renumbered (73436 -> 73436B, or the same title and voltage under a new number) keeps its date."""
    f = os.path.join(HERE, "sources", "catalog-first-seen.json")
    seen = json.load(open(f)) if os.path.exists(f) else {}
    prev_f = os.path.join(WEB, "data", "texas-lines.json")
    prev = {}
    for x in (json.load(open(prev_f)).get("lines", []) if os.path.exists(prev_f) else []):
        if x.get("first_seen"):
            prev.setdefault((x["name"], x["kv"]), x["first_seen"])
    root = lambda i: re.sub(r"[A-Z]$", "", i)
    by_root = {}
    for i, d in seen.items():
        by_root[root(i)] = min(d, by_root.get(root(i), d))
    for x in lines:
        if x["id"] not in seen:
            seen[x["id"]] = by_root.get(root(x["id"])) or prev.get((x["name"], x["kv"])) or TODAY.isoformat()
        x["first_seen"] = seen[x["id"]]
    json.dump(dict(sorted(seen.items())), open(f, "w"), indent=0)


PHRASE_ALIASES = {"BELL COUNTY EAST": "BELL EAST", "GREENE ROAD": "GREENE"}


def alias(name):
    name = " ".join(ALIASES.get(w, w) for w in name.split())
    for a, b in PHRASE_ALIASES.items():
        name = re.sub(rf"\b{a}\b", b, name)
    return name


NAME_STOP = (r"(?:\d|transmission|trans\b|rebuild|dbl|double|2nd|second|line|ckt|circuit|upgrade|overhaul|reconductor|improvement|"
             r"kv|project|addition|phase|into|in\s+conjunction|part\s+of|for\b|and\s+rebuild|load\s+serving)")
NAME_LEAD = re.compile(r"^(?:(?:LCRA ?TSC|AEN|RCEC|BEPC|CPS ?E?|STEC|CTT|BRYN|TNMP|ONCOR'?S?|AEP|PL|LCRA)\s+|[,\s]*(?:approximately\s+|~)?\d+(?:\.\d+)?[- ](?:circuit\s+)?miles?\s+(?:of\s+)?|"
                       r"(?:to\s+)?(?:rebuild|upgrade|construct|install|establish|adds?|loop\s+in|new|the|existing|a|an|second|"
                       r"double[ -](?:ckt|circuit)(?:\s+lines?)?|2nd\s+circuit|transmission|lines?|from|of|between)[\s,]+)+", re.I)
NAME = r"[A-Z0-9][A-Za-z0-9.']*(?: [A-Za-z0-9.']+){0,3}?"   # up to four words
NOT_A_NAME = re.compile(r"\b(with|and|for|the|meet|current|conjunction|switchyard|distribution|expand|convert|build|connect|terminal|"
                        r"support|tline|facility|load|branch|existing|cutting|tier\d|ad-hoc|tpit|project|reliability|ginr)\b", re.I)


def title_ends(text):
    """Station names in a TPIT title or description, for rows whose terminal columns are blank or bus numbers:
    'Rebuild Hill Country to Marion Dbl Ckt' -> ['Hill Country', 'Marion']; 'Add Spadefoot 345 kV Switch' -> ['Spadefoot'];
    'AEN_Holman_Hillje_ckt_3123_reconductor' -> ['Holman', 'Hillje']."""
    raw = clean(text)
    m = re.match(r"^(?:[A-Z]+_)?(?:TPIT\d+_)?([A-Za-z]{3,})_([A-Za-z]{3,})_(?:ckt|transmission|improvement|reconductor)", raw, re.I)
    if m:
        return [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", g) for g in m.groups()]
    t = raw.replace("_", " ")
    head, _, tail = t.rpartition(":")
    t = re.sub(r"\((?:fka|formerly)[^)]*\)|\b\d+(?:[/-]\d+)?\s*-?\s*kV\b", " ", tail or t, flags=re.I)
    t = re.sub(r"\s*[-–]\s*(?:part\s+of|upgrade)\b.*$", "", t, flags=re.I)
    t = NAME_LEAD.sub("", re.sub(r"\s+", " ", t).strip())
    names = []
    m = re.search(r"^(" + NAME + r")\s+(?:switch(?:ing\s+station|yard)?|sub(?:station)?|station)\b", t, re.I)
    if m and not re.search(r"\s(?:to|into)\s", m[1], re.I):
        names = [m[1]]
    else:
        m = (re.search(r"between\s+(" + NAME + r")\s+and\s+(" + NAME + r")(?=\s+" + NAME_STOP + r"|\s*[\(:.,]|$)", t, re.I)
             or re.search(r"(" + NAME + r")(?:\s+to\s+|\s*[-–]\s*)(" + NAME + r")(?=\s+(?:to\s+)?" + NAME_STOP + r"|\s+to\s|\s*[\(:.,]|\s*[-\u2013]\s|$)", t, re.I))
        names = list(m.groups()) if m else ([t] if t and len(t.split()) <= 3 and not re.search(r"\d", t) else [])
    names = [n for n in names if not re.fullmatch(r"(?i)(sub)?station|switch(yard)?|substation", n.strip())]
    if not names and head and len(head.split()) <= 2 and not re.search(r"\d|project|reliability", head, re.I):
        names = [head]   # 'Montura: Construct New 345 kV Station'
    names = [re.sub(r"\s+to$", "", NAME_LEAD.sub("", n).strip()) for n in names]
    names = [re.sub(r"(?i)\s+load\s+serving$|^\d+\s+(?=[A-Za-z]{3})|^T\d+\s+", "", n.title() if n.islower() else n) for n in names]
    names = [n for n in names if len(n) >= 3]
    return [] if any(NOT_A_NAME.search(n) for n in names) else names


def terminals(r):
    """(name, county) for each end: ERCOT's terminal names, with bus numbers and blanks filled from the title or description.
    A filled-in bus-number end keeps its number in parentheses: 'Helotes (5200)'."""
    frm, to = str(r["from"] or "").strip(), str(r["to"] or "").strip()
    is_bus = lambda n: bool(re.fullmatch(r"[\d ,;]+", n))
    if (frm and not is_bus(frm)) and (to and not is_bus(to)) or (bool(frm) != bool(to) and not is_bus(frm or to)):
        return [(frm, r["county_from"]), (to, r["county_to"])]   # both named, or a one-station project
    title = "" if str(r["title"] or "").startswith(BOILERPLATE) else str(r["title"] or "")
    found = title_ends(title) or title_ends(str(r["desc"] or "").split(". ")[0])
    known = [n for n in (frm, to) if n and not is_bus(n)]
    spare = [n for n in found if all(base(n) != base(k) for k in known)]
    ends = []
    for n, county in ((frm, r["county_from"]), (to, r["county_to"])):
        if n and not is_bus(n):
            ends.append((n, county))
        elif spare:
            ends.append((spare.pop(0) + (f" ({n})" if n else ""), county or r["county_from"]))
        elif n:
            ends.append((n, county))
    return ends


def line_name(r, frm, to):
    title = str(r["title"] or "").strip()
    if title.startswith(BOILERPLATE):
        if frm and to:
            return f"{frm} to {to}"
        first = re.split(r"(?<=[a-z0-9])\.\s", clean(r["desc"]))[0].rstrip(".")
        return f"{first} (load addition)" if first else (f"{frm} to {to}" if frm and to else "Load addition upgrades")
    return title or (f"{frm} to {to}" if frm and to else frm)


def bus_names(queue_path):
    """ERCOT bus numbers to station names, from hookup points in the interconnection queue ('5133 Elm Creek 345kV',
    'Shaula (#5380)'). Used only for ends that are still a bare bus number."""
    if not queue_path or not os.path.exists(queue_path):
        return {}
    seen = {}
    word = r"([A-Z][A-Za-z.']+(?: [A-Z][A-Za-z.']+){0,2})"
    for q in read_queue(queue_path):
        t = re.sub(r"\b\d+(\.\d+)?\s*-?\s*kV\b", " ", q["poi"], flags=re.I)
        pairs = re.findall(r"(?:#|\b)(\d{3,6})\)?\s+" + word, t) + [(b, n) for n, b in re.findall(word + r"\s*\((?:bus\s*)?#?\s*(\d{3,6})\)", t, re.I)]
        for b, n in pairs:
            n = re.sub(r"\s+(Switch|Switching|Substation|Station|Sub|Line|Ckt)$", "", n.strip())
            if not re.match(r"(?i)(tap|bus|the|to|and|poi)\b", n):
                seen.setdefault(b, {}).setdefault(n, 0)
                seen[b][n] += 1
    return {b: max(c, key=c.get) for b, c in seen.items()}


def utility_name(u):
    """One spelling per utility: TPIT's codes ('ONCOR', 'LCRATSC') for the cards' 'Oncor' and 'LCRA TSC'."""
    return re.sub(r"\bLCRA TSC\b", "LCRATSC", re.sub(r"\bOncor\b", "ONCOR", str(u or "").strip()))


def route_miles(docket):
    """Length of the utility's recommended route in the filed route links (web/exports/routes/<docket>.geojson)."""
    f = os.path.join(WEB, "exports", "routes", f"{docket}.geojson")
    if not docket or not os.path.exists(f):
        return 0
    total = 0.0
    for ft in json.load(open(f))["features"]:
        if not ft["properties"].get("on_applicant_recommended_route"):
            continue
        g = ft["geometry"]
        for line in ([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]):
            for (x1, y1), (x2, y2) in zip(line, line[1:]):
                total += 69.17 * ((((x2 - x1) * math.cos(math.radians((y1 + y2) / 2))) ** 2 + (y2 - y1) ** 2) ** 0.5)
    return round(total, 1)


def card_facts():
    """Miles and in-service dates researched for cards ERCOT's report doesn't list (sources/card-facts.json)."""
    f = os.path.join(HERE, "sources", "card-facts.json")
    return {c["card_id"]: c for c in json.load(open(f))["cards"]} if os.path.exists(f) else {}


def card_index(projects):
    """Line Watch cards by their pair of end substations."""
    idx = {}
    for p in projects:
        names = [alias(base(e["name"])) for e in (p.get("geo") or {}).get("endpoints") or []]
        if len(names) == 2:
            idx[frozenset(names)] = p
    return idx


def cards_for(r, kv, cards):
    """Every card whose two end substations are both named in the TPIT row's title or terminals, at the same voltage
    ('Construct Mascho - Border - Drill Hole 345 kV DCKT Line' covers the Drill Hole to Border card)."""
    text = " " + alias(re.sub(r"[^A-Z0-9]+", " ", " ".join(str(r[k] or "") for k in ("title", "from", "to")).upper())) + " "
    return [p for pair, p in cards.items()
            if int(num(p.get("kv"))) == kv and all(f" {n} " in text for n in pair if n) and all(pair)]


def classify(r):
    title = "" if str(r["title"] or "").startswith(BOILERPLATE) else str(r["title"] or "")
    text = title + " " + str(r["desc"] or "")
    kv = int(num(r["kv"]))
    new_mi, upg_mi = num(r["new_mi"]), num(r["upg_mi"])
    if kv < 138 or EQUIPMENT.search(text) or (CAPACITOR.search(text) and new_mi < 1 and upg_mi < 1):
        return None
    same_corridor = new_mi >= 1 and new_mi == upg_mi and bool(REUSE.search(text))
    if new_mi >= 1 and not same_corridor:
        ptype, detail = "new line", "second circuit" if UPGRADE_KIND[3][1].search(text) else ""
    elif upg_mi >= 1:
        ptype = "upgrade"
        detail = next((k for k, rx in UPGRADE_KIND if rx.search(text)), "upgrade")
    elif kv >= 345 and NEW_STATION.search(text):
        ptype, detail = "new substation", ""
    else:
        return None
    gen = GENERATOR.search(text) or (POI.search(text) and not str(r["rpg"] or "").strip() and not GRID_PLAN.search(text))
    purpose = "generator hookup" if gen else "large-load hookup" if BIG_LOAD.search(text) else "shared grid"
    return kv, ptype, detail, purpose, same_corridor


def lifecycle(r, card, route):
    """Richard's five stages: built (last 3 years), in construction, approved, planned, proposed."""
    status = str(r["status"] or "").lower()
    actual = r["actual"] if isinstance(r["actual"], (datetime.date, datetime.datetime)) else None
    isd = r["isd"] if isinstance(r["isd"], (datetime.date, datetime.datetime)) else None
    if r["tab"] == "Completed" or status == "in-service" or actual:
        when = actual or isd
        return ("built", f"ERCOT: in service {ym(when)}") if when and when.date() >= CUTOFF else (None, "")
    if "construction" in status:
        return "in construction", "ERCOT: under construction"
    if card and card.get("stage", 0) >= 7:
        return "in construction", "Line Watch card: land buying or construction"
    if "conceptual" in status:
        return "proposed", "ERCOT: conceptual, not approved yet"
    if isd and isd.date() < TODAY.replace(day=1):
        return "in construction", f"estimated: planned in-service date {ym(isd)} has passed and ERCOT has not marked it in service yet"
    if card and card.get("stage") == 6:
        return "approved", "PUC approved the route (Line Watch card)"
    if route == "existing corridor":
        return "approved", "ERCOT: planned; an upgrade in its existing corridor, so there is no new route to approve"
    if isd and (isd.date() if isinstance(isd, datetime.datetime) else isd) <= TODAY + datetime.timedelta(days=548):
        return "approved", "estimated: planned to be in service within 18 months, so its route and site should be settled"
    return "planned", "ERCOT: planned; the route or site is not final yet"


def tap(kv):
    """K2 can tap 345 kV and below, maybe 500 kV, never 765 kV (Oct 26 team call)."""
    if kv >= 765:
        return "no", "Substation only: 765 kV lines are not tapped"
    if kv >= 500:
        return "maybe", "Maybe: a 500 kV tap is possible but not typical, so start at the substations"
    return "yes", "The line itself can be tapped (345 kV and below)"


def recommend(rec):
    located = [e for e in rec["endpoints"] if e.get("confidence") in ("exact", "approx")]
    if rec["purpose"] != "shared grid":
        return "informational", f"Serves one {'generator' if rec['purpose'] == 'generator hookup' else 'large load'}: no new shared capacity."
    if rec["lifecycle"] == "proposed":
        return "follow updates", "Still proposed: watch for ERCOT endorsement and end substations."
    route_set = rec["route_status"] in ("existing corridor", "approved route") or rec["lifecycle"] in ("in construction", "built")
    if rec["kv"] < 500 and route_set and rec["project_type"] != "new substation":
        return "line campaign", ("Upgrade of an existing line: the corridor is known" if rec["route_status"] == "existing corridor"
                                 else "Route is set") + f" and a {rec['kv']} kV line can be tapped along the way."
    if not located:
        return "follow updates", "End substation locations are not public yet."
    if rec["kv"] >= 500:
        return "substation campaign", f"{rec['kv']} kV lines are not tapped; projects connect at the end substations."
    return "substation campaign", "End substations are known; the route is not final yet."


def priority(rec):
    kv = {765: 40, 500: 35, 345: 25}.get(rec["kv"], 10)
    typ = {"new line": 15, "new substation": 12, "upgrade": 5}[rec["project_type"]]
    y = int(rec["in_service"][:4]) if rec["in_service"] else 2035
    when = 10 if rec["lifecycle"] == "built" else 20 if y <= TODAY.year + 1 else 15 if y == TODAY.year + 2 else 10 if y <= TODAY.year + 4 else 5
    score = kv + typ + when + min(rec["miles_new"], 100) / 10
    if rec["recommended_next_step"] == "informational":
        score -= 30
    return round(score, 1)


LINE_COLS = ["id", "name", "kv", "stage", "stage_detail", "in_service", "in_service_kind", "builder", "project_type", "upgrade_kind",
             "miles_new", "miles_upgraded", "purpose", "tappable", "tap_note", "from", "from_status", "from_there_now", "from_work", "from_work_stage",
             "to", "to_status", "to_there_now", "to_work", "to_work_stage", "county_from", "county_to",
             "location_quality", "queue_projects", "queue_mw", "queue_developers", "recommended_next_step", "recommendation_reason", "priority_score",
             "program", "rpg", "docket", "route_status", "ercot_project", "card_id", "first_seen", "market", "source"]
SITE_COLS = ["id", "name", "county", "status", "there_now", "work", "work_stage", "work_in_service", "work_project", "status_reason", "max_kv", "line_count", "lines", "stages", "next_in_service", "builders",
             "queue_projects", "queue_mw", "queue_developers", "location_quality", "location_basis", "check_link", "market"]
STAGE_COLOR = {"built": "ff7f7f7f", "in construction": "ff0000cc", "approved": "ff0080ff", "planned": "ff00b4e6", "proposed": "ffd29a3c"}  # KML aabbggrr


def line_props(x):
    ends = (x["endpoints"] + [{}, {}])[:2]
    worst = max((e.get("confidence") or "unknown" for e in x["endpoints"]), key=lambda c: RANK.get(c, 4), default="unknown")
    return {"feature_type": "line", **{k: x.get(k, "") for k in LINE_COLS if k in x}, "stage": x["lifecycle"], "stage_detail": x["lifecycle_basis"],
            "builder": x["utility"], **{f"{side}_{k}": e.get(src, "") for side, e in zip(("from", "to"), ends)
                                         for k, src in (("status", "station_status"), ("there_now", "there_now"), ("work", "work"), ("work_stage", "work_stage"))},
            "location_quality": worst, "queue_projects": x["queue"]["projects"], "queue_mw": x["queue"]["mw"],
            "queue_developers": "; ".join(x["queue"]["developers"])}


def site_props(st, names):
    return {"feature_type": "substation", **{k: st[k] for k in ("id", "name", "county", "status", "there_now", "work", "work_stage", "work_in_service",
                                                                "work_project", "status_reason", "max_kv", "next_in_service",
                                                                "queue_projects", "queue_mw", "check_link") if k in st},
            "line_count": len(st["lines"]), "lines": "; ".join(names[i] for i in st["lines"][:12]) + (f"; +{len(st['lines']) - 12} more" if len(st["lines"]) > 12 else ""),
            "stages": "; ".join(f"{k} {v}" for k, v in st["stages"].items()), "builders": "; ".join(st["builders"]),
            "queue_developers": "; ".join(st["queue_developers"]), "location_quality": st["confidence"], "location_basis": st["basis"], "market": MARKET}


def write_exports(out, sites):
    """Line table, substation table, and one combined GIS layer (lines + substations) as GeoJSON and KML.
    Steve asked for one file with everything, which is easier to split than to piece back together."""
    ex = os.path.join(WEB, "exports")
    names = {x["id"]: x["name"] for x in out}
    with open(os.path.join(ex, "k2-texas-lines.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, LINE_COLS, extrasaction="ignore")
        w.writeheader()
        for x in out:
            w.writerow(line_props(x))
    with open(os.path.join(ex, "k2-texas-substations.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["id", "name", "county", "lat", "lon"] + SITE_COLS[3:], extrasaction="ignore")
        w.writeheader()
        for st in sites:
            w.writerow({**site_props(st, names), "lat": st["lat"] if st["lat"] is not None else "", "lon": st["lon"] if st["lon"] is not None else ""})
    line_feats, site_feats = [], []
    for x in out:
        pts = [e for e in x["endpoints"] if e.get("lat") is not None]
        if not pts:
            continue
        props = line_props(x)
        if len(pts) >= 2:
            geom = {"type": "LineString", "coordinates": [[e["lon"], e["lat"]] for e in pts]}
            props["geometry_note"] = "Straight line between the end substations, not the route"
        else:
            geom = {"type": "Point", "coordinates": [pts[0]["lon"], pts[0]["lat"]]}
            props["geometry_note"] = "Only one end substation can be placed; point at that end"
        line_feats.append({"type": "Feature", "properties": props, "geometry": geom})
    for st in sites:
        if st["lat"] is not None:
            site_feats.append({"type": "Feature", "properties": site_props(st, names), "geometry": {"type": "Point", "coordinates": [st["lon"], st["lat"]]}})
    json.dump({"type": "FeatureCollection", "features": line_feats}, open(os.path.join(ex, "k2-texas-lines.geojson"), "w"))
    json.dump({"type": "FeatureCollection", "name": "K2 Line Watch Texas", "features": line_feats + site_feats},
              open(os.path.join(ex, "k2-texas-layer.geojson"), "w"))
    write_kml(os.path.join(ex, "k2-texas-layer.kml"), line_feats, site_feats)
    shutil.copyfile(os.path.join(ex, "k2-texas-layer.kml"), os.path.join(ex, "k2-texas-layer.kml.xml"))   # the page serves .kml as .xml


def write_kml(path, line_feats, site_feats):
    from xml.sax.saxutils import escape
    def placemark(f, style):
        p, g = f["properties"], f["geometry"]
        data = "".join(f'<Data name="{escape(str(k))}"><value>{escape(str(v))}</value></Data>' for k, v in p.items() if v not in ("", None))
        if g["type"] == "LineString":
            shape = "<LineString><tessellate>1</tessellate><coordinates>" + " ".join(f"{a},{b},0" for a, b in g["coordinates"]) + "</coordinates></LineString>"
        else:
            shape = f"<Point><coordinates>{g['coordinates'][0]},{g['coordinates'][1]},0</coordinates></Point>"
        return f"<Placemark><name>{escape(p['name'])}</name><styleUrl>#{style}</styleUrl><ExtendedData>{data}</ExtendedData>{shape}</Placemark>"
    styles = "".join(f'<Style id="{k.replace(" ", "-")}"><LineStyle><color>{c}</color><width>3</width></LineStyle><IconStyle><color>{c}</color></IconStyle></Style>'
                     for k, c in STAGE_COLOR.items())
    styles += "".join(f'<Style id="sub-{k.replace(", ", "-")}"><IconStyle><color>{c}</color><scale>0.8</scale></IconStyle></Style>'
                      for k, c in {"new": "ff00b4e6", "existing, expanding": "ff0080ff", "existing": "ff7f7f7f", "unconfirmed": "ffd29a3c"}.items())
    folders = []
    for stage in STAGES:
        fs = [f for f in line_feats if f["properties"]["stage"] == stage]
        folders.append(f"<Folder><name>Lines: {stage} ({len(fs)})</name>" + "".join(placemark(f, stage.replace(" ", "-")) for f in fs) + "</Folder>")
    for status in ("new", "existing, expanding", "existing", "unconfirmed"):
        fs = [f for f in site_feats if f["properties"]["status"] == status]
        folders.append(f"<Folder><name>Substations: {status} ({len(fs)})</name>" + "".join(placemark(f, "sub-" + status.replace(", ", "-")) for f in fs) + "</Folder>")
    with open(path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>K2 Line Watch: Texas</name>'
                "<description>Straight lines between end substations, not routes.</description>" + styles + "".join(folders) + "</Document></kml>")


def build(projects_src, tpit_path, queue_path=None):
    projects = [p for p in load_projects(projects_src) if str(p.get("region", "Texas")).startswith("Texas")]
    places, cards, facts, buses = Places(projects), card_index(projects), card_facts(), bus_names(queue_path)
    out, used_cards = [], set()
    rows = read_tpit(tpit_path)
    for r in rows:
        r["src"] = "October 1, 2026 update (posted Oct 23, 2026)"
    rows += history_rows({str(r["id"]) for r in rows})
    for r in rows:
        c = classify(r)
        if not c:
            continue
        kv, ptype, detail, purpose, same_corridor = c
        frm, to = str(r["from"] or "").strip(), str(r["to"] or "").strip()
        matched = cards_for(r, kv, cards)
        card = (cards.get(frozenset([alias(base(frm)), alias(base(to))])) if frm and to else None) or \
            min(matched, key=lambda p: p.get("stage", 0), default=None)  # a line spanning two cards is as far along as its slower part
        matched = list({p["id"]: p for p in ([card] if card else []) + matched}.values())
        route = "existing corridor" if ptype == "upgrade" else STAGE_ROUTE.get((card or {}).get("stage"), "end substations only")
        life, life_basis = lifecycle(r, card, route)
        if not life:
            continue
        ends = []
        for name, county in terminals(r):
            if re.fullmatch(r"[\d ,;]+", name or ""):   # still bare bus numbers: name them from the queue when it can
                named = [buses[b] for b in re.findall(r"\d+", name) if b in buses]
                name = f"{' / '.join(named)} ({name})" if named else name
            if not name or (ends and (base(name) or clean(name)) == (base(ends[0]["name"]) or clean(ends[0]["name"]))):
                continue
            bus = re.search(r"\((\d+)\)$", name)   # researched points can be keyed by bus number
            hit = (places.find(bus[1], county) if bus else None) or places.find(name, county)
            if hit:
                hit["name"] = name
            ends.append(hit or places.county_point(name, county))
        if ends:
            frm, to = ends[0]["name"], ends[-1]["name"] if len(ends) > 1 else ""
        rpg = str(r["rpg"] or "").strip()
        rec = {"id": "tpit-" + str(r["id"]).strip(), "ercot_project": str(r["id"]).strip(), "name": line_name(r, frm, to),
               "description": re.sub(r"\s+", " ", str(r["desc"] or "")).strip()[:400], "kv": kv, "project_type": ptype, "upgrade_kind": detail,
               "lifecycle": life, "lifecycle_basis": life_basis, "tpit_status": str(r["status"] or ""), "utility": utility_name(r["owner"]),
               "from": frm, "to": to, "county_from": str(r["county_from"] or "").strip(), "county_to": str(r["county_to"] or "").strip(),
               "miles_new": 0 if same_corridor else round(num(r["new_mi"]), 1), "miles_upgraded": round(num(r["upg_mi"]), 1), "transformer_mva": int(num(r["mva"])),
               "in_service": ym(r["actual"]) or ym(r["isd"]), "in_service_kind": "actual" if r["actual"] else "projected",
               "construction_start": "", "capacity_mw": None, "purpose": purpose,
               "program": PROGRAMS.get(rpg, f"ERCOT RPG {rpg}" if re.match(r"\d{2}RPG\d{3}", rpg) else ""),
               "rpg": rpg, "tier": str(r["tier"] or "").strip(), "ercot_board": ym(r["board"]), "docket": (card or {}).get("docket", ""),
               "route_status": route, "card_id": (card or {}).get("id", ""), "card_ids": [p["id"] for p in matched], "endpoints": ends,
               "source": f"ERCOT TPIT ({TPIT_URL}), {r['src']}", "checked": "ERCOT TPIT " + r["src"].split(" (")[0], "market": MARKET}
        if rec["in_service"] and rec["in_service"][:7] > HORIZON:
            used_cards.update(p["id"] for p in matched)   # its card is out of the window too
            continue
        rec["tappable"], rec["tap_note"] = tap(kv)
        rec["recommended_next_step"], rec["recommendation_reason"] = recommend(rec)
        rec["priority_score"] = priority(rec)
        used_cards.update(p["id"] for p in matched)
        out.append(rec)

    # Line Watch cards ERCOT's report doesn't list yet (early signals, open houses, news).
    for p in projects:
        if p["id"] in used_cards or not p.get("geo", {}).get("endpoints"):
            continue
        ends = [{k: e.get(k) for k in ("name", "county", "lat", "lon", "confidence", "basis", "source")} for e in p["geo"]["endpoints"]]
        for e in ends:
            e["county"] = str(e.get("county") or "").split("|")[-1]
        stage = p.get("stage", 2)
        fact = facts.get(p["id"], {})
        miles = num(fact.get("miles")) or num((re.search(r"\d+(?:\.\d+)?", str(p.get("miles") or "")) or [0])[0]) or route_miles(p.get("docket"))
        said = re.search(r"(?:in[ -]service|complet\w*|energiz\w*|online)\D{0,25}?(20\d\d)", f"{p.get('next_step', '')} {p.get('status', '')}", re.I)
        isd = fact.get("in_service") or (said[1] if said else "")
        life = {2: "proposed", 3: "planned", 4: "planned", 5: "planned", 6: "approved", 7: "in construction"}.get(stage, "planned")
        basis = "Line Watch card stage " + str(stage)
        if isd and life != "in construction" and isd[:7] < TODAY.strftime("%Y-%m"):
            life, basis = "in construction", f"estimated: planned in-service date {isd} has passed"
        rec = {"id": "card-" + p["id"], "ercot_project": "", "name": p["name"], "description": p.get("status", ""), "kv": int(num(p.get("kv"))) or 345,
               "project_type": "new line", "upgrade_kind": "", "lifecycle": life, "lifecycle_basis": basis,
               "tpit_status": "", "utility": utility_name(p.get("utility")), "from": ends[0]["name"], "to": ends[-1]["name"],
               "county_from": ends[0]["county"], "county_to": ends[-1]["county"], "miles_new": miles,
               "miles_upgraded": 0, "transformer_mva": 0, "in_service": isd, "in_service_kind": "projected" if isd else "", "construction_start": "", "capacity_mw": None,
               "purpose": "shared grid", "program": PROGRAMS.get(str(p.get("rpg", "")).split(" ")[0], p.get("rpg", "")), "rpg": p.get("rpg", ""),
               "tier": "", "ercot_board": "", "docket": p.get("docket", ""), "route_status": STAGE_ROUTE.get(stage, "end substations only"),
               "card_id": p["id"], "card_ids": [p["id"]], "endpoints": ends, "checked": p.get("checked", ""), "market": MARKET,
               "source": "; ".join(dict.fromkeys([l["url"] for l in p.get("links", [])[:2]] + [fact[k] for k in ("miles_source", "in_service_source") if fact.get(k)]))}
        if rec["in_service"] and rec["in_service"][:7] > HORIZON:
            continue
        rec["tappable"], rec["tap_note"] = tap(rec["kv"])
        rec["recommended_next_step"], rec["recommendation_reason"] = recommend(rec)
        rec["priority_score"] = priority(rec)
        out.append(rec)

    out += oncor_lines(out, places)
    out.sort(key=lambda x: -x["priority_score"])
    stations = attach_queue(out, places, queue_path)
    sites = station_sites(out, stations)
    first_seen(out)
    os.makedirs(os.path.join(WEB, "data"), exist_ok=True)
    meta = {"built": TODAY.isoformat(), "count": len(out), "queue_report": queue_label(queue_path),
            "sources": {"ERCOT TPIT": TPIT_URL, "HIFLD substations": HIFLD_URL, "ERCOT interconnection queue (GIS report)": QUEUE_URL},
            "scope": f"ERCOT Texas: new and upgraded lines 138 kV and up and new 345 kV+ substations, from proposed to built since {CUTOFF:%B %Y}, in service by {HORIZON}, plus Line Watch cards not yet in TPIT",
            "cutoff": CUTOFF.isoformat(), "horizon": HORIZON, "stages": STAGE_HELP}
    json.dump({**meta, "lines": out, "stations": stations, "sites": sites}, open(os.path.join(WEB, "data", "texas-lines.json"), "w"), separators=(",", ":"))

    dcols = ["station", "county", "lat", "lon", "station_status", "lines", "line_names", "max_kv", "inr", "project", "developer", "fuel", "mw",
             "cod", "phase", "ia_signed", "construction_start", "connection", "poi"]
    names = {x["id"]: x for x in out}
    with open(os.path.join(WEB, "exports", "k2-texas-developers.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, dcols, extrasaction="ignore")
        w.writeheader()
        for st in stations:
            ls = sorted((names[i] for i in st["lines"]), key=lambda x: -x["priority_score"])
            for p in st["projects"]:
                w.writerow({**p, "station": st["name"], "county": st["county"], "lat": st["lat"], "lon": st["lon"], "station_status": st["in_place"],
                            "lines": " ".join(st["lines"]), "line_names": "; ".join(x["name"] for x in ls[:3]), "max_kv": max(x["kv"] for x in ls)})

    write_exports(out, sites)
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "projects.json")
    tpit = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "sources", "ercot-tpit-2026-10.xlsx")
    queue = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "sources", "ercot-gis-report-2026-09.xlsx")
    lines = build(src, tpit, queue)
    from collections import Counter
    print(len(lines), "lines")
    print(Counter(x["lifecycle"] for x in lines))
    print(Counter(x["recommended_next_step"] for x in lines))
    print(Counter(x["project_type"] for x in lines), Counter(x["kv"] for x in lines))
    q = [x for x in lines if x["queue"]["projects"]]
    print(len(q), "lines with queued projects;", sum(x["queue"]["projects"] > 0 for x in lines if x["recommended_next_step"] != "informational"), "excluding informational")
    print(Counter(e.get("in_place") for x in lines for e in x["endpoints"]))
    sites = json.load(open(os.path.join(WEB, "data", "texas-lines.json")))["sites"]
    print(len(sites), "substations", Counter(s["status"] for s in sites), Counter(s["confidence"] for s in sites))
