"""El Paso Electric lines for Line Watch: far West Texas, on the western (WECC) grid, outside ERCOT and SPP.

Source: EPE's 2026 System Expansion Plan (2027-2036), curated into sources/epe-plan-2026.json: 345 kV lines and new
345 kV substations with at least one end in Texas, due within the 5-year window. The plan is a PDF, so the list is
kept by hand; lw.py does not rebuild it. Check it when EPE posts its next plan (each summer).
"""
import datetime
import json
import os

import build_catalog as B
from build_spp import SppPlaces

EPE_FILE = os.path.join(B.HERE, "sources", "epe-plan-2026.json")
MARKET_EPE = "WECC"
EL_PASO = (31.76, -106.44)


def epe_lines():
    src = json.load(open(EPE_FILE))
    places, county = SppPlaces(), B.Places([])
    out = []
    for p in src["projects"]:
        if p["in_service"] and p["in_service"] > B.HORIZON:
            continue
        ends = []
        for n in p["ends"]:
            hit = places.find(n, p["kv"], ["TX"]) or places.find(n, p["kv"], ["NM"])
            town = None if hit else places.town(n, ["TX", "NM"])
            if town and abs(town["lat"] - EL_PASO[0]) < 1 and abs(town["lon"] - EL_PASO[1]) < 1:   # named for a town near El Paso
                hit = town
                hit["county"] = places.county_at(hit)
            if not hit:
                hit = county.county_point(n, p["county"])
                hit.update(state="TX", basis=f"Center of {p['county']} County: EPE's plan puts it in the El Paso area, but this substation is not on public maps by this name",
                           source=src["source"])
            ends.append(hit)
        isd = datetime.date(int(p["in_service"][:4]), int(p["in_service"][5:7]), 1)
        filed = bool(p["docket"])
        if isd <= B.TODAY + datetime.timedelta(days=548):
            life, basis = "approved", "estimated: in EPE's plan and due within 18 months, so its route and site should be settled"
        else:
            life, basis = "planned", ("EPE's plan; route case filed at the PUC (Docket %s), route not final yet" % p["docket"] if filed
                                      else "EPE's plan; the route or site is not final yet")
        rec = {"id": "epe-" + "-".join(e.lower().replace(" ", "") for e in p["ends"]) + ("-sub" if p["project_type"] == "new substation" else ""),
               "ercot_project": "", "name": p["name"], "description": "", "kv": p["kv"], "project_type": p["project_type"], "upgrade_kind": "",
               "lifecycle": life, "lifecycle_basis": basis, "tpit_status": "", "utility": "El Paso Electric",
               "from": ends[0]["name"], "to": ends[-1]["name"] if len(ends) > 1 else "", "county_from": ends[0].get("county", ""),
               "county_to": ends[-1].get("county", "") if len(ends) > 1 else "", "miles_new": 0, "miles_upgraded": 0, "transformer_mva": 0,
               "in_service": p["in_service"], "in_service_kind": "projected", "construction_start": "", "capacity_mw": None, "purpose": "shared grid",
               "program": "EPE System Expansion Plan", "rpg": "", "tier": "", "ercot_board": "", "docket": p["docket"],
               "route_status": "filed routes" if filed else "end substations only", "card_id": "", "card_ids": [], "endpoints": ends,
               "market": MARKET_EPE, "state": "TX" if all(e.get("state", "TX") == "TX" for e in ends) else "TX, NM", "source": "; ".join(x for x in (src["source"], p["page"]) if x),
               "checked": "EPE System Expansion Plan 2027-2036"}
        rec["tappable"], rec["tap_note"] = B.tap(p["kv"])
        rec["recommended_next_step"], rec["recommendation_reason"] = B.recommend(rec)
        rec["recommendation_reason"] = rec["recommendation_reason"].replace("ERCOT endorsement", "the PUC route decision")
        rec["priority_score"] = B.priority(rec)
        out.append(rec)
    return out


if __name__ == "__main__":
    for x in epe_lines():
        print(x["id"], x["lifecycle"], x["in_service"], x["name"], [(e["name"], e["confidence"], e.get("state"), e.get("county")) for e in x["endpoints"]])
