"""MISO lines for Line Watch: the MISO part of Texas (Entergy Texas) and MISO's LRTP Tranche 1 backbone.

Sources, both kept by hand (MISO's own site refuses automated downloads):
  sources/miso-etr-2026.json   Entergy Texas, from its monthly construction report to the Texas PUC and its project pages
  sources/miso-lrtp-2026.json  MISO's 18 Tranche 1 345 kV projects, from MISO's public dashboard (June 30, 2026)
  sources/miso-mtep25-appendix-a.xlsx  MISO's MTEP25 Appendix A (new local projects the board approved in Dec 2025),
                               downloaded by Jaiden from MISO's site: lines 138 kV+ and new 345 kV+ substations
Stations are placed from HIFLD and OpenStreetMap by name in the state given, checked against the county when one is
given; new stations go next to the station the source names ("near") or to the county center.
"""
import datetime
import json
import os
import re
from collections import Counter

import build_catalog as B
from build_spp import SppPlaces, STATE_NAME, miles, sbase

ETR_FILE = os.path.join(B.HERE, "sources", "miso-etr-2026.json")
LRTP_FILE = os.path.join(B.HERE, "sources", "miso-lrtp-2026.json")
MARKET_MISO = "MISO"
MISO_STATES = ("TX", "ND", "SD", "MN", "WI", "IA", "MO", "IL", "IN", "MI", "LA", "MS", "AR", "KY")
MTEP_FILE = os.path.join(B.HERE, "sources", "miso-mtep25-appendix-a.xlsx")
MTEP_URL = "https://www.misoenergy.org/planning/transmission-planning/mtep/"
NOT_A_PLACE = re.compile(r"BLANKET|THROUGHOUT|VARIOUS|^\d+ LINES$", re.I)
LOOKUPS = os.path.join(B.HERE, "sources", "osm-miso-lookups.json")
RESEARCH_FILE = os.path.join(B.HERE, "sources", "miso-research-2026.json")
CORRECTIONS_FILE = os.path.join(B.HERE, "sources", "miso-corrections-2026.json")
STAGES = ("built", "in construction", "approved", "planned", "proposed")
# Researched items left out on review: a DC line upgrade (no AC tap possible) and a relocation done only for a Tranche 1 line.
DROP = {"square-butte-arrowhead-hvdc-900mw", "wabasha-relocation-161"}


class MisoPlaces(SppPlaces):
    """Name-based substation finder for the MISO and PJM states (HIFLD + OpenStreetMap + per-name lookups)."""
    def __init__(self, states=MISO_STATES):
        super().__init__(states=states)
        # Substations looked up one name at a time on OpenStreetMap (data/fetch_osm_names.py), for states whose
        # whole-state OpenStreetMap download times out.
        for s in (json.load(open(LOOKUPS))["substations"] if os.path.exists(LOOKUPS) else []):
            volts = [int(v) for v in re.findall(r"\d+", s.get("voltage") or "")]
            self.pts.setdefault(sbase(s["name"]), []).append(
                {"lat": s["lat"], "lon": s["lon"], "kv": max(volts) // 1000 if volts else 0, "state": s["state"], "county": "",
                 "source": "https://www.openstreetmap.org/" + s["osm"],
                 "basis": f"OpenStreetMap substation '{s['name']}'" + (f", {s['voltage']} V" if s.get("voltage") else "") + (f", {s['operator']}" if s.get("operator") else "")})
        self.rings = json.load(open(os.path.join(B.WEB, "counties.json")))
        self.ckeys = {k.upper(): k for k in self.rings}
        self.boxes = {k: (min(x for r in v for x, _ in r), min(y for r in v for _, y in r), max(x for r in v for x, _ in r),
                          max(y for r in v for _, y in r)) for k, v in self.rings.items() if k[:2] in self.states}

    def county_key(self, st, county):
        return self.ckeys.get(f"{st}|{county}".upper())

    def in_counties(self, pt, st, counties):
        """Within about 5 miles of one of the counties the source gives (a station can sit on the county line)."""
        for c in counties:
            k = self.county_key(st, c)
            if not k:
                continue
            x0, y0, x1, y1 = self.boxes[k]
            if x0 - 0.07 <= pt["lon"] <= x1 + 0.07 and y0 - 0.07 <= pt["lat"] <= y1 + 0.07:
                return True
        return False

    def county_center(self, name, st, county, why, source):
        k = self.county_key(st, county)
        if not k:
            return {"name": name, "county": county, "state": st, "confidence": "unknown", "basis": why}
        x, y = B.centroid(max(self.rings[k], key=len))
        return {"name": name, "county": k.split("|")[1], "state": st, "lat": round(y, 4), "lon": round(x, 4), "confidence": "county",
                "basis": f"Center of {k.split('|')[1]} County, {STATE_NAME.get(st, st)}: {why}", "source": source}

    def place(self, s, kv, st, source, near_pt=None):
        """One station: by name on the maps (in the county given, if any), else next to the station it is built
        beside, else its county's center, else unplaced."""
        counties = [c for c in str(s.get("county") or "").split("|") if c]
        hit = None
        if not s.get("new"):
            hit = self.find(s.get("map_name") or s["name"], kv, [st], near=near_pt)
            if hit and counties and not self.in_counties(hit, st, counties):
                hit = None   # same name, wrong place (there is a Castle substation in Dallas too)
        if hit:
            hit["name"] = s["name"]
        elif s.get("near"):
            n = self.find(s["near"], kv, [st])
            if n:
                hit = {**n, "name": s["name"], "confidence": "approx",
                       "basis": f"New substation built beside {s['near']} ({s.get('note') or 'per the source'}); placed at {s['near']}: {n['basis']}"}
        if not hit and not counties and not s.get("new"):
            hit = self.town(s["name"], [st])   # named for its town ('Ottumwa', 'Lake Charles'), where Census places cover the state
        if not hit and counties:
            why = (f"new substation ({s['note']}), not on public maps yet" if s.get("note") else
                   "new substation, not on public maps yet" if s.get("new") else "not on public maps by this name")
            hit = self.county_center(s["name"], st, counties[0], why, source)
        if not hit:
            hit = {"name": s["name"], "county": "", "state": st, "confidence": "unknown",
                   "basis": ("New substation; its location is not published" if s.get("new") else
                             "Not on public maps by this name, and the source gives no county")}
        hit.setdefault("state", st)
        if hit.get("lat") is not None and not hit.get("county"):
            hit["county"] = self.county_at(hit)
        return hit


def finish(rec, kv, note_from):
    rec["tappable"], rec["tap_note"] = B.tap(kv)
    rec["recommended_next_step"], rec["recommendation_reason"] = B.recommend(rec)
    rec["recommendation_reason"] = rec["recommendation_reason"].replace("ERCOT endorsement", note_from)
    rec["priority_score"] = B.priority(rec)
    return rec


def etr_lines(places=None):
    """Entergy Texas (MISO South, Southeast Texas)."""
    src, places = json.load(open(ETR_FILE)), places or MisoPlaces()
    out = []
    today = B.TODAY.strftime("%Y-%m")
    for p in src["projects"]:
        isd = p["in_service"]
        if isd and (isd > B.HORIZON or isd < B.CUTOFF.strftime("%Y-%m")):
            continue
        ends = [places.place(s, p["kv"], "TX", src["report_url"]) for s in p["ends"]]
        st = p["status"]
        if st == "built":
            life, basis = "built", p["basis"]
        elif st == "construction" and isd and isd <= (B.TODAY - datetime.timedelta(days=183)).strftime("%Y-%m"):
            life, basis = "built", f"estimated: Entergy's planned finish ({isd}) is more than 6 months past. {p['basis']}"
        elif st == "construction" and (p.get("start", "9999") <= today):
            life, basis = "in construction", ("estimated: " if isd and isd < today else "") + p["basis"]
        elif st == "construction":
            life, basis = "approved", p["basis"]
        else:
            life, basis = {"approved": "approved", "proposed": "proposed"}[st], p["basis"]
        new = [s["name"] for s in p["ends"] if s.get("new")]
        rec = {"id": "etr-" + p["key"], "ercot_project": "", "name": p["name"],
               "description": ("New substation" + ("s " if len(new) > 1 else " ") + ", ".join(new) + ". " if new else "") + p["basis"],
               "kv": p["kv"], "project_type": p["project_type"], "upgrade_kind": "", "lifecycle": life, "lifecycle_basis": basis,
               "tpit_status": "", "utility": "Entergy Texas", "from": ends[0]["name"], "to": ends[-1]["name"] if len(ends) > 1 else "",
               "county_from": ends[0].get("county", ""), "county_to": ends[-1].get("county", "") if len(ends) > 1 else "",
               "miles_new": p["miles"], "miles_upgraded": 0, "transformer_mva": 0, "in_service": isd,
               "in_service_kind": ("actual" if st == "built" else "projected") if isd else "", "construction_start": p.get("start", ""),
               "capacity_mw": None, "purpose": "shared grid", "program": "Entergy Texas (MISO South)", "rpg": "", "tier": "", "ercot_board": "",
               "docket": p["docket"], "route_status": "route final" if life in ("approved", "in construction", "built") else "filed routes" if st == "proposed" and p["page"] else "end substations only",
               "card_id": "", "card_ids": [], "endpoints": ends, "market": MARKET_MISO, "state": "TX",
               "source": "; ".join(x for x in (src["report_url"], p["page"]) if x), "checked": "Entergy Texas PUC report (June 2025) and project pages"}
        out.append(finish(rec, p["kv"], "the PUC route decision"))
    return out


def lrtp_lines(places=None):
    """MISO's LRTP Tranche 1: 345 kV lines MISO approved in July 2022, due 2028 to 2031."""
    src, places = json.load(open(LRTP_FILE)), places or MisoPlaces()
    out = []
    for p in src["projects"]:
        if p["in_service"] > B.HORIZON:
            continue
        ends = []
        for s in p["stations"]:
            near = next((e for e in reversed(ends) if e.get("lat") is not None), None)
            ends.append(places.place(s, 345, s["state"], src["dashboard_url"], near))
        if p["construction"]:
            life, basis = "in construction", f"MISO dashboard (June 30, 2026): construction {p['construction']}"
        else:
            life, basis = "planned", (f"MISO-approved (LRTP Tranche 1, July 2022); state approval {src['status_key'][p['regulatory']]} "
                                      "per MISO's dashboard (June 30, 2026); route not confirmed here")
        new = sorted({s["name"] for s in p["stations"] if s.get("new")})
        states = [s for s in p["states"]]
        rec = {"id": f"miso-lrtp-{p['id']}", "ercot_project": "", "name": p["name"] + " 345 kV",
               "description": f"MISO LRTP Tranche 1 project {p['id']}, owner {p['owner']}. " + (f"New substation{'s' if len(new) > 1 else ''}: {', '.join(new)}. " if new else ""),
               "kv": 345, "project_type": "new line", "upgrade_kind": "", "lifecycle": life, "lifecycle_basis": basis, "tpit_status": "",
               "utility": p["owner"], "from": ends[0]["name"], "to": ends[-1]["name"], "county_from": ends[0].get("county", ""),
               "county_to": ends[-1].get("county", ""), "miles_new": p["miles"], "miles_upgraded": 0, "transformer_mva": 0,
               "in_service": p["in_service"], "in_service_kind": "projected", "construction_start": "", "capacity_mw": None,
               "purpose": "shared grid", "program": "MISO LRTP Tranche 1", "rpg": "", "tier": "", "ercot_board": "", "docket": "",
               "route_status": "end substations only", "card_id": "", "card_ids": [], "endpoints": ends, "market": MARKET_MISO,
               "state": ", ".join(states), "source": src["dashboard_url"], "checked": "MISO Tranche 1 dashboard (June 30, 2026)"}
        out.append(finish(rec, 345, "MISO approval"))
    return out


def mtep_rows():
    """MTEP25 facilities Line Watch keeps: new and upgraded lines 138 kV+ and new 345 kV+ substations, in the window."""
    import openpyxl
    if not os.path.exists(MTEP_FILE):
        return []
    rows = list(openpyxl.load_workbook(MTEP_FILE, read_only=True, data_only=True)["MTEP25 Facilities"].iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    out = []
    for r in rows[2:]:
        r = {k: (v.strip() if isinstance(v, str) else v) for k, v in zip(head, r)}
        if not r.get("Facility ID"):
            continue
        kv = int(B.num(r["Max kV"]))
        isd = r["Expected ISD"].strftime("%Y-%m") if isinstance(r["Expected ISD"], datetime.datetime) else str(r["Expected ISD"] or "")[:7]
        desc = re.sub(r"\s+", " ", str(r["Description"] or "")).strip()
        ftype = r["Facility Type"]
        if kv < 138 or not isd or isd > B.HORIZON or isd < B.CUTOFF.strftime("%Y-%m"):
            continue
        if NOT_A_PLACE.search(str(r["From Sub"] or "")):
            continue   # a budget line ('Blanket for SCADA switches', 'Various Lines'), not one project at one place
        if ftype == "Line New":
            ptype = "new line"
        elif ftype == "Line Upgrade":
            ptype = "upgrade"
        elif ftype == "Substation" and kv >= 345 and B.NEW_STATION.search(desc):
            ptype = "new substation"
        else:
            continue
        out.append({**r, "kv": kv, "isd": isd, "desc": desc, "ptype": ptype})
    return out


def mtep_lines(places=None, skip_pairs=()):
    """MISO's MTEP25 local projects (Appendix A, approved Dec 2025). Plan status: M4 in service = built; M3 under
    construction; otherwise approved for an upgrade on an existing line or a project due within 18 months, else planned."""
    places = places or MisoPlaces()
    out, today = [], B.TODAY.strftime("%Y-%m")
    soon = (B.TODAY + datetime.timedelta(days=548)).strftime("%Y-%m")
    for r in mtep_rows():
        st = str(r["State"] or "").strip()[:2]
        names = [n for n in (str(r["From Sub"] or "").strip(), str(r["To Sub"] or "").strip()) if n]
        if not names or st not in MISO_STATES:
            continue
        if any(frozenset(B.base(n) for n in names) <= ends for ends in skip_pairs):
            continue   # already in the list from Entergy's own report
        ends = []
        for n in names:
            near = next((e for e in ends if e.get("lat") is not None), None)
            ends.append(places.place({"name": n}, r["kv"], st, MTEP_URL, near))
        if ends[0].get("lat") is None and len(ends) > 1 and ends[1].get("lat") is not None:
            ends[0] = places.place({"name": names[0]}, r["kv"], st, MTEP_URL, ends[1])
        status = str(r["Plan Status"] or "")
        detail = next((k for k, rx in B.UPGRADE_KIND if rx.search(r["desc"])), "upgrade") if r["ptype"] == "upgrade" else ""
        if status.startswith("M4"):
            life, basis = "built", "MISO: project in service (MTEP25 status)"
        elif status.startswith("M3"):
            life, basis = "in construction", "MISO: under construction (MTEP25 status)"
        elif r["isd"] < today:
            life, basis = "in construction", f"estimated: planned in-service date {r['isd']} has passed and MISO's list does not show it in service"
        elif r["ptype"] == "upgrade":
            life, basis = "approved", "MISO-approved (MTEP25 Appendix A); work on an existing line"
        elif r["isd"] <= soon:
            life, basis = "approved", "estimated: MISO-approved (MTEP25 Appendix A) and due within 18 months, so its route and site should be settled"
        else:
            life, basis = "planned", "MISO-approved (MTEP25 Appendix A, Dec 2025); route or site not confirmed here"
        gen = str(r.get("Submitting Comp.") or "")
        purpose = "generator hookup" if B.GENERATOR.search(r["desc"]) else "large-load hookup" if B.BIG_LOAD.search(r["desc"]) else "shared grid"
        rec = {"id": f"mtep25-{r['Facility ID']}", "ercot_project": "", "name": (" - ".join(names) + f" {r['kv']} kV" + (f" ckt {r['Ckt']}" if r.get("Ckt") else "")) if r["ptype"] != "new substation" else f"{names[0]} {r['kv']} kV substation",
               "description": r["desc"][:400], "kv": r["kv"], "project_type": r["ptype"], "upgrade_kind": detail, "lifecycle": life,
               "lifecycle_basis": basis, "tpit_status": "", "utility": gen.title(), "from": ends[0]["name"], "to": ends[-1]["name"] if len(ends) > 1 else "",
               "county_from": ends[0].get("county", ""), "county_to": ends[-1].get("county", "") if len(ends) > 1 else "",
               "miles_new": round(B.num(r["Miles New"]), 1), "miles_upgraded": round(B.num(r["Miles Upgrade"]), 1), "transformer_mva": 0,
               "in_service": r["isd"], "in_service_kind": "actual" if life == "built" else "projected", "construction_start": "", "capacity_mw": None,
               "purpose": purpose, "program": f"MISO MTEP25 project {r['PrjID']}", "rpg": "", "tier": "", "ercot_board": "", "docket": "",
               "route_status": "existing corridor" if r["ptype"] == "upgrade" else "end substations only", "card_id": "", "card_ids": [],
               "endpoints": ends, "market": MARKET_MISO, "state": st, "source": MTEP_URL, "checked": "MISO MTEP25 Appendix A (data as of Oct 2025)"}
        out.append(finish(rec, r["kv"], "MISO approval"))
    return out


def research_lines(places=None, have=(), have_mtep=(), path=None, prefix="misor-", market=MARKET_MISO):
    """MISO projects found in utility pages, state commission dockets and transmission owners' plans
    (sources/miso-research-2026.json): projects approved before MTEP25 that are still being built, and ones not in
    MISO's list yet. Each carries its own stage and source; projects already in the list (same end substations) are skipped."""
    path = path or RESEARCH_FILE
    if not os.path.exists(path):
        return []
    src, places = json.load(open(path)), places or MisoPlaces()
    out, seen = [], set(have)
    for p in src["projects"]:
        isd = p.get("in_service") or ""
        if p["kv"] < 138 or (isd and (isd > B.HORIZON or isd < B.CUTOFF.strftime("%Y-%m"))) or p["stage"] not in STAGES:
            continue
        if p["stage"] == "built" and not isd:
            continue   # built, but no date to show it is within the last 3 years
        key = frozenset((B.base(e["name"]), e["state"]) for e in p["ends"])
        if key in seen or any(p.get(k) and str(p[k]) in have_mtep for k in ("mtep_id", "pjm_id")) or p["key"] in DROP:
            continue
        seen.add(key)
        ends = []
        for e in p["ends"]:
            if e.get("lat") is not None:
                ends.append({"name": e["name"], "county": e.get("county", ""), "state": e["state"], "lat": e["lat"], "lon": e["lon"],
                             "confidence": "approx", "basis": e.get("location_basis") or "located from the project's own description", "source": p["sources"][0]})
            else:
                near = next((x for x in ends if x.get("lat") is not None), None)
                ends.append(places.place({"name": e["name"], "county": e.get("county", ""), "new": e.get("new", False)}, p["kv"], e["state"], p["sources"][0], near))
        new = [e["name"] for e in p["ends"] if e.get("new")]
        states = sorted({e["state"] for e in p["ends"]} | {p["state"]})
        rec = {"id": prefix + p["key"], "ercot_project": "", "name": p["name"], "description": (f"New substation{'s' if len(new) > 1 else ''}: {', '.join(new)}. " if new else "") + p["stage_basis"],
               "kv": p["kv"], "project_type": p["project_type"], "upgrade_kind": "", "lifecycle": p["stage"], "lifecycle_basis": p["stage_basis"],
               "tpit_status": "", "utility": p["utility"], "from": ends[0]["name"], "to": ends[-1]["name"] if len(ends) > 1 else "",
               "county_from": ends[0].get("county", ""), "county_to": ends[-1].get("county", "") if len(ends) > 1 else "",
               "miles_new": p.get("miles_new") or 0, "miles_upgraded": p.get("miles_upgraded") or 0, "transformer_mva": 0, "in_service": isd,
               "in_service_kind": ("actual" if p["stage"] == "built" else "projected") if isd else "", "construction_start": "", "capacity_mw": None,
               "purpose": "large-load hookup" if B.BIG_LOAD.search(p["name"] + " " + p["stage_basis"]) else "shared grid",
               "program": f"{market} (" + (f"MTEP project {p['mtep_id']}" if p.get("mtep_id") else f"PJM upgrade {p['pjm_id']}" if p.get("pjm_id") else "utility and state filings") + ")",
               "rpg": "", "tier": "", "ercot_board": "", "docket": p.get("docket", ""),
               "route_status": "existing corridor" if p["project_type"] == "upgrade" else "route final" if p["stage"] in ("approved", "in construction", "built") else "end substations only",
               "card_id": "", "card_ids": [], "endpoints": ends, "market": market, "state": ", ".join(states),
               "source": "; ".join(p["sources"][:3]), "checked": f"Line Watch research, {src.get('checked', '')}"}
        out.append(finish(rec, p["kv"], "the regulator's decision"))
    return out


def miso_lines():
    places = MisoPlaces()
    etr = etr_lines(places)
    pairs = {frozenset(B.base(e["name"]) for e in x["endpoints"]) for x in etr}
    known = etr + lrtp_lines(places) + mtep_lines(places, pairs)
    have = {frozenset((B.base(e["name"]), e.get("state", "")) for e in x["endpoints"]) for x in known}
    have_mtep = {re.sub(r"\D", "", x["program"]) for x in known if x["id"].startswith("mtep25-")}
    drop = json.load(open(CORRECTIONS_FILE))["drop"] if os.path.exists(CORRECTIONS_FILE) else {}
    return [x for x in known + research_lines(places, have, have_mtep) if x["id"] not in drop]   # withdrawn or cancelled since the list was made


if __name__ == "__main__":
    ls = miso_lines()
    print(len(ls), "MISO lines", Counter(x["lifecycle"] for x in ls), Counter(x["state"] for x in ls))
    print(Counter(e["confidence"] for x in ls for e in x["endpoints"]))
    for x in ls:
        print(x["id"], x["kv"], x["lifecycle"], x["in_service"], "|", x["name"], "|",
              [(e["name"], e["confidence"], e.get("county"), e.get("state")) for e in x["endpoints"]])
