"""MISO lines for Line Watch: the MISO part of Texas (Entergy Texas) and MISO's LRTP Tranche 1 backbone.

Sources, both kept by hand (MISO's own site refuses automated downloads):
  sources/miso-etr-2026.json   Entergy Texas, from its monthly construction report to the Texas PUC and its project pages
  sources/miso-lrtp-2026.json  MISO's 18 Tranche 1 345 kV projects, from MISO's public dashboard (June 30, 2026)
Stations are placed from HIFLD and OpenStreetMap by name in the state given, checked against the county when one is
given; new stations go next to the station the source names ("near") or to the county center.
"""
import datetime
import json
import os
import re
from collections import Counter

import build_catalog as B
from build_spp import SppPlaces, STATE_NAME, miles

ETR_FILE = os.path.join(B.HERE, "sources", "miso-etr-2026.json")
LRTP_FILE = os.path.join(B.HERE, "sources", "miso-lrtp-2026.json")
MARKET_MISO = "MISO"
MISO_STATES = ("TX", "ND", "SD", "MN", "WI", "IA", "MO", "IL", "IN", "MI")


class MisoPlaces(SppPlaces):
    def __init__(self):
        super().__init__(states=MISO_STATES)
        self.rings = json.load(open(os.path.join(B.WEB, "counties.json")))
        self.ckeys = {k.upper(): k for k in self.rings}
        self.boxes = {k: (min(x for r in v for x, _ in r), min(y for r in v for _, y in r), max(x for r in v for x, _ in r),
                          max(y for r in v for _, y in r)) for k, v in self.rings.items() if k[:2] in MISO_STATES}

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


def miso_lines():
    places = MisoPlaces()
    return etr_lines(places) + lrtp_lines(places)


if __name__ == "__main__":
    ls = miso_lines()
    print(len(ls), "MISO lines", Counter(x["lifecycle"] for x in ls), Counter(x["state"] for x in ls))
    print(Counter(e["confidence"] for x in ls for e in x["endpoints"]))
    for x in ls:
        print(x["id"], x["kv"], x["lifecycle"], x["in_service"], "|", x["name"], "|",
              [(e["name"], e["confidence"], e.get("county"), e.get("state")) for e in x["endpoints"]])
