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
import os
import re
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")
TPIT_URL = "https://www.ercot.com/gridinfo/planning"
HIFLD_URL = "https://services5.arcgis.com/HDRa0B57OVrv2E1q/ArcGIS/rest/services/Electric_Substations/FeatureServer/0"
QUEUE_URL = "https://www.ercot.com/misapp/GetReports.do?reportTypeId=15933"
TODAY = datetime.date.today()

PROGRAMS = {"25RPG025": "ERCOT 765 kV STEP: Eastern Backbone", "H.B. 5066": "Permian Basin Reliability Plan (HB 5066)"}
GENERATOR = re.compile(r"GEN[ -]?TIE|\bGEN\b|GENERATION|BESS|SOLAR|WIND|STORAGE|\bESR\b|\d{2}INR\d{3,4}|\bG?INR\b|POWER PLANT", re.I)
# 'POI' alone is weaker: it also names a hookup to another utility or a co-op delivery point inside a grid plan.
POI = re.compile(r"\bPOI\b", re.I)
GRID_PLAN = re.compile(r"RELIABILITY PLAN|\d{2}RPG\d{3}|\bPOI\)? WITH\b", re.I)
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


class Places:
    """Substation points: Line Watch card pins first, then HIFLD by name + county."""
    def __init__(self, projects):
        self.cards = {}
        for p in projects:
            for e in (p.get("geo") or {}).get("endpoints") or []:
                if e.get("lat") is None:
                    continue
                st, _, cty = (e.get("county") or "|").partition("|")
                self.cards.setdefault((base(e["name"]), st), {**e, "basis": e.get("basis", ""), "from": "Line Watch card"})
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
        self.boxes = {}
        for k, rings in json.load(open(os.path.join(WEB, "counties.json"))).items():
            xs = [x for r in rings for x, _ in r]
            ys = [y for r in rings for _, y in r]
            self.boxes[k] = (min(xs), min(ys), max(xs), max(ys))
        # Named OpenStreetMap substations (sources/osm-tx-substations.json): many stations HIFLD leaves unnamed.
        osm = os.path.join(HERE, "sources", "osm-tx-substations.json")
        self.osm = {}
        for s in (json.load(open(osm))["substations"] if os.path.exists(osm) else []):
            self.osm.setdefault(base(s["name"]), []).append(s)

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
    if re.search(r"\b(HIFLD|OpenStreetMap) (\d+ kV )?substation", basis, re.I) and not re.search(r"not (in|on) (HIFLD|the HIFLD)", basis, re.I):
        return "on public maps"
    if re.match(r"new\b", e["name"], re.I) or (rec["project_type"] == "new substation" and NEW_STATION.search(rec["description"])):
        return "new or expanding (per ERCOT)"
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


def subname(n):
    return re.sub(r"\s*\(.*", "", re.sub(r"\s+", " ", str(n or ""))).strip()


def first_seen(lines):
    """Date each line first appeared in the catalog (sources/catalog-first-seen.json), so new entries stand out."""
    f = os.path.join(HERE, "sources", "catalog-first-seen.json")
    seen = json.load(open(f)) if os.path.exists(f) else {}
    for x in lines:
        x["first_seen"] = seen.setdefault(x["id"], TODAY.isoformat())
    json.dump(dict(sorted(seen.items())), open(f, "w"), indent=0)


def alias(name):
    return " ".join(ALIASES.get(w, w) for w in name.split())


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
    text = " ".join(str(r[k] or "") for k in ("title", "desc"))
    kv = int(num(r["kv"]))
    if kv < 138 or EQUIPMENT.search(text):
        return None
    new_mi, upg_mi = num(r["new_mi"]), num(r["upg_mi"])
    if new_mi >= 1:
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
    return kv, ptype, detail, purpose


def lifecycle(r, card):
    status = str(r["status"] or "").lower()
    actual = r["actual"] if isinstance(r["actual"], (datetime.date, datetime.datetime)) else None
    isd = r["isd"] if isinstance(r["isd"], (datetime.date, datetime.datetime)) else None
    if r["tab"] == "Completed" or status == "in-service" or actual:
        when = actual or isd
        return ("operating (recently built)", "TPIT actual in-service date") if when and when.year >= TODAY.year else (None, "")
    if "construction" in status:
        return "in construction", "TPIT status"
    if card and card.get("stage", 0) >= 7:
        return "in construction", "Line Watch card stage"
    if "conceptual" in status:
        return "proposed", "TPIT status (conceptual)"
    if card and card.get("stage") == 6:
        return "about to enter construction", "route approved (Line Watch card)"
    if isd and (isd.date() if isinstance(isd, datetime.datetime) else isd) <= TODAY + datetime.timedelta(days=548):
        return "about to enter construction", "estimated: planned to be in service within 18 months"
    return "planned", "TPIT status"


def recommend(rec):
    located = [e for e in rec["endpoints"] if e.get("confidence") in ("exact", "approx")]
    if rec["purpose"] != "shared grid":
        return "informational", f"Serves one {'generator' if rec['purpose'] == 'generator hookup' else 'large load'}: no new shared capacity."
    if rec["lifecycle"] == "proposed":
        return "follow updates", "Still proposed: watch for ERCOT endorsement and end substations."
    route_set = rec["route_status"] in ("existing corridor", "approved route") or rec["lifecycle"] in ("in construction", "operating (recently built)")
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
    when = 10 if rec["lifecycle"].startswith("operating") else 20 if y <= TODAY.year + 1 else 15 if y == TODAY.year + 2 else 10 if y <= TODAY.year + 4 else 5
    score = kv + typ + when + min(rec["miles_new"], 100) / 10
    if rec["recommended_next_step"] == "informational":
        score -= 30
    return round(score, 1)


def build(projects_src, tpit_path, queue_path=None):
    projects = [p for p in load_projects(projects_src) if str(p.get("region", "Texas")).startswith("Texas")]
    places, cards = Places(projects), card_index(projects)
    out, used_cards = [], set()
    for r in read_tpit(tpit_path):
        c = classify(r)
        if not c:
            continue
        kv, ptype, detail, purpose = c
        frm, to = str(r["from"] or "").strip(), str(r["to"] or "").strip()
        matched = cards_for(r, kv, cards)
        card = (cards.get(frozenset([alias(base(frm)), alias(base(to))])) if frm and to else None) or \
            min(matched, key=lambda p: p.get("stage", 0), default=None)  # a line spanning two cards is as far along as its slower part
        matched = list({p["id"]: p for p in ([card] if card else []) + matched}.values())
        life, life_basis = lifecycle(r, card)
        if not life:
            continue
        ends = []
        for name, county in ((frm, r["county_from"]), (to, r["county_to"])):
            if not name or (ends and base(name) == base(ends[0]["name"])):
                continue
            ends.append(places.find(name, county) or {"name": name, "county": county or "", "confidence": "unknown",
                                                       "basis": "Not on the Line Watch cards or the HIFLD substation map (new or renamed station)"})
        rpg = str(r["rpg"] or "").strip()
        route = "existing corridor" if ptype == "upgrade" else STAGE_ROUTE.get((card or {}).get("stage"), "end substations only")
        rec = {"id": "tpit-" + str(r["id"]).strip(), "ercot_project": str(r["id"]).strip(), "name": (f"{frm} to {to}" if (not r["title"] or str(r["title"]).startswith("This models")) and frm and to else str(r["title"] or frm).strip()),
               "description": re.sub(r"\s+", " ", str(r["desc"] or "")).strip()[:400], "kv": kv, "project_type": ptype, "upgrade_kind": detail,
               "lifecycle": life, "lifecycle_basis": life_basis, "tpit_status": str(r["status"] or ""), "utility": str(r["owner"] or "").strip(),
               "from": frm, "to": to, "county_from": str(r["county_from"] or "").strip(), "county_to": str(r["county_to"] or "").strip(),
               "miles_new": round(num(r["new_mi"]), 1), "miles_upgraded": round(num(r["upg_mi"]), 1), "transformer_mva": int(num(r["mva"])),
               "in_service": ym(r["actual"]) or ym(r["isd"]), "in_service_kind": "actual" if r["actual"] else "projected",
               "construction_start": "", "capacity_mw": None, "purpose": purpose,
               "program": PROGRAMS.get(rpg, f"ERCOT RPG {rpg}" if re.match(r"\d{2}RPG\d{3}", rpg) else ""),
               "rpg": rpg, "tier": str(r["tier"] or "").strip(), "ercot_board": ym(r["board"]), "docket": (card or {}).get("docket", ""),
               "route_status": route, "card_id": (card or {}).get("id", ""), "card_ids": [p["id"] for p in matched], "endpoints": ends,
               "source": f"ERCOT TPIT ({TPIT_URL}), July 13, 2026 update", "checked": "ERCOT TPIT 2026-07-13"}
        rec["tap_note"] = "Projects connect at the substations" if kv >= 500 else "The line itself can be tapped"
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
        life = {2: "planned", 3: "planned", 4: "planned", 5: "planned", 6: "about to enter construction", 7: "in construction"}.get(stage, "planned")
        rec = {"id": "card-" + p["id"], "ercot_project": "", "name": p["name"], "description": p.get("status", ""), "kv": int(num(p.get("kv"))) or 345,
               "project_type": "new line", "upgrade_kind": "", "lifecycle": life, "lifecycle_basis": "Line Watch card stage " + str(stage),
               "tpit_status": "", "utility": p.get("utility", ""), "from": ends[0]["name"], "to": ends[-1]["name"],
               "county_from": ends[0]["county"], "county_to": ends[-1]["county"], "miles_new": num(re.sub(r"[^0-9.]", "", p.get("miles", "")) or 0),
               "miles_upgraded": 0, "transformer_mva": 0, "in_service": "", "in_service_kind": "", "construction_start": "", "capacity_mw": None,
               "purpose": "shared grid", "program": PROGRAMS.get(str(p.get("rpg", "")).split(" ")[0], p.get("rpg", "")), "rpg": p.get("rpg", ""),
               "tier": "", "ercot_board": "", "docket": p.get("docket", ""), "route_status": STAGE_ROUTE.get(stage, "end substations only"),
               "card_id": p["id"], "card_ids": [p["id"]], "endpoints": ends, "source": "; ".join(l["url"] for l in p.get("links", [])[:2]), "checked": p.get("checked", "")}
        rec["tap_note"] = "Projects connect at the substations" if rec["kv"] >= 500 else "The line itself can be tapped"
        rec["recommended_next_step"], rec["recommendation_reason"] = recommend(rec)
        rec["priority_score"] = priority(rec)
        out.append(rec)

    out.sort(key=lambda x: -x["priority_score"])
    stations = attach_queue(out, places, queue_path)
    first_seen(out)
    os.makedirs(os.path.join(WEB, "data"), exist_ok=True)
    meta = {"built": TODAY.isoformat(), "count": len(out), "queue_report": queue_label(queue_path),
            "sources": {"ERCOT TPIT": TPIT_URL, "HIFLD substations": HIFLD_URL, "ERCOT interconnection queue (GIS report)": QUEUE_URL},
            "scope": "ERCOT Texas: new and upgraded lines 138 kV and up, new 345 kV+ substations, lines energized this year, plus Line Watch cards not yet in TPIT"}
    json.dump({**meta, "lines": out, "stations": stations}, open(os.path.join(WEB, "data", "texas-lines.json"), "w"), separators=(",", ":"))

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

    cols = ["id", "name", "kv", "project_type", "upgrade_kind", "lifecycle", "in_service", "in_service_kind", "utility", "from", "to",
            "county_from", "county_to", "miles_new", "miles_upgraded", "purpose", "program", "rpg", "docket", "route_status",
            "recommended_next_step", "recommendation_reason", "tap_note", "priority_score", "from_lat", "from_lon", "from_location",
            "to_lat", "to_lon", "to_location", "from_status", "to_status", "queue_projects", "queue_mw", "queue_developers",
            "first_seen", "card_id", "ercot_project", "source"]
    with open(os.path.join(WEB, "exports", "k2-texas-lines.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        for x in out:
            row = dict(x)
            for side, e in zip(("from", "to"), (x["endpoints"] + [{}, {}])[:2]):
                row[side + "_lat"], row[side + "_lon"], row[side + "_location"] = e.get("lat", ""), e.get("lon", ""), e.get("confidence", "")
                row[side + "_status"] = e.get("in_place", "")
            row["queue_projects"], row["queue_mw"], row["queue_developers"] = x["queue"]["projects"], x["queue"]["mw"], "; ".join(x["queue"]["developers"])
            w.writerow(row)
    feats = []
    for x in out:
        pts = [e for e in x["endpoints"] if e.get("lat") is not None]
        props = {k: x[k] for k in cols if k in x} | {"queue_projects": x["queue"]["projects"], "queue_mw": x["queue"]["mw"],
                                                      "queue_developers": "; ".join(x["queue"]["developers"])}
        if len(pts) >= 2:
            geom = {"type": "LineString", "coordinates": [[e["lon"], e["lat"]] for e in pts]}
            props["geometry_note"] = "Straight line between the end substations, not the route"
        elif pts:
            geom = {"type": "Point", "coordinates": [pts[0]["lon"], pts[0]["lat"]]}
        else:
            continue
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(WEB, "exports", "k2-texas-lines.geojson"), "w"))
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "projects.json")
    tpit = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "sources", "ercot-tpit-2026-07.xlsx")
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
