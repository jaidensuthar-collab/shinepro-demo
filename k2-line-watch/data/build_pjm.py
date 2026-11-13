"""PJM lines for Line Watch: every PJM upgrade (baseline, supplemental and generator-interconnection network
upgrades) that is a new or upgraded line at 138 kV and up, or a new substation / switching station at 230 kV and up,
in the window. Source: PJM's Project Construction data (sources/pjm-upgrades.json, refreshed by fetch_pjm.py).

PJM status -> Line Watch stage:
  IS (in service) = built; UC = in construction;
  EP (engineering and procurement): an upgrade of an existing line, or anything due within 18 months = approved;
      otherwise planned (approved by PJM or the utility, route or site not final);
  PL (planning): baseline = planned, supplemental = proposed (supplemental projects are the utility's own plans,
      reviewed but not approved by PJM's board);
  Active (generator-interconnection upgrade not yet under an agreement) = proposed;
  On Hold is left out (its date is not reliable), as are cancelled and withdrawn upgrades.
"""
import datetime
import json
import os
import re
from collections import Counter

import build_catalog as B
from build_miso import MisoPlaces, finish, research_lines

PJM_FILE = os.path.join(B.HERE, "sources", "pjm-upgrades.json")
PJM_RESEARCH = os.path.join(B.HERE, "sources", "pjm-research-2026.json")
MARKET_PJM = "PJM"
PJM_STATES = ("PA", "OH", "VA", "WV", "MD", "NJ", "DE", "DC", "NC", "KY", "IL", "IN", "MI", "TN")

LINE_EQUIP = re.compile(r"^(Transmission Line|Conductor|Transmission Structures|Tie-in|Line and Terminal Equipment|Cable)", re.I)
# PJM's equipment field is sometimes the station work ('Circuit Breaker', 'Substation') when the description is a line:
# 'two new 2.5 mile 138 kV lines from Tollway substation to the customer site'.
LINE_SAID = re.compile(r"\b(new|rebuild\w*|reconduct\w*|construct\w*|build\w*|extension|extend\w*|establish\w*|greenfield|install\w*)\b.{0,60}?\d+(?:\.\d+)?\s*-?\s*mi(?:le)?s?\b.{0,60}?\b(line|lines|circuit|circuits|cable|feed|feeds|radial|radials)\b|"
                       r"\b(radial|radials|feed|feeds)\b.{0,40}?\d+(?:\.\d+)?\s*-?\s*mi(?:le)?s?\b|"
                       r"\b\d+(?:\.\d+)?\s*-?\s*mi(?:le)?s?\b.{0,40}?\b(new|rebuild\w*|reconduct\w*)\b.{0,40}?\b(line|lines|circuit)\b", re.I)
# Without a length, only trust line wording on rows whose equipment is a line or not given.
LINE_SAID_KV = re.compile(r"\b(rebuild\w*|reconduct\w*|construct\w*|build)\b.{0,80}?\b\d{3}\s*kV\b.{0,30}?\b(line|lines|circuit|circuits)\b", re.I)
OLD_SUB = re.compile(r"^\s*(rebuild|replace|upgrade|expand|convert|reconfigure|retire)\b.{0,60}\bexisting\b", re.I)
SUB_EQUIP = re.compile(r"^(Substation|Switching station|Ring Bus|Switching|Station Equipment|Tie-in)", re.I)
LINE_WORK = re.compile(r"\b(construct|build|new\b.{0,40}\bline|rebuild|re-?conductor|uprate|convert|conversion|loop|cut[- ]?in|"
                       r"extend|extension|relocat|double[- ]circuit|second circuit|upgrade\b.{0,30}\bline|replace\b.{0,25}conductor|"
                       r"tap\b)", re.I)
NOT_LINE = re.compile(r"^\s*(install|replace|upgrade)\b.{0,40}\b(fiber|opgw|relay|breaker|switch|wave trap|meter|ct|scada|"
                      r"communication|protection|terminal equipment|disconnect)", re.I)
NEW_SUB = re.compile(r"\b(new|construct|build|establish|create)\b.{0,50}\b(substation|switching station|switchyard|station|"
                     r"sub\b|ring bus)|\binterconnect the new substation|\bnew\b(?:\s+\S+){0,4}\s+(?:230|345|500|765)\s*kV\s+(?:GIS\s+)?bus\b|"
                     r"\bsubstation work at new\b", re.I)
LINE_REWORK = re.compile(r"\b\d{3}\s*kV\b.{0,40}?\b(line|lines|circuits?)\b.{0,15}?\b(reconduct\w*|rebuild\w*|uprate\w*)", re.I)
NEW_LINE = re.compile(r"\b(construct|build|new|install|establish|greenfield)\b.{0,60}\b(lines?|circuits?|leads?|loop|extension|tap|feeds?|radials?)\b|\bloop\b.{0,40}\binto\b|"
                      r"\bcut[- ]?(in|and loop)|\bextend\b|\binstall\w*\b.{0,40}?\bmi(?:le)?s?\b.{0,40}?\btransmission\b", re.I)
SPLIT = re.compile(r"\s*[-–—]+\s*|\s*,\s*|\s*/\s*|\s+to\s+|\s+and\s+|\s*&\s*")
ALT = [(re.compile(r"\bMt\.?\s", re.I), "Mount "), (re.compile(r"\bSt\.?\s", re.I), "Saint "), (re.compile(r"\b(Switch|Sw|Rd|Road)\b\.?", re.I), "")]


def date_of(s):
    try:
        return datetime.datetime.strptime(s, "%m/%d/%Y").date()
    except (TypeError, ValueError):
        return None


MILES = re.compile(r"\d+(?:\.\d+)?\s*-?\s*mi(?:le)?s?\b", re.I)
FIBER = re.compile(r"fiber|opgw|\bADLT\b|dielectric|exit transition", re.I)


def line_kv(r):
    """The line's own voltage: the kV written next to 'line' when there is one ('a new 7.5 mile 69 kV line'), else
    the description's kV values, else PJM's voltage field."""
    near = [int(n) for n in re.findall(r"(\d{2,3})\s*-?\s*kV\s+(?:\S+\s+){0,3}?(?:line|lines|circuit|circuits|cable|UG)\b", r["Description"], re.I)]
    if near:   # the line most of the description is about; a passing mention of a nearby line does not count
        c = Counter(near)
        return max(c, key=lambda k: (c[k], k))
    said = [int(n) for n in re.findall(r"(\d{2,3})\s*-?\s*kV", r["Description"], re.I)]
    field = [int(n) for n in re.findall(r"\d+", r["Voltage"] or "")]
    return max(said or field or [0])


def ends_of(r):
    loc = re.sub(r"\(.*?\)|\b\d{2,3}\s*-?\s*kV\b|\b(line|lines|substation|station|switchyard|ss|sub)\b", " ", r["Location"] or "", flags=re.I)
    names = [re.sub(r"\s+", " ", n).strip(" .#-") for n in SPLIT.split(loc)]
    names = [n for n in names if len(n) >= 3 and not re.fullmatch(r"(new|customer|various|multiple|tbd|n/?a)", n, re.I)]
    return list(dict.fromkeys(names))[:3]


def pjm_rows():
    """The PJM upgrades Line Watch keeps, with their type, voltage, in-service date and stage."""
    if not os.path.exists(PJM_FILE):
        return []
    out = []
    lo, hi = B.CUTOFF.strftime("%Y-%m"), B.HORIZON
    soon = (B.TODAY + datetime.timedelta(days=548)).strftime("%Y-%m")
    today = B.TODAY.strftime("%Y-%m")
    for r in json.load(open(PJM_FILE))["upgrades"]:
        st = r["Status"]
        if st in ("Cancelled", "W", "On Hold"):
            continue
        desc = re.sub(r"\s+", " ", r["Description"]).strip()
        eq = r["Equipment"]
        blank = not eq.strip()   # newer rows often carry no equipment type: read the description
        fiber_only = FIBER.search(desc) and not re.search(r"\b(rebuild|reconductor|construct|radials?|feeds?|double circuit|single circuit)\b", desc, re.I)
        lineish = LINE_EQUIP.match(eq) or blank
        strong_new = re.search(r"\b(build|construct|establish)\w*\s+(an?\s+)?(new|greenfield)\b.{0,60}\b(substation|station|switchyard|switching station)\b|"
                               r"\brelocat\w*\s+the\s+[\w .'-]{0,40}?\b(substation|station)\b", desc, re.I)
        if strong_new and re.search(r"\b(line|lines|building|house|relay\w*)\b", strong_new.group(0), re.I):
            strong_new = None   # 'a new control building at X substation', 'a new 230 kV line into X station'
        new_sub = bool(strong_new) or ((SUB_EQUIP.match(eq) or blank) and NEW_SUB.search(desc) and not OLD_SUB.search(desc))
        if new_sub and not LINE_SAID.search(desc):   # a new station without a line length is the station, not a line
            kv = max([int(n) for n in re.findall(r"\d+", r["Voltage"] or "")] + [int(n) for n in re.findall(r"(\d{3})\s*(?:/\s*\d{3}\s*)?-?\s*kV", desc, re.I)] or [0])
            ptype = "new substation"
            if kv < 230:
                continue
        elif ((lineish and (LINE_WORK.search(desc) or LINE_SAID_KV.search(desc) or LINE_REWORK.search(desc))) or LINE_SAID.search(desc)
              or (LINE_EQUIP.match(eq) and MILES.search(desc) and re.search(r"\binstall\w*\b", desc, re.I))) \
                and not NOT_LINE.search(desc) and not fiber_only:
            kv = line_kv(r)
            ptype = "new line" if NEW_LINE.search(desc) and not re.search(r"\b(rebuild|reconductor|uprate)\b", desc, re.I) else "upgrade"
        elif (SUB_EQUIP.match(eq) or blank) and NEW_SUB.search(desc) and not OLD_SUB.search(desc):
            kv = max([int(n) for n in re.findall(r"\d+", r["Voltage"] or "")] + [int(n) for n in re.findall(r"(\d{3})\s*(?:/\s*\d{3}\s*)?-?\s*kV", desc, re.I)] or [0])
            ptype = "new substation"
            if kv < 230:
                continue
        else:
            continue
        if kv < 138:
            continue
        d = date_of(r["ActualInServiceDate"]) if st == "IS" else None
        d = d or date_of(r["RevisedInServiceDate"]) or date_of(r["ProjectedInServiceDate"]) or date_of(r["ISAInServiceDate"]) or date_of(r["RequiredDate"])
        if st == "IS" and not d:
            continue
        isd = d.strftime("%Y-%m") if d else ""
        if isd and (isd < lo or isd > hi):
            continue
        sup = r["ProjectType"] == "Supplemental"
        if st == "IS":
            life, basis = "built", "PJM: in service"
        elif st.startswith("UC"):
            life, basis = "in construction", "PJM: under construction"
        elif st == "EP" and (ptype == "upgrade" or (isd and isd <= soon)):
            life, basis = "approved", "PJM: engineering and procurement" + ("" if ptype == "upgrade" else "; due within 18 months, so its route and site should be settled (estimated)")
        elif st == "EP":
            life, basis = "planned", "PJM: engineering and procurement; route or site not final yet"
        elif st == "PL" and not sup:
            life, basis = "planned", "PJM: planning (baseline project approved by PJM's board)"
        else:
            life, basis = "proposed", {"PL": "PJM: planning (utility's supplemental project, reviewed by PJM, not board-approved)",
                                       "Active": "PJM: generator-interconnection upgrade, not yet under an interconnection agreement"}.get(st, f"PJM status {st}")
        if isd and isd < today and life not in ("built", "in construction"):
            life, basis = "in construction", f"estimated: PJM's in-service date {isd} has passed and PJM has not marked it in service"
        out.append({**r, "desc": desc, "kv": kv, "ptype": ptype, "isd": isd, "life": life, "basis": basis})
    return out


def pjm_lines(places=None):
    places = places or MisoPlaces(states=PJM_STATES)
    out = []
    for r in pjm_rows():
        states = [s.strip() for s in (r["State"] or "").split(",") if s.strip() in PJM_STATES] or ["PA"]
        names = ends_of(r) or [r["Location"] or r["UpgradeId"]]
        ends = []
        for n in names:
            near = next((e for e in ends if e.get("lat") is not None), None)
            hit = None
            variants = [n] + [v for v in dict.fromkeys(rx.sub(rep, n).strip() for rx, rep in ALT) if v and v != n]
            for st in states:
                for v in variants:
                    hit = places.place({"name": v}, r["kv"], st, PAGE_URL, near)
                    if hit.get("lat") is not None:
                        hit["name"] = n
                        break
                if hit.get("lat") is not None:
                    break
            ends.append(hit)
        driver = r["Driver"] or ""
        purpose = ("generator hookup" if r["ProjectType"] == "Network" or re.search(r"generat|interconnection request", driver, re.I) or B.GENERATOR.search(r["desc"])
                   else "large-load hookup" if re.search(r"customer|load", driver, re.I) and B.BIG_LOAD.search(r["desc"] + " " + driver)
                   else "shared grid")
        detail = next((k for k, rx in B.UPGRADE_KIND if rx.search(r["desc"])), "upgrade") if r["ptype"] == "upgrade" else ""
        miles = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*mi", r["desc"], re.I)
        name = (" - ".join(e["name"] for e in ends) if len(ends) > 1 else ends[0]["name"]) + f" {r['kv']} kV" + (" substation" if r["ptype"] == "new substation" else "")
        rec = {"id": "pjm-" + r["UpgradeId"], "ercot_project": "", "name": name, "description": r["desc"][:400], "kv": r["kv"],
               "project_type": r["ptype"], "upgrade_kind": detail, "lifecycle": r["life"], "lifecycle_basis": r["basis"], "tpit_status": r["Status"],
               "utility": r["TransmissionOwner"], "from": ends[0]["name"], "to": ends[-1]["name"] if len(ends) > 1 else "",
               "county_from": ends[0].get("county", ""), "county_to": ends[-1].get("county", "") if len(ends) > 1 else "",
               "miles_new": float(miles[1]) if miles and r["ptype"] == "new line" else 0,
               "miles_upgraded": float(miles[1]) if miles and r["ptype"] == "upgrade" else 0, "transformer_mva": 0,
               "in_service": r["isd"], "in_service_kind": "actual" if r["life"] == "built" else ("projected" if r["isd"] else ""),
               "construction_start": "", "capacity_mw": None, "purpose": purpose,
               "program": f"PJM {r['ProjectType'].lower()} upgrade {r['UpgradeId']}", "rpg": "", "tier": "", "ercot_board": r["PJMBoardApprovalDate"],
               "docket": "", "route_status": "existing corridor" if r["ptype"] == "upgrade" else "end substations only", "card_id": "", "card_ids": [],
               "endpoints": ends, "market": MARKET_PJM, "state": ", ".join(states), "pjm_upgrade": r["UpgradeId"], "pjm_status": r["Status"],
               "source": PAGE_URL, "checked": f"PJM Project Construction data (fetched {json.load(open(PJM_FILE))['fetched']})"}
        out.append(finish(rec, r["kv"], "PJM approval"))
    # Projects PJM's list does not carry (generator ties, merchant lines, announced data-center hookups, state cases),
    # from research (sources/pjm-research-2026.json); ones with the same end substations as a PJM row are skipped.
    have = {frozenset((B.base(e["name"]), e.get("state", "")) for e in x["endpoints"]) for x in out}
    out += research_lines(places, have, {x["pjm_upgrade"] for x in out}, path=PJM_RESEARCH, prefix="pjmr-", market=MARKET_PJM)
    return out


PAGE_URL = "https://www.pjm.com/planning/m/project-construction"


if __name__ == "__main__":
    ls = pjm_lines()
    print(len(ls), "PJM lines", Counter(x["lifecycle"] for x in ls), Counter(x["project_type"] for x in ls))
    print(Counter(x["state"].split(",")[0] for x in ls).most_common())
    print(Counter(e["confidence"] for x in ls for e in x["endpoints"]))
    print(sum(1 for x in ls if not any(e.get("lat") is not None for e in x["endpoints"])), "with no map point")
    print(Counter(x["kv"] for x in ls), Counter(x["purpose"] for x in ls))
    for x in ls[:12]:
        print(x["id"], x["kv"], x["lifecycle"], x["in_service"], "|", x["name"], "|", [(e["name"], e["confidence"]) for e in x["endpoints"]])
