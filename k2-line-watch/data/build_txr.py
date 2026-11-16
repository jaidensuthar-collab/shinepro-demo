"""Texas, Oklahoma and El Paso lines the official lists miss (Nov 2026 sweep): PUC of Texas CCN cases, utilities'
monthly construction reports, ERCOT RPG reviews and Regional Transmission Plans, SPP's quarterly project tracking,
Oklahoma Corporation Commission cases, Entergy Texas and El Paso Electric status reports, and news.

sources/texas-research-2026.json   researched projects (same shape as the MISO and PJM research files, plus "market")
sources/texas-corrections-2026.json  stage or in-service changes to listed lines, and lines to drop, each with its source

A researched project is skipped when a listed line already has the same end substations (in either direction, or
one set inside the other), the same docket at the same voltage, or when ERCOT's report already lists the pair with
a date outside the window (the official date wins)."""
import json
import os
import re

import build_catalog as B
from build_miso import MisoPlaces, finish, research_lines

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.join(HERE, "sources", "texas-research-2026.json")
CORRECTIONS = os.path.join(HERE, "sources", "texas-corrections-2026.json")
# Later sweeps in the same shape: the rest of SPP (Kansas to the Dakotas, Nov 2026).
RESEARCH_FILES = [RESEARCH, os.path.join(HERE, "sources", "spp-research-2026.json"),
                  os.path.join(HERE, "sources", "caiso-research-2026.json"),   # and CAISO (California, Nov 2026)
                  os.path.join(HERE, "sources", "northeast-research-2026.json"),   # and New York / New England
                  os.path.join(HERE, "sources", "west-research-2026.json"),   # and the West outside CAISO and SPP
                  os.path.join(HERE, "sources", "southeast-research-2026.json")]   # and the Southeast (SERTP and Florida)
CORRECTION_FILES = [CORRECTIONS, os.path.join(HERE, "sources", "spp-corrections-2026.json"),
                    os.path.join(HERE, "sources", "caiso-corrections-2026.json")]


def load_research():
    files = [json.load(open(f)) for f in RESEARCH_FILES if os.path.exists(f)]
    return {"checked": max((f.get("checked", "") for f in files), default=""), "projects": [p for f in files for p in f["projects"]]}


def load_corrections():
    out = {"set": [], "drop": {}}
    for f in CORRECTION_FILES:
        if os.path.exists(f):
            d = json.load(open(f))
            out["set"] += d.get("set", [])
            out["drop"].update(d.get("drop", {}))
    return out
STATES = ["TX", "OK", "NM", "LA", "AR", "KS", "NE", "ND", "SD", "MT", "WY", "CO", "MO", "IA", "MN", "CA", "NV", "AZ", "NY", "CT", "MA", "ME", "NH", "RI", "VT", "UT", "ID", "OR", "WA", "GA", "NC", "SC", "TN", "AL", "FL", "KY", "MS"]
MARKETS = {"ERCOT": B.MARKET, "SPP": "SPP", "MISO": "MISO", "WECC": "WECC", "CAISO": "CAISO", "NYISO": "NYISO", "ISO-NE": "ISO-NE", "West": "West", "Southeast": "Southeast"}
PREFIX = {"ERCOT": "txr-", "SPP": "sppr-", "MISO": "etrr-", "WECC": "eper-", "CAISO": "caisor-", "NYISO": "nyr-", "ISO-NE": "isner-", "West": "westr-", "Southeast": "ser-"}
RESEARCHED = "Line Watch research"


FILLER = {"COLLECTOR", "COLLECTION", "STATIONS", "SOLAR", "WIND", "BESS", "STORAGE", "AND", "PROJECT", "PLANT", "ENERGY",
          "CENTER", "MW", "GEN", "TIE", "WETT", "LST", "ETT", "SHARYLAND", "INTERCONNECTION", "ON", "OF", "THE", "CUT", "IN",
          "LINE", "CUSTOMER", "TRANSMISSION", "ENTERGY", "TEXAS", "UNNAMED", "ORDER", "BULK"}


def key(name):
    return B.alias(B.base(name))


def words(name):
    return frozenset(w for w in key(name).split() if w not in FILLER and not w.isdigit())


def toks(name):
    """Name words that identify a station: 'Tiger Solar (255 MW) collector' and 'Tiger Solar POI' are both {TIGER};
    'Mulberry 765 kV (new)' and 'Mulberry Creek' share {MULBERRY}. A name in brackets is a second name for the same
    station: 'Ciruela (Panther)' matches 'Panther' too."""
    alts = [words(name)] + [words(a) for a in re.findall(r"\(([^)]*)\)", str(name))]
    return tuple(a for a in alts if a)


def same(a, b):
    return any(x <= y or y <= x for x in a for y in b)


def ends_of(x):
    return (frozenset(str(x.get("state", "TX")).replace(" ", "").split(",")), [t for t in (toks(e["name"]) for e in x["endpoints"]) if t])


def tpit_pairs():
    """End-substation pairs of every ERCOT report row at 138 kV+, in or out of the window."""
    out, ids = [], set()
    for r in B.read_tpit(os.path.join(HERE, "sources", "ercot-tpit-2026-10.xlsx")):
        ids.add(str(r["id"]).strip().upper())
        if B.num(r["kv"]) < 138:
            continue
        names = [t for t in (toks(n) for n, _ in B.terminals(r) if n) if t]   # bus-number ends named from the title
        if len(names) >= 2:
            out.append((names, int(B.num(r["kv"]))))
    return out, ids


def covers(ends, h):
    """Every end of the shorter list matches a different end of the longer one (at least two ends)."""
    short, long_ = (ends, h) if len(ends) <= len(h) else (h, ends)
    if len(short) < 2:
        return False
    free = list(long_)
    for t in short:
        m = next((u for u in free if same(t, u)), None)
        if m is None:
            return False
        free.remove(m)
    return True


def pstates(p):
    """A researched project's own state field may name several states ('GA, AL')."""
    return {s.strip() for s in str(p["state"]).split(",") if s.strip()}


def duplicate(p, listed, pairs):
    ends = [t for t in (toks(e["name"]) for e in p["ends"]) if t]
    states = pstates(p) | {e["state"] for e in p["ends"]}
    listed = [h for st, h in listed if st & states]   # same names in another state are other stations
    if len(ends) >= 2:
        if any(covers(ends, h) for h in listed):
            return True
        if p.get("market") == "ERCOT" and any(kv == p["kv"] and covers(ends, names) for names, kv in pairs):
            return True   # ERCOT's report lists it; its own rules (dates, size, stage) decide whether it is in the window
    elif len(ends) == 1 and p["project_type"] == "new substation":
        return any(same(ends[0], u) for h in listed for u in h)   # already an end of a listed line, so already a site on the map
    return False


def txr_lines(out):
    src = load_research()
    if not src["projects"]:
        return []
    listed = [ends_of(x) for x in out]
    dockets = {(str(x.get("docket") or "").strip(), x["kv"]) for x in out if str(x.get("docket") or "").strip()}
    (pairs, tpit_ids), keep = tpit_pairs(), []
    for p in src["projects"]:
        gap = re.search(r"tpit-gap-(\w+)", p["key"])
        if gap and gap[1].upper() in tpit_ids:
            continue   # a row of ERCOT's report: the report's own rules decide whether it is a line in the window
        if duplicate(p, listed, pairs) or (p.get("docket") and (str(p["docket"]).strip(), p["kv"]) in dockets and p["project_type"] != "new substation"):
            continue
        keep.append(p)
        listed.append((frozenset(pstates(p) | {e["state"] for e in p["ends"]}), [t for t in (toks(e["name"]) for e in p["ends"]) if t]))   # the sweep files overlap each other too
    places = MisoPlaces(states=STATES)
    have = {frozenset((B.base(e["name"]), e.get("state", "")) for e in x["endpoints"]) for x in out}
    lines = []
    for m, label in MARKETS.items():
        part = [p for p in keep if p.get("market", "ERCOT") == m]
        lines += research_lines(places, have, (), prefix=PREFIX[m], market=label, src={**src, "projects": part})
    gen = re.compile(r"GEN[- ]?TIE|GENERATION TIE|GENERATOR|\bSOLAR\b|\bWIND\b|\bBESS\b|STORAGE|GEN-\d{4}|\bPOI\b", re.I)
    for x in lines:
        x["checked"] = f"{RESEARCHED}, {src.get('checked', '')} (Texas and SPP sweeps)"
        if x["purpose"] == "shared grid" and gen.search(x["name"]):
            x["purpose"] = "generator hookup"   # a tie for one plant adds no shared capacity
            finish(x, x["kv"], "the regulator's decision")
    return lines


def apply_corrections(out):
    """Stage and date changes to listed lines where a newer public source shows the official list is behind."""
    fix = load_corrections()
    drop = set(fix.get("drop", {}))
    by_id = {x["id"]: x for x in out}
    for c in fix.get("set", []):
        x = by_id.get(c["id"])
        if not x:
            continue
        if "stage" in c:
            x["lifecycle"] = c["stage"]
        if "in_service" in c:
            x["in_service"] = c["in_service"]
            x["in_service_kind"] = "actual" if x["lifecycle"] == "built" else "projected"
        x["lifecycle_basis"] = f"{RESEARCHED}: {c['basis']}"
        x["source"] = "; ".join([x["source"]] + c["sources"][:2])
        finish(x, x["kv"], "the source")
    return [x for x in out if x["id"] not in drop and not (x["in_service"] and x["in_service"][:7] > B.HORIZON)]
