#!/usr/bin/env python3
"""K2 Line Watch runner: every Line Watch job as one plain command, for any agent or scheduler.

Nothing here calls an AI model or needs a Claude, Google or Hermes account. Each command reads and
writes plain files under state/ (the "memory" of Line Watch), prints a short Markdown summary that
an agent can pass on as-is, and exits non-zero only when something actually failed. That way the same
jobs run from Claude scheduled tasks, Hermes cron jobs (agent or --no-agent mode), OpenClaw, GitHub
Actions or a plain crontab, and the agent only adds the parts that need judgment or app access
(syncing to the Google Sheet, publishing the page, drafting emails).

Commands
  python3 lw.py watch [--quiet]      Check every source for new signals (twice a day).
                                     New K2 signals are added to state/k2-watch.csv, state/signals/
                                     and state/seen.txt; the sheet rows and database writes for this
                                     run are left in state/runs/<time>/ for an agent to sync.
                                     --quiet prints nothing when there is nothing new (Hermes
                                     --no-agent jobs stay silent on empty output).
  python3 lw.py texas [--force]      Refresh the Texas lines list when Oncor's CCN viewer or ERCOT's
                                     TPIT report changed: rebuild, run the data checks, summarize
                                     what changed. Exit 0 = fine, 1 = a data check failed, 3 = a new
                                     TPIT edition was downloaded and the code needs its new date.
  python3 lw.py export-page          Write web/data/line-watch-state.json so the page works as a
                                     plain static website (no Claude database needed).
  python3 lw.py status               One-paragraph status: last check, counts, sources.
  python3 lw.py import-sheet FILE    Rebuild state/k2-watch.csv and state/signals/ from a CSV
                                     download of the 'K2 Watch' tab (File > Download > CSV).

Standard library only (the Texas rebuild also needs openpyxl, like data/build_catalog.py).
"""

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
DATA = os.path.join(HERE, "data")
WEB = os.path.join(HERE, "web")
SHEET_HEADER = ["Found", "Importance", "What happened", "Project", "Utility", "kV", "Where",
                "What this kind of signal means", "Why K2 cares", "What to do next", "Link", "ID", "Status"]
ERCOT_PLANNING = "https://www.ercot.com/gridinfo/planning"
PAGE_URL = "https://claude.ai/artifact/FCARNQ1KQBr5r5DX9V6XfG"
VOLATILE_KEYS = {"fetched", "fetched_at", "retrieved", "generated", "as_of"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


# ---------- small helpers ----------

def now_ct():
    """Current time in US Central (CST/CDT), without needing tz data on the machine."""
    utc = dt.datetime.now(dt.timezone.utc)
    year = utc.year
    # DST: second Sunday of March 2am to first Sunday of November 2am, local time.
    march = dt.datetime(year, 3, 8, 8, tzinfo=dt.timezone.utc)
    start = march + dt.timedelta(days=(6 - march.weekday()) % 7)
    nov = dt.datetime(year, 11, 1, 7, tzinfo=dt.timezone.utc)
    end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7)
    offset = -5 if start <= utc < end else -6
    return (utc + dt.timedelta(hours=offset)).replace(tzinfo=None)


def doc_id(signal_id):
    """'puct:60319:83' -> 'puct_60319_83' (same rule as monitor.db_doc_id)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", signal_id)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def read_seen(state=STATE):
    try:
        with open(os.path.join(state, "seen.txt"), encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]
    except FileNotFoundError:
        return []


def add_seen(ids, state=STATE):
    have = set(read_seen(state))
    fresh = [i for i in ids if i and i not in have]
    if fresh:
        with open(os.path.join(state, "seen.txt"), "a", encoding="utf-8") as fh:
            for i in fresh:
                fh.write(i + "\n")
    return fresh


def append_csv(rows, state=STATE):
    path = os.path.join(state, "k2-watch.csv")
    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(SHEET_HEADER)
        for r in rows:
            w.writerow([str(c).lstrip("'") if i == 5 else c for i, c in enumerate(r)])


def strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(x) for x in obj]
    return obj


def py(script, *args, cwd=HERE, timeout=900):
    """Run one of the Line Watch scripts with this Python; return (code, stdout, stderr)."""
    p = subprocess.run([sys.executable, script, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


# ---------- watch ----------

def cmd_watch(args, state=STATE):
    os.makedirs(state, exist_ok=True)
    stamp = now_ct().strftime("%Y-%m-%dT%H%M")
    run_dir = os.path.join(state, "runs", stamp)
    os.makedirs(run_dir, exist_ok=True)
    seen_file = os.path.join(state, "seen.txt")
    if not os.path.exists(seen_file):
        print("state/seen.txt is missing: without it every old signal would be reported again. "
              "Restore it from git or run 'lw.py import-sheet' first.", file=sys.stderr)
        return 1
    rows_p, report_p, db_dir = (os.path.join(run_dir, n) for n in ("rows.json", "report.json", "db"))
    code, out, err = py("monitor.py", "--seen", seen_file, "--rows", rows_p, "--json", report_p,
                        "--db-dir", db_dir, "--puct-days", str(args.puct_days))
    report = read_json(report_p)
    if report is None:
        print("The monitor failed before writing a report.\n" + (err or out)[-1500:], file=sys.stderr)
        return code or 1
    rows = read_json(rows_p, [])
    records = report.get("new", [])

    for rec in records:
        write_json(os.path.join(state, "signals", doc_id(rec["id"]) + ".json"), rec)
    append_csv(rows, state)
    add_seen([r[11] for r in rows], state)

    status = read_json(os.path.join(state, "status.json"), {}) or {}
    status.update({"last_checked": now_ct().strftime("%Y-%m-%d %H:%M") + " CT",
                   "last_run_found": report.get("total_found", 0),
                   "last_run_new_for_k2": len(records),
                   "kept": len(glob.glob(os.path.join(state, "signals", "*.json"))),
                   "dropped_not_k2": int(status.get("dropped_not_k2", 0)) + report.get("dropped_not_k2", 0),
                   "last_run_dir": os.path.relpath(run_dir, HERE),
                   "source_errors": report.get("errors", [])})
    write_json(os.path.join(state, "status.json"), status)

    if args.quiet and not records and not report.get("errors"):
        return 0
    print(watch_summary(report, rows, run_dir))
    return 0


def watch_summary(report, rows, run_dir):
    records = report.get("new", [])
    high = [r for r in records if r.get("importance") == "High"]
    lines = [f"**Line Watch check {report.get('checked')}**: {len(records)} new K2 signal(s) "
             f"({len(high)} High), {report.get('total_found', 0)} found in all, "
             f"{report.get('dropped_not_k2', 0)} not relevant to K2."]
    for r in records:
        kv = r.get("kv") or r.get("voltage_kv") or ""
        lines.append(f"- **{r.get('importance')}** {r.get('what_happened')}"
                     + (f" ({kv} kV)" if kv else "") + f" [link]({r.get('url')})")
    if report.get("errors"):
        lines.append("Source errors: " + "; ".join(report["errors"]))
    if rows:
        rel = os.path.relpath(run_dir, HERE)
        lines.append(f"To sync: append {rel}/rows.json to 'K2 Watch'!A:M; database writes are in {rel}/db/writes.json.")
    return "\n".join(lines)


# ---------- texas ----------

def tpit_edition(url):
    """'.../ERCOT-October-TPIT-No-Cost-100126.xlsx' -> (2026, 10, 1)."""
    m = re.search(r"(\d{2})(\d{2})(\d{2})\.xlsx$", url)
    if not m:
        return None
    return 2000 + int(m.group(3)), int(m.group(1)), int(m.group(2))


def latest_local_tpit():
    files = sorted(glob.glob(os.path.join(DATA, "sources", "ercot-tpit-*.xlsx")))
    if not files:
        return None
    y, mo = re.search(r"(\d{4})-(\d{2})", os.path.basename(files[-1])).groups()
    return int(y), int(mo)


def find_tpit_link():
    req = urllib.request.Request(ERCOT_PLANNING, headers={"User-Agent": "K2-Line-Watch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="([^"]*TPIT[^"]*\.xlsx)"', html, re.I)))
    links = [l if l.startswith("http") else "https://www.ercot.com" + l for l in links]
    return links[-1] if links else None


def lines_diff(before, after):
    la = {x["id"]: x for x in (before or {}).get("lines", [])}
    lb = {x["id"]: x for x in (after or {}).get("lines", [])}
    added = [lb[k] for k in lb if k not in la]
    removed = [la[k] for k in la if k not in lb]
    stages = [(lb[k], la[k].get("lifecycle"), lb[k].get("lifecycle")) for k in lb
              if k in la and la[k].get("lifecycle") != lb[k].get("lifecycle")]
    return added, removed, stages


def cmd_texas(args):
    out = []
    oncor = os.path.join(DATA, "sources", "oncor-ccn.json")
    before_oncor = read_json(oncor)
    with open(oncor, "rb") as fh:
        before_bytes = fh.read()
    code, so, se = py(os.path.join("data", "fetch_oncor_ccn.py"), timeout=300)
    after_oncor = read_json(oncor)
    oncor_changed = strip_volatile(before_oncor) != strip_volatile(after_oncor)
    if code != 0:
        out.append("Oncor CCN viewer: fetch failed, kept the last copy. " + (se or so)[-300:])
        oncor_changed = False
    if not oncor_changed:
        with open(oncor, "wb") as fh:  # only the fetch date moved: put the exact old file back
            fh.write(before_bytes)
    out.append("Oncor CCN viewer: " + ("changed" if oncor_changed else "no change"))

    tpit_new = False
    try:
        link = find_tpit_link()
        ed = tpit_edition(link) if link else None
        local = latest_local_tpit()
        if ed and (not local or (ed[0], ed[1]) > local):
            dest = os.path.join(DATA, "sources", f"ercot-tpit-{ed[0]}-{ed[1]:02d}.xlsx")
            req = urllib.request.Request(link, headers={"User-Agent": "K2-Line-Watch/1.0"})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as fh:
                fh.write(r.read())
            tpit_new = True
            out.append(f"ERCOT TPIT: NEW edition {MONTHS[ed[1] - 1]} {ed[2]}, {ed[0]} downloaded to "
                       f"{os.path.relpath(dest, HERE)}. Before rebuilding, point data/build_catalog.py "
                       f"(default TPIT path and the 'October 1, 2026 update' source text) and "
                       f"data/check_catalog.py at it; keep the older editions.")
        else:
            out.append("ERCOT TPIT: no new edition" + (f" (latest {link.rsplit('/', 1)[-1]})" if link else ""))
    except Exception as e:  # network trouble is a report line, not a crash
        out.append(f"ERCOT TPIT: could not check the planning page ({e}); try again at the next run "
                   f"or open {ERCOT_PLANNING} and compare the TPIT file name with data/sources/")
    if tpit_new:
        print("\n".join(out))
        return 3

    if not (oncor_changed or args.force):
        print("**Texas lines list**: no source changed, no rebuild.\n" + "\n".join("- " + l for l in out))
        return 0

    committed = read_json(os.path.join(WEB, "data", "texas-lines.json"))
    projects = os.path.join(STATE, "projects")
    code, so, se = py(os.path.join("data", "build_catalog.py"), projects)
    if code != 0:
        print("**Texas lines list**: the build failed.\n" + (se or so)[-1500:])
        return 1
    code, so, se = py(os.path.join("data", "check_catalog.py"))
    passed = code == 0 and "checks passed" in so
    tail = [l for l in so.splitlines() if "checks passed" in l]
    added, removed, stages = lines_diff(committed, read_json(os.path.join(WEB, "data", "texas-lines.json")))
    out.append(f"Data checks: {tail[-1] if tail else 'see output'}" + ("" if passed else " (FAILED: do not publish)"))
    out.append(f"Lines added: {len(added)}; removed: {len(removed)}; stage changes: {len(stages)}")
    for x in added[:15]:
        out.append(f"  + {x.get('name')} ({x.get('kv')} kV, {x.get('lifecycle')})")
    for x in removed[:15]:
        out.append(f"  - {x.get('name')} ({x.get('kv')} kV)")
    for x, a, b in stages[:15]:
        out.append(f"  ~ {x.get('name')} ({x.get('kv')} kV): {a} -> {b}")
    print("**Texas lines list rebuilt**\n" + "\n".join("- " + l if not l.startswith("  ") else l for l in out))
    return 0 if passed else 1


# ---------- page, status, import ----------

def load_dir(folder):
    docs = []
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        d = read_json(f)
        if isinstance(d, dict):
            d.setdefault("id", os.path.splitext(os.path.basename(f))[0])
            docs.append(d)
    return docs


def cmd_export_page(args):
    page = {"generated": now_ct().strftime("%Y-%m-%d %H:%M") + " CT",
            "meta": read_json(os.path.join(STATE, "status.json"), {}),
            "projects": load_dir(os.path.join(STATE, "projects")),
            "signals": load_dir(os.path.join(STATE, "signals")),
            "irps": read_json(os.path.join(DATA, "irps.json"), [])}
    dest = os.path.join(WEB, "data", "line-watch-state.json")
    write_json(dest, page)
    print(f"Wrote {os.path.relpath(dest, HERE)}: {len(page['projects'])} projects, {len(page['signals'])} signals. "
          "Serve the web/ folder from any static host (GitHub Pages works) to use the page outside Claude.")
    return 0


def cmd_status(args):
    s = read_json(os.path.join(STATE, "status.json"), {}) or {}
    print(f"Last check: {s.get('last_checked', 'never')}. Seen IDs: {len(read_seen())}. "
          f"Signals kept: {len(glob.glob(os.path.join(STATE, 'signals', '*.json')))}. "
          f"Project cards: {len(glob.glob(os.path.join(STATE, 'projects', '*.json')))}. "
          f"Last run: {s.get('last_run_new_for_k2', 0)} new of {s.get('last_run_found', 0)} found. "
          f"Live page: {PAGE_URL}")
    return 0


def cmd_import_sheet(args):
    with open(args.file, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if rows and rows[0][:3] == SHEET_HEADER[:3]:
        rows = rows[1:]
    rows = [r + [""] * (13 - len(r)) for r in rows if len(r) >= 12 and r[11].strip()]
    path = os.path.join(STATE, "k2-watch.csv")
    if os.path.exists(path):
        os.remove(path)
    append_csv(rows)
    for r in rows:
        kv = str(r[5]).lstrip("'")
        rec = {"id": r[11], "found": r[0], "importance": r[1], "what_happened": r[2], "project": r[3],
               "utility": r[4], "kv": kv, "voltage_kv": kv, "where": r[6], "stage": r[7], "why_k2": r[8],
               "next_step": r[9], "url": r[10], "status": r[12] or "New", "title": r[2]}
        write_json(os.path.join(STATE, "signals", doc_id(r[11]) + ".json"), rec)
    added = add_seen([r[11] for r in rows])
    print(f"Imported {len(rows)} rows into state/k2-watch.csv and state/signals/ ({len(added)} IDs were new to seen.txt).")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="check every source for new signals")
    w.add_argument("--quiet", action="store_true", help="print nothing when nothing is new")
    w.add_argument("--puct-days", type=int, default=14)
    t = sub.add_parser("texas", help="refresh the Texas lines list if a source changed")
    t.add_argument("--force", action="store_true", help="rebuild even if no source changed")
    sub.add_parser("export-page", help="write web/data/line-watch-state.json for static hosting")
    sub.add_parser("status", help="print a one-paragraph status")
    i = sub.add_parser("import-sheet", help="rebuild local signals from a CSV of the K2 Watch tab")
    i.add_argument("file")
    args = p.parse_args(argv)
    return {"watch": cmd_watch, "texas": cmd_texas, "export-page": cmd_export_page,
            "status": cmd_status, "import-sheet": cmd_import_sheet}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
