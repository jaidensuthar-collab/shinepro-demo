#!/usr/bin/env python3
"""K2 line monitor: find new Texas transmission-line signals before routes are approved.

It checks three kinds of public sources, earliest signal first:

  Step 2  ERCOT Regional Planning Group (RPG) meeting documents
          (new project submissions, scopes and recommendations; names the end substations)
  Step 3  Utility project pages (Oncor, AEP Texas, LCRA)
          (a new page usually means open houses with preliminary route links are coming)
  Step 4-5 PUCT Interchange: new electric cases asking to amend a
          Certificate of Convenience and Necessity (CCN) for a transmission line

Every signal gets a stable ID. Pass the IDs you have already seen (one per line)
with --seen and only new signals are reported. Standard library only, so it runs
on Python 3.9+ with nothing to install.

Examples:
  python3 monitor.py                         # print everything found right now
  python3 monitor.py --seen seen.txt         # only what is new since last time
  python3 monitor.py --seen seen.txt --json new.json --rows rows.json
"""

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

USER_AGENT = "Mozilla/5.0 (compatible; K2LineMonitor/1.0)"

PUCT_SEARCH = "https://interchange.puc.texas.gov/search/search/"
PUCT_DOCKET = ("https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber={cn}"
               "&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending")

# Any recent RPG meeting page works as a starting point; the walker follows the
# links between meetings to reach the newest one.
RPG_SEED = "https://www.ercot.com/calendar/09222026-RPG-Meeting"

UTILITY_PAGES = [
    # (utility, list page, prefix every project page starts with)
    ("Oncor",
     "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/"
     "current-transmission-line-projects.html",
     "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/"
     "current-transmission-line-projects/"),
    ("AEP Texas",
     "https://aeptransmission.com/texas/",
     "https://aeptransmission.com/texas/"),
    ("LCRA TSC",
     "https://www.lcra.org/energy/electric-transmission/transmission-line-routing/",
     "https://www.lcra.org/energy/electric-transmission/transmission-line-routing/"),
]

KNOWN_UTILITIES = [
    ("CENTERPOINT", "CenterPoint"), ("CNP", "CenterPoint"), ("CEHE", "CenterPoint"),
    ("ONCOR", "Oncor"), ("AEPSC", "AEP"), ("AEP", "AEP Texas"), ("CPS", "CPS Energy"),
    ("LCRA", "LCRA TSC"), ("TNMP", "TNMP"), ("TEXAS-NEW MEXICO", "TNMP"),
    ("WETT", "WETT"), ("WIND ENERGY TRANSMISSION", "WETT"), ("STEC", "STEC"),
    ("SOUTH TEXAS ELECTRIC", "STEC"), ("BRAZOS", "Brazos Electric"), ("BEC", "Brazos Electric"),
    ("DME", "Denton Municipal"), ("DENTON", "Denton Municipal"), ("AUSTIN ENERGY", "Austin Energy"),
    ("EL PASO ELECTRIC", "El Paso Electric"), ("SOUTHWESTERN ELECTRIC POWER", "SWEPCO"),
    ("SOUTHWESTERN PUBLIC SERVICE", "SPS (Xcel)"), ("ENTERGY", "Entergy Texas"),
    ("GSEC", "Golden Spread"), ("GOLDEN SPREAD", "Golden Spread"), ("SHARYLAND", "Sharyland"),
    ("CROSS TEXAS", "Cross Texas"), ("CTT", "Cross Texas"), ("LONESTAR", "Lone Star Transmission"),
    ("LPL", "Lubbock Power & Light"), ("LUBBOCK", "Lubbock Power & Light"),
    ("PEC", "Pedernales Electric"), ("PEDERNALES", "Pedernales Electric"), ("AEN", "Austin Energy"),
    ("RAYBURN", "Rayburn Electric"), ("BRYAN TEXAS", "BTU"), ("GARLAND", "Garland Power & Light"),
]

KV_RE = re.compile(r"(\d{2,3})(?:\s*/\s*(\d{2,3}))?\s*-?\s*kv\b", re.I)
RPG_ID_RE = re.compile(r"\b\d{2}RPG\d{3}\b", re.I)
MEETING_RE = re.compile(r"https://www\.ercot\.com/calendar/(\d{2})(\d{2})(\d{4})-RPG-Meeting")
RPG_SKIP = ("agenda", "minutes", "miscellaneous", "financial assumptions", "antitrust",
            "meeting notes", "announcement", "batch zero", "batch-zero", "resiliency assessment")
RPG_KEEP = ("kv", "transmission", "line", "substation", "rpg", "reliability", "upgrade",
            "improvement", "project")


@dataclass
class Signal:
    id: str
    step: str
    source: str
    utility: str
    voltage_kv: str
    title: str
    source_date: str
    url: str
    priority: str = ""


def fetch(url, timeout=45, retries=2):
    """Download a page as text, retrying briefly on network errors."""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("could not fetch %s: %s" % (url, last))


def short_id(prefix, url):
    """Stable short ID for a URL, so the Monitor Feed stays compact."""
    key = url.lower().rstrip("/")
    return "%s:%s" % (prefix, hashlib.sha1(key.encode("utf-8")).hexdigest()[:10])


def clean(fragment):
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("_", " ")
    return " ".join(text.split())


def priority(kv, title):
    """High: 345 kV and up. Low: rebuilds, small lines and routine status updates. Else Medium."""
    t = title.lower()
    top = max([int(v) for v in kv.split("/") if v] or [0])
    if any(w in t for w in ("status update", "statusupdate", "rebuild", "retermination", "replacement")):
        return "Low"
    if top >= 345 or "765" in t:
        return "High"
    if 0 < top < 100:
        return "Low"
    return "Medium"


def anchors(page_html):
    for href, inner in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S | re.I):
        yield html.unescape(href), clean(inner)


def voltage(text):
    found = []
    for a, b in KV_RE.findall(text):
        for v in (a, b):
            if v and v not in found:
                found.append(v)
    found.sort(key=int, reverse=True)
    return "/".join(found)


def guess_utility(text):
    upper = text.upper()
    names = []
    for key, name in KNOWN_UTILITIES:
        if re.search(r"(?<![A-Z])" + re.escape(key) + r"(?![A-Z])", upper) and name not in names:
            names.append(name)
    return ", ".join(names)


# ---------------------------------------------------------------- PUCT (steps 4-5)

def is_transmission_case(description):
    d = description.upper()
    if "CERTIFICATE OF CONVENIENCE" not in d:
        return False
    # Battery or plant purchases also amend CCNs but name no line voltage.
    return bool(KV_RE.search(d)) or "TRANSMISSION LINE" in d


def parse_puct_dockets(page_html):
    """Rows of the PUCT docket list: control number, item, filing party, description."""
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S | re.I):
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) >= 4 and cells[0].isdigit():
            rows.append({"control": cells[0], "party": cells[2], "description": cells[3]})
    return rows


def puct_signals(days, today):
    signals = []
    start = today - dt.timedelta(days=days)
    # Query in two-week windows so a busy month never hits a page limit.
    window_start = start
    while window_start <= today:
        window_end = min(window_start + dt.timedelta(days=13), today)
        query = urllib.parse.urlencode({
            "UtilityType": "E", "ItemMatch": "Equal", "ItemNumber": "1", "DocumentType": "ALL",
            "DateFiledFrom": window_start.isoformat(), "DateFiledTo": window_end.isoformat(),
        })
        for row in parse_puct_dockets(fetch(PUCT_SEARCH + "?" + query)):
            if not is_transmission_case(row["description"]):
                continue
            signals.append(Signal(
                id="puct:%s" % row["control"],
                step="4-5 PUCT route case opened",
                source="PUCT Docket %s" % row["control"],
                utility=guess_utility(row["party"] + " " + row["description"]) or row["party"].title(),
                voltage_kv=voltage(row["description"]),
                title=row["description"].title(),
                source_date="filed %s to %s" % (window_start.isoformat(), window_end.isoformat()),
                url=PUCT_DOCKET.format(cn=row["control"]),
            ))
        window_start = window_end + dt.timedelta(days=1)
    return signals


# ---------------------------------------------------------------- ERCOT RPG (step 2)

def meeting_date(url):
    m = MEETING_RE.match(url)
    if not m:
        return None
    month, day, year = (int(x) for x in m.groups())
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def parse_rpg_page(page_html):
    """Return (links to other RPG meetings, documents posted for this meeting)."""
    meetings, docs = set(), []
    for href, text in anchors(page_html):
        if MEETING_RE.match(href):
            meetings.add(MEETING_RE.match(href).group(0))
        elif "/files/docs/" in href:
            url = urllib.parse.urljoin("https://www.ercot.com/", href)
            docs.append((text, url))
    return meetings, docs


def is_relevant_rpg_doc(title):
    t = title.lower()
    if any(word in t for word in RPG_SKIP):
        return False
    return any(word in t for word in RPG_KEEP)


def rpg_signals(today, seed=RPG_SEED, max_pages=8, lookback_days=120):
    """Walk RPG meeting pages from the seed toward the newest, newest first."""
    signals, fetched, known = [], set(), {seed}
    oldest = today - dt.timedelta(days=lookback_days)
    while len(fetched) < max_pages:
        candidates = sorted(
            (u for u in known - fetched
             if meeting_date(u) and oldest <= meeting_date(u) <= today + dt.timedelta(days=45)),
            key=meeting_date, reverse=True)
        if not candidates:
            break
        url = candidates[0]
        fetched.add(url)
        try:
            meetings, docs = parse_rpg_page(fetch(url))
        except RuntimeError:
            continue
        known |= meetings
        held = meeting_date(url)
        for title, doc_url in docs:
            if not is_relevant_rpg_doc(title):
                continue
            ids = sorted(set(x.upper() for x in RPG_ID_RE.findall(title + " " + doc_url)))
            signals.append(Signal(
                id=short_id("rpg", doc_url),
                step="2 ERCOT planning review",
                source="ERCOT RPG meeting %s%s" % (held.isoformat(), (" (" + ", ".join(ids) + ")") if ids else ""),
                utility=guess_utility(title),
                voltage_kv=voltage(title),
                title=re.sub(r"^\d+\.\s*", "", title),
                source_date=held.isoformat(),
                url=doc_url,
            ))
        time.sleep(1)
    if not fetched:
        raise RuntimeError("no RPG meeting page could be read; update RPG_SEED to a recent meeting")
    return signals


# ---------------------------------------------------------------- utility pages (step 3)

def parse_utility_projects(page_html, page_url, prefix):
    """Project links that sit exactly one level below the utility's project-list prefix."""
    projects, seen = [], set()
    pre = prefix.lower()
    for href, text in anchors(page_html):
        url = urllib.parse.urljoin(page_url, href).split("#")[0].split("?")[0]
        low = url.lower()
        if not low.startswith(pre):
            continue
        rest = low[len(pre):].strip("/")
        if not rest or "/" in rest or rest.endswith((".pdf", ".php")) or not text:
            continue
        key = low.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        projects.append((text, url))
    return projects


def utility_signals():
    signals, errors = [], []
    for utility, page, prefix in UTILITY_PAGES:
        try:
            projects = parse_utility_projects(fetch(page), page, prefix)
        except RuntimeError as err:
            errors.append("%s: %s" % (utility, err))
            continue
        if not projects:
            errors.append("%s: page loaded but no project links matched; the site layout may have changed" % utility)
        for title, url in projects:
            signals.append(Signal(
                id=short_id("util", url),
                step="3 utility project page (open houses)",
                source="%s project list" % utility,
                utility=utility,
                voltage_kv=voltage(title),
                title=title,
                source_date="",
                url=url,
            ))
    return signals, errors


# ---------------------------------------------------------------- main

SHEET_HEADER = ["Found", "Priority", "Step", "Source", "Utility", "kV", "Title", "Source date", "Link",
                "ID", "Status"]


def to_row(sig, found, status):
    # The leading apostrophe keeps Sheets from turning "345/138" into a date.
    kv = ("'" + sig.voltage_kv) if sig.voltage_kv else ""
    return [found, sig.priority, sig.step, sig.source, sig.utility, kv, sig.title,
            sig.source_date, sig.url, sig.id, status]


def run(args):
    today = dt.date.today() if not args.today else dt.date.fromisoformat(args.today)
    seen = set()
    if args.seen:
        try:
            with open(args.seen, encoding="utf-8") as fh:
                seen = {line.strip() for line in fh if line.strip()}
        except FileNotFoundError:
            pass

    signals, errors = [], []
    sources = {"puct", "rpg", "util"} if args.only == "all" else {args.only}
    if "puct" in sources:
        try:
            signals += puct_signals(args.puct_days, today)
        except RuntimeError as err:
            errors.append("PUCT: %s" % err)
    if "rpg" in sources:
        try:
            signals += rpg_signals(today, seed=args.rpg_seed)
        except RuntimeError as err:
            errors.append("ERCOT RPG: %s" % err)
    if "util" in sources:
        util, util_errors = utility_signals()
        signals += util
        errors += util_errors

    unique, ids = [], set()
    for sig in signals:
        if sig.id not in ids:
            ids.add(sig.id)
            sig.priority = priority(sig.voltage_kv, sig.title)
            unique.append(sig)
    order = {"High": 0, "Medium": 1, "Low": 2}
    unique.sort(key=lambda s: (order[s.priority], s.step))
    new = [s for s in unique if s.id not in seen]

    status = "Known at start" if args.baseline else "New"
    rows = [to_row(s, today.isoformat(), status) for s in new]
    report = {"checked": today.isoformat(), "total_found": len(unique), "new": [asdict(s) for s in new],
              "errors": errors}
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    if args.rows:
        with open(args.rows, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    print("Checked %s: %d signals found, %d new." % (today.isoformat(), len(unique), len(new)))
    for s in new:
        print("- %-6s [%s] %s | %s | %s kV | %s" % (s.priority, s.step, s.source, s.utility or "?",
                                                    s.voltage_kv or "?", s.title))
    for e in errors:
        print("! " + e, file=sys.stderr)
    return 2 if errors and not unique else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seen", help="file of IDs already reported, one per line")
    p.add_argument("--json", help="write the full report as JSON here")
    p.add_argument("--rows", help="write new signals as rows for the Monitor Feed tab (JSON 2D array)")
    p.add_argument("--baseline", action="store_true", help="mark everything as 'Known at start' (first run)")
    p.add_argument("--only", choices=["all", "puct", "rpg", "util"], default="all")
    p.add_argument("--puct-days", type=int, default=30, help="how far back to look for new PUCT cases")
    p.add_argument("--rpg-seed", default=RPG_SEED, help="any recent ERCOT RPG meeting page URL")
    p.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
