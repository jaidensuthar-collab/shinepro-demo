"""Decide which monitor signals K2 cares about, and explain each one in plain English.

K2 Renew finds land for solar, storage and data-center partners near NEW grid capacity.
So a signal matters when it points to a new or bigger high-voltage line or substation,
early enough that the land near it can still be secured. Everything else is dropped:
rebuilds of existing lines, small local lines, generator hookups for a single wind or
solar farm, neighborhood reliability work, routine paperwork and repeat status updates.

explain(signal) returns None (drop) or a dict of plain-English fields for the sheet,
the webpage database and the chatbot.
"""

import re

KV_RE = re.compile(r"(\d{2,3})\s*-?\s*kv", re.I)

# Work on an existing line or local system: no new capacity for K2's partners.
NOT_NEW_CAPACITY = ("rebuild", "replacement", "replace", "reconductor", "retermination", "relocat",
                    "pole", "cable", "gas main", "conversion", "streetlight", "communit",
                    "neighborhood", "mall", "village", "service reliability", "reactive power",
                    "wildfire", "distribution", "corridor upgrade")
# A line built only to plug in one power plant (a generator tie) adds no room for others.
GEN_TIE = re.compile(r"\bPOI\b|\bPOD\b|point of interconnection|\bwind\b|\bsolar\b|\bcollector\b", re.I)
# ERCOT documents that repeat or are not about a specific project.
RPG_NOISE = ("status update", "statusupdate", "batch", "assessment", "financial", "miscellaneous",
             "agenda", "minutes")
# News that is opinion or policy talk rather than a specific line.
NEWS_NOISE = ("opinion", "op-ed", "editorial", "study finds", "could save", "ratepayers", "bill ",
              "how we build", "letter to the editor", "podcast")
NEWS_SPECIFIC = ("kv", "open house", "route", "transmission line", "power line")

STAGES = {
    "2": "ERCOT review: the grid operator is checking the need. Usually 1 to 2 years before a route is filed.",
    "3": "Utility project page or open houses: draft route options are being shown. Usually 4 to 9 months before a route is filed.",
    "3+": "In the news: often the first public word of open houses or a fight over a route.",
    "4-5": "Route case filed at the Texas PUC: route options and landowners are now public. A decision usually takes about 6 months.",
    "5-6": "Decision stage in the route case: the PUC is close to picking, or has picked, the final route.",
}


# Substations in ERCOT's 765 kV plan (PUCT-approved Permian import paths and the Eastern Backbone).
# A line between two of them is part of the 765 kV build even when its page never says "765".
PLAN_765 = ("hillje", "blu lacy", "howard", "solstice", "bell county east", "bell east", "big hill",
            "sand lake", "watermill", "martin lake", "dinosaur", "longshore", "drill hole", "euclid")


def _max_kv(text, kv_field=""):
    values = [int(v) for v in re.findall(r"\d{2,3}", kv_field or "")] or \
             [int(v) for v in KV_RE.findall(text or "")]
    if values:
        return max(values)
    low = (text or "").lower()
    if sum(1 for name in PLAN_765 if name in low) >= 2:
        return 765
    return 0


def _project_name(title):
    """Pull the line's name out of a PUCT case title, e.g. 'Pine To Mccloud 345 Kv Transmission Line'."""
    m = re.search(r"\bFOR THE (?:PROPOSED )?(.+?)(?: PROJECT)?(?: IN [A-Z ,.'-]+ COUNT(?:Y|IES))?$",
                  title.upper())
    name = m.group(1) if m else title
    name = re.sub(r"\s+TRANSMISSION LINES?(?: PROJECT)?$", "", name)
    return name.title().replace("Kv", "kV")


def _counties(title):
    m = re.search(r"\bIN ([A-Z ,.'-]+?) COUNT(?:Y|IES)\b", title.upper())
    if not m:
        return ""
    return m.group(1).title().replace(" And ", ", ").replace(",,", ",") + (" County" if "," not in m.group(1) and " AND " not in m.group(1) else " counties")


def _short(text, limit=110):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rsplit(" ", 1)[0] + "..."


def explain(sig):
    """Return plain-English fields if K2 should care about this signal, else None."""
    title = sig.get("title", "")
    low = title.lower()
    step = sig.get("step", "").split(" ")[0]
    utility = sig.get("utility") or "A utility"
    kv = _max_kv(title, sig.get("voltage_kv", ""))

    if any(word in low for word in NOT_NEW_CAPACITY):
        return None
    if 0 < kv < 138:
        return None

    out = {"project": "", "where": "", "what_happened": "", "stage": STAGES.get(step, ""),
           "why_k2": "", "next_step": "", "importance": "High" if kv >= 345 or "765" in low else "Medium",
           "kv": str(kv) if kv else ""}

    if step == "4-5":  # new PUCT route case
        name = _project_name(title)
        if GEN_TIE.search(name):
            return None
        out["project"] = name
        out["where"] = _counties(title)
        out["what_happened"] = "%s asked the Texas PUC to approve a route for the %s line." % (utility, name)
        out["why_k2"] = ("The route options, both end substations and the landowner list are now public. "
                         "The end substations stay put whichever route wins.")
        out["next_step"] = ("Open the case, find the route map and the two end substations, "
                            "and check who owns the land around them.")
    elif step == "5-6":  # filing inside a route case already being watched
        if sig.get("priority") != "High" and not re.search(r"ROUTE|MAP|ERRATA|AMENDED APPLICATION|APPLICATION OF",
                                                           title.upper()):
            return None
        decision = sig.get("priority") == "High"
        case = sig.get("source", "").replace(" item", ", filing")
        out["what_happened"] = ("Decision news in %s: %s" if decision else "%s: %s") % (case, _short(title.capitalize(), 140))
        out["why_k2"] = ("A decision here fixes or changes where the line goes. Once a route is approved, the "
                         "utility's land agents start buying easements." if decision else
                         "The utility changed or completed its route filing, so the map of possible routes may have changed.")
        out["next_step"] = ("Read the order. If a route was picked, update the card with the final route and move fast "
                            "on land near the end substations." if decision else
                            "Open the filing and compare the route map with the one on the card.")
        out["importance"] = "High" if decision else out["importance"]
    elif step == "2":  # ERCOT planning
        if any(word in low for word in RPG_NOISE):
            return None
        # ERCOT's "scope" document repeats the utility's own submission; keep the submission.
        if "scope" in low and "recommendation" not in low:
            return None
        # Big lines and regional plans only; local load-serving projects are not K2's market.
        if kv < 345 and "765" not in low and "plan" not in low:
            return None
        name = re.sub(r"\b(EIR|Scope|Overview|Final|FinalUpdate|RPG|Recommendation|Presentation|Project)\b", "", title)
        name = re.sub(r"\b(\d{6,8}|\d{1,2}-\d{1,2}-\d{2,4}|(January|February|March|April|May|June|July|August|"
                      r"September|October|November|December)\s*\d{0,2},?\s*\d{4})\b", "", name)
        out["project"] = _short(" ".join(name.split()), 90).strip(" -_")
        out["what_happened"] = "%s brought a project to ERCOT's planning review: %s." % (utility, _short(title, 120))
        out["why_k2"] = ("This is the earliest public sign of a new line. ERCOT documents name the end substations "
                         "long before any route exists, and few people outside the industry read them.")
        out["next_step"] = ("Open the document, write down the two end substations and their counties, "
                            "and start an Opportunity Card.")
    elif step == "3":  # utility project page
        if GEN_TIE.search(title) or sig.get("note") == "completed":
            return None
        # Project pages are numerous; only big lines (345 kV and up) make the cut.
        if kv < 345 and "765" not in low:
            return None
        out["project"] = re.sub(r"\s+(Transmission\s+)?(Line\s+)?(Improvements?\s+)?Project$", "", title).strip()
        out["what_happened"] = "%s has a project page for the %s." % (utility, title)
        out["why_k2"] = ("A project page usually means open houses with draft route maps are coming or under way. "
                         "That map shows the whole area the line could cross.")
        out["next_step"] = "Check the page for open-house dates and a study-area map, and note the end substations."
    elif step == "3+":  # news
        if any(word in low for word in NEWS_NOISE) or not any(word in low for word in NEWS_SPECIFIC):
            return None
        out["project"] = ""
        out["what_happened"] = "News: %s" % _short(title, 140)
        out["why_k2"] = ("Local news often reports open houses and route fights before the official filing, "
                         "and covers lines outside Texas too.")
        out["next_step"] = "Read it. If it names a specific line or open house, add it to the watch list."
        out["importance"] = "High" if ("open house" in low or "765" in low) else "Medium"
    else:
        return None
    return out
