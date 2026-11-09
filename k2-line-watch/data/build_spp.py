"""SPP lines for Line Watch: the Texas Panhandle / South Plains and Oklahoma.

Source: SPP's 2026 Transmission Expansion Plan (STEP) project list, Appendix 1 (sources/spp-step-2026.xlsx), from
https://www.spp.org/documents/76727/2026%20spp%20transmission%20expansion%20(step)%20plan.zip
Every upgrade SPP has approved or is tracking, with owner, state, in-service date, status and end buses.

Same scope and stages as the ERCOT list: new and rebuilt lines 138 kV and up and new 345 kV+ substations, built in the
last 3 years or due within the next 5. Terminal equipment, transformers, reactors and 69/115 kV work are left out.

    python3 data/build_spp.py        # prints what it would add
"""
import datetime
import difflib
import json
import math
import os
import re
from collections import Counter

import openpyxl

import build_catalog as B

STEP_URL = "https://www.spp.org/engineering/transmission-planning/"
STEP_FILE = os.path.join(B.HERE, "sources", "spp-step-2026.xlsx")
STEP_LABEL = "2026 STEP project list (Appendix 1, posted Oct 2026)"
STEP_DOC = "76727"   # SPP document id of the STEP zip this list was built from (lw.py texas watches for a newer one)
STATE_NAME = {"TX": "Texas", "OK": "Oklahoma", "AR": "Arkansas", "KS": "Kansas", "MO": "Missouri", "NM": "New Mexico"}
HOME = ("TX", "OK")              # the states this list covers
NEIGHBORS = ("AR", "KS", "MO", "NM")   # where a line leaving Oklahoma or the Panhandle can end
STATE_BOX = {"TX": (-106.7, 25.8, -93.5, 36.6), "OK": (-103.1, 33.6, -94.4, 37.1)}
OWNERS = {"SPS": "SPS (Xcel Energy)", "OGE": "OG&E", "AEP": "AEP (PSO / SWEPCO)", "WFEC": "Western Farmers", "GRDA": "GRDA",
          "ETEC": "ETEC", "LEA": "Lea County Coop", "NEET": "NextEra (NEET)", "TBD": "not assigned yet"}
BUILT = {"complete", "in service", "closed out"}
EARLY = {"identified", "re-evaluation", "pending ntc/ntc-c"}
EXTRA = r"\b(INTERCHANGE|INT|EHV|SUBSTATION|SUB|SWITCHING|STATION|SW|CKT\s*\d*|CIRCUIT\s*\d*|PLANT)\b"


def norm(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ")).strip()


def sbase(name):
    """'Lubbock South Interchange 230 kV' -> 'LUBBOCK SOUTH'; 'CLEO JCT' -> 'CLEO JUNCTION'; 'MATHEWSON 345' -> 'MATHEWSON'."""
    n = B.base(re.sub(r"\(.*?\)", " ", norm(name)))
    n = re.sub(EXTRA, " ", n)
    n = re.sub(r"\bJCT\b", "JUNCTION", n)
    n = re.sub(r"^FT\b", "FORT", n)
    n = re.sub(r"\s\d{2,3}(\s?KV)?$", "", re.sub(r"\s+", " ", n).strip())
    return re.sub(r"\s+", " ", n).strip()


def read_step(path=STEP_FILE):
    rows = list(openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True))
    head = next(i for i, r in enumerate(rows) if r and norm(r[0]) == "NTC ID")
    cols = [norm(c) for c in rows[head]]
    out = []
    for r in rows[head + 1:]:
        if not any(r):
            continue
        d = dict(zip(cols, r))
        states = set(re.findall(r"\b(TX|OK)\b", norm(d.get("State(s)"))))
        if states:
            d["states"] = sorted(states, key=["TX", "OK"].index)
            out.append(d)
    return out


def kv_of(d):
    v = norm(d.get("Voltages (kV)"))
    kvs = [int(x) for x in re.findall(r"\d+", v)] or [int(x) for x in re.findall(r"(\d{2,3})\s*-?\s*kV", norm(d.get("Upgrade Name")), re.I)]
    return max(kvs) if kvs else 0


ENDS = re.compile(r"^(?:Line\s*-\s*)?(.+?)\s+\d{2,3}(?:/\d{2,3})?\s*-?\s*kV", re.I)


def line_ends(name):
    """'Tecovas – Potter County 345 kV Ckt 1 New Line' -> ['Tecovas', 'Potter County']."""
    m = ENDS.match(norm(name).replace("–", "-"))
    if not m:
        return []
    parts = [re.sub(r"(?i)\s+(ckt|circuit)\s*\d+$", "", p.strip(" ,")) for p in re.split(r"\s+-\s+|\s*-\s+|\s+-\s*", m[1]) if p.strip(" ,")]
    return parts if len(parts) >= 2 else []


def classify(d):
    """kv, project type, upgrade kind, end names, miles new, miles upgraded; None for equipment and small work."""
    name, desc = norm(d.get("Upgrade Name")), norm(d.get("Project Description/ Comments"))
    text = f"{name} {desc}"
    kv = kv_of(d)
    if kv < 138 or re.search(r"TERMINAL|TRANSFORMER|\bXFR\b|REACTOR|CAPACITOR|STATCOM|SVC\b|BREAKER|RELAY|METER|RING BUS|"
                             r"WAVE ?TRAP|JUMPER|SWITCHES|CT\b|BUS TIE", name, re.I):
        return None
    m = lambda rx: re.search(rx, text, re.I)
    mi = re.search(r"(\d+(?:\.\d+)?)[- ]mile", desc, re.I)
    miles = float(mi[1]) if mi else 0.0
    new_mi, upg_mi = B.num(d.get("Number of New")), B.num(d.get("Number of Rebuild/Reconductor")) or B.num(d.get("Number of Voltage Conversion"))
    ends = line_ends(name)
    gen = re.search(r"GEN-\d{4}-\d+", norm(d.get("Project Name")) + " " + text)
    if ends and m(r"NEW LINE|\bBUILD\b|NEW .{0,20}CIRCUIT|\bCONSTRUCT"):
        return kv, "new line", "second circuit" if m(r"CKT\s*2|CIRCUIT 2|SECOND CIRCUIT|DOUBLE CIRCUIT") else "", ends, new_mi or miles, 0.0, gen
    if ends and m(r"REBUILD|RECONDUCT|CONVER|UPRATE|UPGRADE"):
        kind = next((k for k, rx in B.UPGRADE_KIND if rx.search(text)), "upgrade")
        return kv, "upgrade", kind, ends, 0.0, upg_mi or miles, gen
    if kv >= 345 and m(r"(NEW|BUILD|INSTALL|CONSTRUCT|ESTABLISH)\b.{0,40}(SUBSTATION|SWITCHING STATION|SWITCHYARD)") and \
            not m(r"EXPAN|TERMINAL"):
        site = re.sub(r"(?i)^new\s+\d{3}(/\d{3})?\s*kV\s+substation\s+at\s+", "", name)
        site = re.sub(r"(?i)\s+\d{3}(/\d{3})?\s*kV.*$", "", site).strip()
        return kv, "new substation", "", [site], 0.0, 0.0, gen
    return None


def stage(d, ptype):
    status = norm(d.get("Project Status")).lower()
    isd = d.get("Project Owner Indicated In-Service Date")
    isd = isd.date() if isinstance(isd, datetime.datetime) else isd if isinstance(isd, datetime.date) else None
    label = norm(d.get("Project Status"))
    if status in BUILT:
        if isd and isd >= B.CUTOFF:
            return "built", f"SPP: {label.lower()}, in service {isd:%Y-%m}"
        return None, ""
    if status in EARLY:
        return "proposed", f"SPP: {label.lower()}; in SPP's plan but no notice to construct yet"
    if isd and isd < B.TODAY.replace(day=1):
        return "in construction", f"estimated: planned in-service date {isd:%Y-%m} has passed and SPP has not marked it complete"
    if ptype == "upgrade":
        return "approved", f"SPP: notice to construct issued ({label}); an upgrade in its existing corridor, so there is no new route to approve"
    if isd and isd <= B.TODAY + datetime.timedelta(days=548):
        return "approved", f"estimated: SPP notice to construct issued ({label}) and due within 18 months, so its route and site should be settled"
    return "planned", f"SPP: notice to construct issued ({label}); the route or site is not final yet"


class SppPlaces:
    """HIFLD and OpenStreetMap substations in Texas and Oklahoma, by name. SPP gives no county, so a name must be
    unique (one place) among transmission-level substations, or the nearest one to the line's other end."""
    def __init__(self, researched=None):
        self.pts = {}
        self.researched = researched or {}
        for st in HOME + NEIGHBORS:
            f = os.path.join(B.HERE, "sources", f"hifld-{st.lower()}-substations.json")
            for s in json.load(open(f))["substations"] if os.path.exists(f) else []:
                if re.match(r"(UNKNOWN|TAP)\d+$", s["name"]):
                    continue
                self.pts.setdefault(sbase(s["name"]), []).append(
                    {"lat": s["lat"], "lon": s["lon"], "kv": s.get("max_kv") or 0, "state": st, "county": str(s["county"]).title(),
                     "basis": f"HIFLD substation {s['name']} ({str(s['county']).title()} County, {STATE_NAME[st]}, {s['max_kv']} kV max)",
                     "source": B.HIFLD_URL})
            f = os.path.join(B.HERE, "sources", f"osm-{st.lower()}-substations.json")
            for s in json.load(open(f))["substations"] if os.path.exists(f) else []:
                volts = [int(v) for v in re.findall(r"\d+", s.get("voltage") or "")]
                self.pts.setdefault(sbase(s["name"]), []).append(
                    {"lat": s["lat"], "lon": s["lon"], "kv": max(volts) // 1000 if volts else (115 if s.get("kind") == "transmission" else 0),
                     "state": st, "county": "", "source": "https://www.openstreetmap.org/" + s["osm"],
                     "basis": f"OpenStreetMap substation '{s['name']}'" + (f", {s['voltage']} V" if s.get("voltage") else "")
                              + (f", {s['operator']}" if s.get("operator") else "")})

        self.keys = list(self.pts)
        self.towns = {}
        f = os.path.join(B.HERE, "sources", "census-places.json")
        for st, name, lat, lon in json.load(open(f))["places"] if os.path.exists(f) else []:
            self.towns.setdefault((sbase(name), st), []).append((name, lat, lon))

    def county_at(self, pt):
        """County from the point (OpenStreetMap and town points carry none), so one substation is one record across sources."""
        if not hasattr(self, "rings"):
            self.rings = json.load(open(os.path.join(B.WEB, "counties.json")))
            self.boxes = {k: (min(x for r in v for x, _ in r), min(y for r in v for _, y in r), max(x for r in v for x, _ in r),
                              max(y for r in v for _, y in r)) for k, v in self.rings.items() if k[:2] in HOME + NEIGHBORS}
        for k, (x0, y0, x1, y1) in self.boxes.items():
            if k[:2] == pt.get("state") and x0 <= pt["lon"] <= x1 and y0 <= pt["lat"] <= y1 and B.in_county(self, k, pt):
                return k.split("|")[1]
        return ""

    def town(self, name, states):
        """Many SPP substations are named for their town ('Kingfisher', 'Talihina'). If the name is one town in the
        line's states, place the substation at that town: good enough to see the area, not to find the parcel."""
        b = sbase(re.sub(r"(?i)\b(tap|sw|switch|switchyard|east|west|north|south|ne|nw|se|sw)\b", " ", name))
        hits = [(st, t) for st in states for t in self.towns.get((b, st), [])]
        if len(hits) != 1:
            return None
        st, (town, lat, lon) = hits[0]
        return {"name": name, "county": "", "state": st, "lat": lat, "lon": lon, "confidence": "town",
                "basis": f"Center of {town}, {STATE_NAME[st]}: the substation is named for the town but is not on public maps by this name",
                "source": "https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html"}

    def find(self, name, kv, states, near=None, strict=True):
        """strict: only substations in the states SPP lists for the row. Otherwise any state, but only within about
        200 miles of the line's other end (a line from Oklahoma into the Panhandle ends in Texas)."""
        b = sbase(name)
        r = self.researched.get(b)
        if r:
            return {"name": name, "county": r.get("county", ""), "state": r.get("state", states[0]), "lat": r["lat"], "lon": r["lon"],
                    "confidence": r["confidence"], "basis": r["basis"], "source": r["source"]}
        ok = (lambda c: c["state"] in states) if strict else \
            (lambda c: near is not None and miles(c, near) <= 200)
        keys = [b, b + " COUNTY", re.sub(r" COUNTY$", "", b)]   # 'Potter' / 'Potter County'
        cands = next(([c for c in self.pts.get(k, []) if ok(c)] for k in keys if any(ok(c) for c in self.pts.get(k, []))), [])
        spelled = ""
        if not cands and len(b) >= 6:
            # One-letter spelling differences between SPP and the maps ('Matthewson' / 'MATHEWSON', 'Talequah' / 'TAHLEQUAH'),
            # only for a transmission-level station that passes the same state rule.
            close = [k for k in difflib.get_close_matches(b, self.keys, n=3, cutoff=0.88) if k[0] == b[0]]
            close = [k for k in close if any(ok(c) and c["kv"] >= 115 for c in self.pts[k])]
            if len(close) == 1:
                cands, spelled = [c for c in self.pts[close[0]] if ok(c)], close[0]
        if not cands:
            return None
        hi = [c for c in cands if c["kv"] >= min(kv, 115)] or cands
        groups = []
        for c in hi:   # one station's HIFLD and OSM points differ a little: group points within about 5 miles
            g = next((g for g in groups if abs(g[0]["lat"] - c["lat"]) < 0.08 and abs(g[0]["lon"] - c["lon"]) < 0.08), None)
            g.append(c) if g else groups.append([c])
        conf, why = ("approx", f"; matched by spelling (SPP writes '{name}')") if spelled else ("exact", "")
        if len(groups) > 1:
            top = max(max(c["kv"] for c in g) for g in groups)
            biggest = [g for g in groups if max(c["kv"] for c in g) == top]
            if near:
                groups.sort(key=lambda g: miles(g[0], near))
                why += f"; one of {len(groups)} places with this name, the nearest to the line's other end"
            elif len(biggest) == 1 and top >= 230:
                groups = biggest
                why += f"; one of {len(groups)} places with this name, the only one at {top} kV"
            else:
                return None
            conf = "approx"
        g = groups[0]
        c = next((c for c in g if c["county"]), g[0])   # HIFLD carries the county
        return {"name": name, "county": c["county"], "state": c["state"], "lat": g[0]["lat"], "lon": g[0]["lon"], "confidence": conf,
                "basis": g[0]["basis"] + why, "source": g[0]["source"]}


def miles(a, b):
    return 69.0 * math.hypot(a["lat"] - b["lat"], (a["lon"] - b["lon"]) * math.cos(math.radians(a["lat"])))


def owner(d):
    o = norm(d.get("Project Owner"))
    return OWNERS.get(o, o)


def spp_lines(researched=None):
    """Line records in the same shape as the ERCOT ones, market 'SPP'."""
    places = SppPlaces(researched)
    groups = {}
    for d in read_step():
        c = classify(d)
        if not c:
            continue
        kv, ptype, detail, ends, new_mi, upg_mi, gen = c
        life, basis = stage(d, ptype)
        if not life:
            continue
        isd = d.get("Project Owner Indicated In-Service Date")
        isd = B.ym(isd)
        if isd and isd > B.HORIZON:
            continue
        ckt = re.search(r"CKT\s*(\d)", norm(d.get("Upgrade Name")), re.I)
        key = (frozenset(sbase(e) for e in ends), kv, ptype, ckt[1] if ckt else "1")
        g = groups.setdefault(key, {"rows": [], "kv": kv, "ptype": ptype, "detail": detail, "ends": ends, "gen": gen})
        g["rows"].append((d, life, basis, new_mi, upg_mi, isd))
    out = []
    for key, g in groups.items():
        rows = g["rows"]
        # One line SPP splits between two owners (each builds its part) is one line; it is as far along as its slower part.
        d, life, basis, _, _, isd = max(rows, key=lambda t: B.STAGES.index(t[1]))
        states = sorted({s for r in rows for s in r[0]["states"]}, key=["TX", "OK"].index)
        ids = sorted({str(r[0].get("Upgrade ID")) for r in rows})
        ends = []
        for n in g["ends"]:
            ends.append(places.find(n, g["kv"], states) or {"name": n, "county": "", "state": "", "confidence": "unknown",
                                                              "basis": "Not on public maps by this name (SPP gives no county)"})
        for i, e in enumerate(ends):   # ambiguous names: take the one nearest the other end; then across the state line
            near = next((o for o in ends if o is not e and o.get("lat") is not None), None)
            if e.get("lat") is None and near:
                ends[i] = places.find(e["name"], g["kv"], states, near) or places.find(e["name"], g["kv"], states, near, strict=False) or e
        for i, e in enumerate(ends):
            if e.get("lat") is None:
                ends[i] = places.town(e["name"], [s for s in states if s in HOME]) or e
        for e in ends:
            e["name"] = re.sub(r"\s+", " ", e["name"]).strip()
            if e.get("lat") is not None and not e.get("county"):
                e["county"] = places.county_at(e)
        placed = [e for e in ends if e.get("lat") is not None]
        if placed and not any(e["state"] in HOME for e in placed):
            continue   # SPP lists the state that pays; the line itself is in Arkansas, Kansas or Missouri
        if not placed and not set(r[0]["State(s)"] for r in rows) <= {"TX", "OK"}:
            continue   # can't tell which state it is in
        placed_states = sorted({e["state"] for e in placed if e["state"] in HOME} or set(states), key=list(HOME).index)
        name = norm(d.get("Upgrade Name")).replace("–", "-")
        name = re.sub(r"\s+", " ", re.sub(r"\s*\((SPS|OGE|AEP|WFEC|GRDA)\)\s*$", "", name))
        purpose = "generator hookup" if g["gen"] else "shared grid"
        rec = {"id": "spp-" + ids[0], "ercot_project": "", "spp_upgrades": ids, "spp_project": str(d.get("Project ID") or ""),
               "spp_ntc": str(d.get("NTC ID") or ""), "name": name,
               "description": norm(d.get("Project Description/ Comments"))[:400], "kv": g["kv"], "project_type": g["ptype"],
               "upgrade_kind": g["detail"], "lifecycle": life, "lifecycle_basis": basis, "tpit_status": "",
               "spp_status": norm(d.get("Project Status")), "utility": " / ".join(dict.fromkeys(owner(r[0]) for r in rows)),
               "from": ends[0]["name"], "to": ends[-1]["name"] if len(ends) > 1 else "",
               "county_from": ends[0].get("county", ""), "county_to": ends[-1].get("county", "") if len(ends) > 1 else "",
               "miles_new": round(max(r[3] for r in rows), 1), "miles_upgraded": round(max(r[4] for r in rows), 1), "transformer_mva": 0,
               "in_service": max((r[5] for r in rows if r[5]), default=""), "in_service_kind": "actual" if life == "built" else "projected",
               "construction_start": "", "capacity_mw": None, "purpose": purpose,
               "program": f"SPP {norm(d.get('Source Study'))}".strip(), "rpg": "", "tier": "", "ercot_board": "", "docket": "",
               "route_status": "existing corridor" if g["ptype"] == "upgrade" else "end substations only",
               "card_id": "", "card_ids": [], "endpoints": ends, "market": "SPP", "state": ", ".join(placed_states),
               "source": f"SPP STEP ({STEP_URL}), {STEP_LABEL}", "checked": "SPP " + STEP_LABEL.split(" (")[0]}
        if not rec["in_service"]:
            rec["in_service_kind"] = ""
        rec["tappable"], rec["tap_note"] = B.tap(g["kv"])
        rec["recommended_next_step"], rec["recommendation_reason"] = B.recommend(rec)
        rec["recommendation_reason"] = rec["recommendation_reason"].replace("ERCOT endorsement", "an SPP notice to construct")
        rec["priority_score"] = B.priority(rec)
        out.append(rec)
    return out


if __name__ == "__main__":
    ls = spp_lines()
    print(len(ls), "SPP lines")
    print(Counter(x["state"] for x in ls), Counter(x["lifecycle"] for x in ls), Counter(x["project_type"] for x in ls), Counter(x["kv"] for x in ls))
    print(Counter(e["confidence"] for x in ls for e in x["endpoints"]))
    for x in sorted(ls, key=lambda x: -x["priority_score"])[:25]:
        print(x["id"], x["state"], x["kv"], x["lifecycle"], x["in_service"], "|", x["name"], "|", [(e["name"], e["confidence"], e.get("county")) for e in x["endpoints"]])
    print("unplaced:", [(x["name"], [e["name"] for e in x["endpoints"] if e.get("lat") is None]) for x in ls if any(e.get("lat") is None for e in x["endpoints"])][:40])
