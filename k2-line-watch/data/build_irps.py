"""Build data/irps.json (IRP pilot) from the research files in irp_research/.

  python3 build_irps.py

Each research record follows one schema (see irp_research/*.json). A few numbers are
adjusted here so the page's rankings compare like with like; every adjustment is noted
in the record itself.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = ("part1.json", "part2.json", "part3.json")

# Market tiers from the K2 plan (priority "C" markets; DFW, Phoenix, Chicago, Atlanta cores lower).
PRIORITY = {"MS", "LA", "WI", "IN", "IA", "KS", "MO", "OK", "AR", "TX", "WV", "KY", "NE", "WA", "OR", "MI", "MN", "TN",
            "SC", "NM", "AL", "PA", "OH", "NC", "UT"}


def adjust(u):
    load = u.setdefault("load", {})
    if u["id"] == "entergy-mississippi" and load.get("data_center_mw"):
        load["large_load_notes"] = (load.get("large_load_notes") or "") + (
            " (Data-center MW left blank here: the 1,034 MW is substation capacity built for Amazon, not a load forecast.)")
        load["data_center_mw"] = None
    if u["id"] == "ercot":
        u["context"] = True
        load["energy_growth_note"] = ("Not ranked with the utilities: the preliminary forecast's growth rate (about 22% a year) "
                                      "comes from a large-load request queue that ERCOT itself is cutting. " + (load.get("energy_growth_note") or ""))
        load["peak_growth_pct_per_year"] = None
        for g in u.get("generation_adds") or []:
            g["note"] = "Interconnection requests in ERCOT's queue, not planned plants. " + (g.get("note") or "")
        u["queue_not_plan"] = True
    u["priority_market"] = any(s in PRIORITY for s in u.get("states") or [])
    return u


def main():
    recs = []
    for part in PARTS:
        with open(os.path.join(HERE, "irp_research", part), encoding="utf-8") as fh:
            recs += [adjust(u) for u in json.load(fh)]
    ids = [u["id"] for u in recs]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for u in recs:
        assert u.get("sources"), u["id"] + " has no sources"
    with open(os.path.join(HERE, "irps.json"), "w", encoding="utf-8") as fh:
        json.dump(recs, fh, indent=1, ensure_ascii=False)
    print("%d IRP records" % len(recs))


if __name__ == "__main__":
    main()
