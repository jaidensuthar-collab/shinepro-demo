"""Turn one Tier 3 run into the K2 group page, a private page for Jaiden, and a 'what's new' summary.

    python3 report/build_report.py <run_dir> [--update-seen]

<run_dir> holds run-record.json and the lead CSV the workflow wrote (see run_headless.sh).
Writes into <run_dir>:
  line-watch-to-call-list.html   shareable page (owners as type + initials, no street addresses)
  private-step-by-step.html      the same steps with real names and addresses (never publish)
  summary.json                   counts and what is new, for the run reply
With --update-seen it also updates data/seen-owners.txt and data/last-run.json, which hold
only one-way fingerprints and counts (no names), so they are safe in the public repo.
"""
import collections
import glob
import hashlib
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SEEN = os.path.join(DATA, "seen-owners.txt")
LAST = os.path.join(DATA, "last-run.json")
GIS = os.path.join(DATA, "gis-check.json")
REPO = "https://github.com/jaidensuthar-collab/shinepro-demo/tree/claude/vibrant-euler-urtmp2/k2-tier3"
WF = "https://github.com/jaidensuthar-collab/shinepro-demo/blob/claude/vibrant-euler-urtmp2/k2-tier3/workflows/line-watch-to-call-list.json"
FCC = "https://docs.fcc.gov/public/attachments/FCC-24-17A1.pdf"
e = lambda x: html.escape(str(x))
n = lambda x: f"{x:,}"

TYPE = {"Business": "Company", "Person": "Individual", "Trust": "Family trust", "Estate": "Estate", "Public or utility": "Public"}
STOP = {"ETAL", "ET", "AL", "JR", "SR", "II", "III", "THE", "OF", "AND"}


def short(name):
    return re.sub(r"\s*\(.*?\)", "", name or "")


def owner_key(r):
    return hashlib.sha1(f"{r['owner_name']}|{r['mail_zip']}".encode()).hexdigest()[:16]


def phone(num):
    return f"({num[:3]}) {num[3:6]}-{num[6:]}" if num and len(num) == 10 else ""


def table(cols, rows, num=()):
    th = "".join(f'<th class="{"num" if c in num else ""}">{e(c)}</th>' for c in cols)
    if not rows:
        return f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody><tr><td colspan="{len(cols)}" class="empty">None in this run.</td></tr></tbody></table></div>'
    trs = "".join("<tr>" + "".join(f'<td class="{"num" if c in num else ""}">{v}</td>' for c, v in zip(cols, r)) + "</tr>" for r in rows)
    return f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


class Run:
    def __init__(self, run_dir):
        rec = json.load(open(os.path.join(run_dir, "run-record.json")))
        rec = rec[0] if isinstance(rec, list) else rec
        self.st = rec["settings"]
        self.subs = rec["substations"]
        self.total_subs = rec["substations_in_line_watch"]
        self.tile_count = rec["tiles"]
        self.first_tiles = rec["first_tiles"]
        self.per_sub = rec["parcel_records_per_substation"]
        self.failed = rec["failed_first_try"]
        self.stats = rec["stats"]
        self.scored_count = rec["scored_count"]
        self.final = rec["leads"]
        self.land = [r for r in self.final if r["category"] == "landowner"]
        self.phones = rec["phones"]
        self.mode = self.st.get("phoneLookup", "off")
        timing = os.path.join(run_dir, "timing.json")
        self.secs = json.load(open(timing))["seconds"] if os.path.exists(timing) else 0


class View:
    """Renders names either as-is (private) or as type + initials (shareable)."""
    def __init__(self, mask):
        self.mask = mask

    def who(self, name, typ=None):
        if not self.mask:
            return e(name)
        parts = [x for x in re.split(r"[^A-Z0-9]+", str(name).upper()) if x and x not in STOP]
        ini = ".".join(x[0] for x in parts[:3]) + "." if parts else ""
        return f'{e(TYPE.get(typ, "Owner"))} <span class="ini">{e(ini)}</span>'

    def mail(self, r):
        city = f"{e(r['mail_city'])}, {e(r['mail_state'])}"
        if self.mask:
            return city
        street = " ".join(x for x in [r["mail_line1"], r["mail_line2"]] if x)
        return f"{e(street)}<br>{city} {e(r['mail_zip'])}"


def phone_cell(ps):
    if not ps:
        return '<span class="muted-in">no match</span>'
    bits = []
    for p in ps:
        flag = ('<span class="chip warn">Do Not Call</span>' if p["dnc"] else
                '<span class="chip warn">TCPA litigator</span>' if p["litigator"] else '<span class="chip ok">clean</span>')
        bits.append(f'<span class="tel">{phone(p["number"])}</span> {e(p["type"])} {flag}')
    return "<br>".join(bits)


def steps_html(run, v):
    st, subs = run.st, run.subs
    out = []

    def step(i, title, node, count, what, body):
        out.append(f"""<section class="stage"><div class="head"><span class="no">{i}</span><div><h3>{e(title)}</h3>
<div class="meta"><span>n8n node: <b>{e(node)}</b></span><span class="out">{count}</span></div></div></div>{f'<p>{what}</p>' if what else ''}{body}</section>""")

    rows = [(e(k), f"<code>{e(val)}</code>") for k, val in st.items() if k not in ("substationsUrl", "outputFolder", "runDate", "consentedParcelIds")]
    step(1, "Settings", "Settings", "1 item", "The knobs for this run.", table(["Setting", "Value"], rows))

    rows = [(f"<b>{e(short(s['name']))}</b>", e(s["county"]), e(s["bestProject"]), e(s["bestStageLabel"]), e(s["bestWindow"]),
             '<span class="chip ok">exact</span>' if s["confidence"] == "exact" else '<span class="chip warn">approx</span>')
            for s in subs]
    step(2, "Pick substations", "Get Line Watch substations, Pick substations", f"{run.total_subs} in, {len(subs)} out",
         f"Read {run.total_subs} substations from Line Watch and kept Texas ones with a usable location, High projects and early timing first.",
         table(["Substation", "County", "Project", "Stage", "Timing", "Location"], rows))

    rows = [(e(short(subs[0]["name"])), e(t["tile"]), f"<code>{e(t['envelope'])}</code>") for t in run.first_tiles]
    step(3, "Make map tiles", "Make map tiles", f"{n(run.tile_count)} tiles",
         f"Each substation gets a 4 x 4 mile square cut into 16 one-mile tiles. First 4 for {e(short(subs[0]['name'])) if subs else ''}:",
         table(["Substation", "Tile", "Box (west, south, east, north)"], rows))

    per = collections.Counter(run.per_sub)
    rows = [(e(short(s["name"])), n(per[s["id"]])) for s in subs]
    step(4, "Look up parcels", "Look up parcels (Texas parcel layer)", f"{n(sum(per.values()))} parcel records",
         f"Every tile asks the Texas statewide parcel layer for its parcels. {run.failed} of {n(run.tile_count)} tiles failed the first time"
         f"{(' and got a second try; ' + str(run.stats.get('tileErrors', 0)) + ' still failed after it') if run.failed else ''}. A parcel that crosses two tiles counts twice here; the next step removes duplicates and anything over {st.get('radiusMiles', 2)} miles away.",
         table(["Substation", "Parcel records"], rows, num=("Parcel records",)))

    s = run.stats
    rows = [(f"<b>{r['lead_score']}</b>", v.who(r["owner_name"], r["owner_type"]), e(r["owner_type"]), f"{r['total_acres']:,.0f}",
             f"{r['miles_to_substation']:.2f}", e(short(r["substation"].split(";")[0]))) for r in sorted(run.land, key=lambda r: -r["lead_score"])[:15]]
    step(5, "Score parcels and owners", "Score parcels and owners", f"{n(run.scored_count)} owners",
         f"{n(s.get('parcelsInRadius', 0))} unique parcels within {st.get('radiusMiles', 2)} miles, grouped by owner. "
         f"{n(s.get('ownersBelowMinAcres', 0))} owners under {st.get('minAcres', 20)} acres dropped, leaving {s.get('landowners', 0)} landowners and {s.get('skipped', 0)} set aside. Top 15:",
         table(["Score", "Owner", "Type", "Acres", "Miles", "Substation"], rows, num=("Score", "Acres", "Miles")))

    if run.mode == "off":
        step(6, "Find phone numbers", "Phone lookup on?", "off", "Phone lookup was off for this run, so every landowner goes to the letter list.", "")
    else:
        found = sum(1 for p in run.phones if p.get("phones"))
        rows = [(v.who(p["owner_name"], p["owner_type"]), phone_cell(p.get("phones"))) for p in run.phones[:12]]
        note = {"demo": "<b>Every number here is made up</b> (555-0100 to 555-0199). Real numbers need a Tracerfy key.",
                "sandbox": "<b>These numbers are fake</b> (Tracerfy test server).", "live": "Real numbers from Tracerfy."}[run.mode]
        step(6, f"Find phone numbers ({run.mode})", "Phone lookup", f"{len(run.phones)} looked up, {found} with a number",
             f"Only landowners are looked up. {note}", table(["Owner", "Phones found"], rows))

    cnt = collections.Counter(r["list"] for r in run.final)
    lane = lambda k: [r for r in run.final if r["list"] == k]
    wrows = [(v.who(r["owner_name"], r["owner_type"]), f'<span class="tel">{phone(r["best_phone"])}</span>' if r["best_phone"] else '<span class="muted-in">number comes with their reply</span>',
              f"{r['total_acres']:,.0f}", e(short(r["substation"].split(';')[0]))) for r in lane("wendy")]
    srows = [(f"<b>{r['lead_score']}</b>", v.who(r["owner_name"], r["owner_type"]), f'<span class="tel">{phone(r["best_phone"])}</span> {e(r["best_phone_type"])}',
              f"{r['total_acres']:,.0f}", f"{r['miles_to_substation']:.2f}", e(short(r["substation"].split(';')[0]))) for r in lane("sales-call")[:25]]
    mrows = [(f"<b>{r['lead_score']}</b>", v.who(r["owner_name"], r["owner_type"]), v.mail(r), f"{r['total_acres']:,.0f}",
              e("all numbers blocked" if int(r.get("phones_blocked") or 0) else "no number found" if run.mode != "off" else "phone lookup off"))
             for r in lane("mail-first")[:12]]
    aside = lane("skip: energy-company") + lane("skip: public-or-utility")
    krows = [(e(r["owner_name"]), e(r["list"].replace("skip: ", "")), f"{r['total_acres']:,.0f}", e(short(r["substation"].split(';')[0]))) for r in aside[:10]]
    body = f"""<div class="lanes4">
<div class="lane wendy"><b>{cnt['wendy']}</b> Wendy</div><div class="lane"><b>{cnt['sales-call']}</b> Salesperson call</div>
<div class="lane"><b>{cnt['mail-first']}</b> Letter first</div><div class="lane"><b>{len(aside)}</b> Set aside</div></div>
<h4>Wendy (owners who opted in)</h4>{table(["Owner", "Phone", "Acres", "Substation"], wrows, num=("Acres",))}
<h4>Salesperson calls: top {min(25, cnt['sales-call'])} of {cnt['sales-call']}</h4>{table(["Score", "Owner", "Number to call", "Acres", "Miles", "Substation"], srows, num=("Score", "Acres", "Miles"))}
<h4>Letter first: top {min(12, cnt['mail-first'])} of {cnt['mail-first']}</h4>{table(["Score", "Owner", "Mailing address", "Acres", "Why no call"], mrows, num=("Score", "Acres"))}
<h4>Set aside: {len(aside)}</h4>{table(["Owner", "Reason", "Acres", "Substation"], krows, num=("Acres",))}"""
    step(7, "Pick next step", "Join leads, Pick next step", f"{len(run.final)} leads in 4 lanes",
         "Wendy only gets owners who opted in; clean numbers go to a salesperson who dials by hand; everyone else gets a letter first.", body)

    step(8, "Save the CSV", "Make CSV, Save CSV", "1 file",
         f"All {len(run.final)} rows, with parcel IDs and market value, saved as <code>k2-tier3-leads-{e(st.get('runDate', ''))}.csv</code>. The Send to Wendy node stays off until Deepak's format.", "")
    return "".join(out)


def build(run_dir, update_seen):
    run = Run(run_dir)
    date = run.st.get("runDate", "")
    seen = set(open(SEEN).read().split()) if os.path.exists(SEEN) else set()
    last = json.load(open(LAST)) if os.path.exists(LAST) else None
    baseline = not seen
    new_land = [r for r in run.land if owner_key(r) not in seen]
    new_subs = [s for s in run.subs if last and s["id"] not in set(last.get("substations", []))]

    # Per-substation rollup and headline stats
    by_sub = collections.OrderedDict()
    for s in run.subs:
        by_sub[s["name"]] = {"s": s, "owners": 0, "acres": 0.0, "big": 0, "new": 0}
    new_keys = {owner_key(r) for r in new_land}
    for r in run.land:
        name = r["substation"].split("; ")[0]
        if name in by_sub:
            b = by_sub[name]
            b["owners"] += 1; b["acres"] += float(r["total_acres"]); b["big"] += float(r["total_acres"]) >= 200
            b["new"] += owner_key(r) in new_keys
    acres_total = sum(float(r["total_acres"]) for r in run.land)
    over200 = sum(float(r["total_acres"]) >= 200 for r in run.land)
    over640 = sum(float(r["total_acres"]) >= 640 for r in run.land)
    outstate = sum(r["mail_state"] not in ("TX", "") for r in run.land)
    approx_n = sum(s["confidence"] != "exact" for s in run.subs)
    energy = [r for r in run.final if r["category"] == "energy-company"]
    energy_subs = {short(r["substation"].split("; ")[0]) for r in energy}

    summary = {"date": date, "substations": len(run.subs), "substations_in_line_watch": run.total_subs,
               "new_substations": [short(s["name"]) for s in new_subs], "landowners": len(run.land),
               "new_landowners": 0 if baseline else len(new_land), "baseline": baseline,
               "acres": round(acres_total), "failed_tiles_first_try": run.failed, "failed_tiles_after_retry": run.stats.get("tileErrors", 0), "phone_mode": run.mode,
               "lanes": dict(collections.Counter(r["list"] for r in run.final)),
               "biggest_new": [] if baseline else [f"{r['total_acres']:,.0f} ac near {short(r['substation'].split('; ')[0])}"
                                                    for r in sorted(new_land, key=lambda r: -float(r["total_acres"]))[:3]],
               "approx_substations": approx_n}

    gis_html = ""
    if os.path.exists(GIS):
        g = json.load(open(GIS))
        res = g["results"]
        cnt = collections.Counter(r["result"] for r in res)
        chip = {"confirmed": "ok", "likely": "off", "not on map": "warn"}
        label = {"confirmed": "Confirmed", "likely": "Likely", "not on map": "Not on map yet"}
        order = {"confirmed": 0, "likely": 1, "not on map": 2}
        rows = [(f'<span class="sub">{e(short(r["name"]))}</span>', f'<span class="chip {chip[r["result"]]}">{label[r["result"]]}</span>', e(r["note"]))
                for r in sorted(res, key=lambda r: (order[r["result"]], r["name"]))]
        gis_html = f"""<section aria-labelledby="gis">
  <div class="eyebrow">GIS check &middot; {e(g['date'])}</div>
  <h2 id="gis">Checking the approximate substation points</h2>
  <p>Each of the {len(res)} substation points that started out approximate was checked against the national substation map (<a href="{e(g['source_url'])}">HIFLD Electric Substations</a>), matching by name within 15 miles. Confirmed points now use the map's location.</p>
  <div class="newstats"><div><b>{cnt['confirmed']}</b>confirmed and corrected</div><div><b>{cnt['likely']}</b>likely match</div><div><b>{cnt['not on map']}</b>not on the map yet</div></div>
  {table(["Substation", "Result", "What was found"], rows)}
  <p class="muted">The ones not on the map are new or proposed, so no public point exists yet. Their locations come from utility filings and maps, and still need a check by the GIS team.</p>
</section>"""

    def page(v):
        sub_rows = "".join(f"""<tr><td><span class="sub">{e(short(name))}</span><span class="muted">{e(b['s']['county'])} County</span></td>
<td>{e(b['s']['bestProject'])}<span class="muted">{e(b['s']['bestStageLabel'])}</span></td>
<td class="num">{b['owners']}</td><td class="num">{n(round(b['acres']))}</td><td class="num">{b['big']}</td>
<td class="num">{'' if baseline else b['new']}</td>
<td><span class="chip {'ok' if b['s']['confidence'] == 'exact' else 'warn'}">{'Confirmed' if b['s']['confidence'] == 'exact' else 'GIS to confirm'}</span></td></tr>"""
                           for name, b in sorted(by_sub.items(), key=lambda kv: -kv[1]["owners"]))
        top = sorted(run.land, key=lambda r: -r["lead_score"])[:10]
        lead_rows = ""
        for r in top:
            a = min(float(r["total_acres"]), 640) / 640 * 35
            c = max(0, 1 - float(r["miles_to_substation"]) / float(run.st.get("radiusMiles", 2))) * 30
            imp = 15 if r["project_importance"] == "High" else 8
            tim = {"Open now": 15, "Act fast": 10}.get(r["timing"], 3)
            pen = "approximate" in r["location_check"]
            seg = lambda cls, val: f'<i class="{cls}" style="width:{val:.1f}%"></i>'
            lead_rows += f"""<tr><td class="num score">{r['lead_score']}</td>
<td><div class="bar" role="img" aria-label="Acres {a:.0f}, closeness {c:.0f}, importance {imp}, timing {tim}">{seg('s-acres', a)}{seg('s-close', c)}{seg('s-imp', imp)}{seg('s-time', tim)}</div>{'<span class="pen">&minus;5</span>' if pen else ''}</td>
<td>{v.who(r['owner_name'], r['owner_type'])}</td><td class="num">{n(round(float(r['total_acres'])))}</td><td class="num">{float(r['miles_to_substation']):.2f}</td>
<td>{e(short(r['substation'].split('; ')[0]))}<span class="muted">{e(r['county'].title())} County</span></td></tr>"""
        if baseline:
            news = f"""<p>This is the first full run, so it sets the baseline: {len(run.land)} landowners near {len(run.subs)} substations. Starting next week this section lists only owners and substations that were not here before.</p>"""
        else:
            nl = sorted(new_land, key=lambda r: -r["lead_score"])[:15]
            rows = [(f"<b>{r['lead_score']}</b>", v.who(r["owner_name"], r["owner_type"]), f"{float(r['total_acres']):,.0f}",
                     f"{float(r['miles_to_substation']):.2f}", e(short(r["substation"].split('; ')[0])), e(r["project"])) for r in nl]
            subs_txt = (", ".join(e(short(s["name"])) for s in new_subs)) if new_subs else "none"
            news = f"""<div class="newstats"><div><b>{len(new_subs)}</b>new substations</div><div><b>{len(new_land)}</b>new landowners</div>
<div><b>{n(round(sum(float(r['total_acres']) for r in new_land)))}</b>new acres</div></div>
<p>New substations from Line Watch: {subs_txt}.</p>
{table(["Score", "Owner", "Acres", "Miles", "Substation", "Project"], rows, num=("Score", "Acres", "Miles"))}"""
        energy_html = "".join(f"<li>{e(r['owner_name'].title().replace(' Llc', ' LLC').replace(' Lp', ' LP').replace('Db ', 'DB '))} ({e(short(r['substation'].split('; ')[0]))})</li>" for r in energy)
        demo_note = {"demo": "Phone numbers on this page are made up (demo mode).", "off": "Phone lookup was off for this run.",
                     "sandbox": "Phone numbers are fake (Tracerfy test server).", "live": "Phone numbers are real (Tracerfy)."}[run.mode]
        private = "" if v.mask else '<p class="banner"><b>Private, for Jaiden.</b> Real owner names and addresses from public appraisal records. Do not forward; the shareable page hides them.</p>'
        return f"""<title>Line Watch to Call List</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
  <div class="eyebrow">K2 Tier 3 &middot; updated every Monday &middot; last run {e(date)}</div>
  <h1>Line Watch to Call List</h1>
  <p class="lede">An n8n workflow that starts from the substations K2 Line Watch tracks, finds the land within {e(run.st.get('radiusMiles', 2))} miles of each one, and turns it into a scored list of landowners with a next step for each. It reruns every week to pick up new substations and new land. <a href="#bystep">See what each step produced</a>.</p>
  <div class="status"><span class="chip ok">Runs weekly</span><span class="chip off">{e(demo_note)}</span><span class="chip off">Wendy hand-off built, switched off</span></div>
  {private}
</header>

<section aria-labelledby="new">
  <div class="eyebrow">Since the last run</div>
  <h2 id="new">What is new</h2>
  {news}
</section>

<section aria-labelledby="flow">
  <div class="eyebrow">How it works &middot; this run</div>
  <h2 id="flow">From substation to landowner</h2>
  <div class="pipe">
    <div class="step"><div class="dot">1</div><div class="big">{len(run.subs)}</div><h3>Substations</h3><p>Texas substations from the Line Watch project cards ({run.total_subs} cards' worth in total).</p></div>
    <div class="step"><div class="dot">2</div><div class="big">{n(run.tile_count)}</div><h3>Map tiles</h3><p>Each 4 x 4 mile square cut into 1-mile tiles so busy areas are not cut off.</p></div>
    <div class="step"><div class="dot">3</div><div class="big">{n(run.stats.get('parcelsInRadius', 0))}</div><h3>Parcels within {e(run.st.get('radiusMiles', 2))} mi</h3><p>Texas statewide parcel layer: owner, mailing address, acres. Free and public.</p></div>
    <div class="step"><div class="dot">4</div><div class="big">{n(len(run.land))}</div><h3>Landowners, {e(run.st.get('minAcres', 20))}+ acres</h3><p>Parcels grouped by owner. City, utility and railroad land set aside.</p></div>
    <div class="step"><div class="dot">5</div><div class="big">0&ndash;100</div><h3>Lead score</h3><p>Acres, closeness, project importance and timing.</p></div>
    <div class="step"><div class="dot">6</div><div class="big">3</div><h3>Next-step lists</h3><p>Letter, salesperson call, or Wendy call for owners who opted in.</p></div>
  </div>
  <p>{f"The run took about {round(run.secs / 60, 1)} minutes. " if run.secs else ""}The {n(len(run.land))} owners hold {n(round(acres_total))} acres; {over200} own 200 acres or more and {over640} own a full section (640 acres) or more. {outstate} have a mailing address outside Texas, which usually means absentee owners.</p>
</section>

<section aria-labelledby="subs">
  <div class="eyebrow">Where the land is</div>
  <h2 id="subs">The {len(run.subs)} substations in this run</h2>
  <div class="table"><table>
    <thead><tr><th>Substation</th><th>Line Watch project</th><th class="num">Owners</th><th class="num">Acres</th><th class="num">200+ ac</th><th class="num">New</th><th>Location</th></tr></thead>
    <tbody>{sub_rows}</tbody></table></div>
  <p class="muted">Acres count whole parcels that reach within the radius. {approx_n} of these {len(run.subs)} substation points are approximate, so their results need a GIS check before anyone calls.</p>
</section>

{gis_html}

<section aria-labelledby="leads">
  <div class="eyebrow">What a lead looks like</div>
  <h2 id="leads">Top 10 leads by score</h2>
  <div class="legend"><span style="--c: var(--olive)">Acres (up to 35)</span><span style="--c: var(--steel)">Closeness (up to 30)</span><span style="--c: var(--amber)">Project importance (8 or 15)</span><span style="--c: var(--teal)">Timing (3 to 15)</span></div>
  <div class="table"><table>
    <thead><tr><th class="num">Score</th><th>Score parts</th><th>Owner</th><th class="num">Acres</th><th class="num">Miles</th><th>Nearest substation</th></tr></thead>
    <tbody>{lead_rows}</tbody></table></div>
  <p class="muted">{'Owner names are hidden on this page; the CSV has full names, mailing addresses and parcel IDs.' if v.mask else 'Full names shown: private page.'}</p>
</section>

<section aria-labelledby="comp">
  <div class="split">
    <div class="callout"><div class="eyebrow">Competition signal</div>
      <h2 id="comp">Energy companies already own land at {len(energy_subs)} of the {len(run.subs)} substations</h2>
      <p>The workflow sets these owners aside instead of calling them. It also shows where developers are already buying near a new substation.</p></div>
    <ul class="plain">{energy_html or '<li>None this run.</li>'}</ul>
  </div>
</section>

<section aria-labelledby="wendy">
  <div class="eyebrow">Where Wendy fits</div>
  <h2 id="wendy">Three lanes for every lead</h2>
  <p>The FCC ruled in February 2024 that AI-generated voices count as an "artificial voice" under the TCPA, so an AI call to a home or cell phone needs the person's prior consent (<a href="{FCC}">FCC 24-17</a>). No cold lead goes straight to Wendy.</p>
  <div class="lanes">
    <div class="lane"><h3>Letter first</h3><div class="who">Landowners without a clean number</div><p>A letter introducing K2 that invites the owner to call or reply. A reply is the opt-in.</p></div>
    <div class="lane"><h3>Salesperson call</h3><div class="who">Numbers not on Do Not Call and not a known litigator</div><p>A K2 salesperson dials by hand. Real numbers need a Tracerfy key.</p></div>
    <div class="lane wendy"><h3>Wendy</h3><div class="who">Owners who opted in</div><p>Wendy qualifies interest and books the sales call. Waits on Wendy's input format.</p></div>
  </div>
  <p class="muted">This is how the prototype is set up, not legal advice. A lawyer should confirm the calling plan before any real calls.</p>
</section>

<section aria-labelledby="asks">
  <div class="eyebrow">What would help next</div>
  <h2 id="asks">Questions for the team</h2>
  <div class="asks">
    <div class="ask"><div class="to">Richard &amp; John</div><p>Are 2 miles and 20 acres the right starting filters? Which substations matter most?</p></div>
    <div class="ask"><div class="to">Deepak</div><p>What format does Wendy take for a call list, and how is consent recorded on your side?</p></div>
    <div class="ask"><div class="to">GIS team</div><p>Could someone check the {approx_n} approximate substation points? They are marked "GIS to confirm" above.</p></div>
    <div class="ask"><div class="to">Everyone</div><p>Is a letter the right first touch for landowners, and is a phone lookup service worth paying for at this stage?</p></div>
  </div>
</section>

<section aria-labelledby="bystep" class="bystep">
  <div class="eyebrow">Step by step &middot; run {e(date)}</div>
  <h2 id="bystep">What each step produced</h2>
  <p>{'Owners show as type and initials on this page. ' if v.mask else ''}{e(demo_note)}</p>
  {steps_html(run, v)}
</section>

<footer>
  <p>Workflow and setup steps on GitHub: <a href="{REPO}">k2-tier3 folder</a> &middot; <a href="{WF}">workflow file</a> (import into n8n 1.123 or later).</p>
  <p>Data: K2 Line Watch project cards; Texas Geographic Information Office StratMap land parcels (county appraisal districts). Built by Jaiden Suthar.</p>
</footer>
</div>
"""

    open(os.path.join(run_dir, "line-watch-to-call-list.html"), "w").write(page(View(mask=True)))
    open(os.path.join(run_dir, "private-step-by-step.html"), "w").write(
        "<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'></head><body>"
        + page(View(mask=False)).replace("<title>Line Watch to Call List</title>", "<title>Tier 3 Private Run</title>") + "</body></html>")
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=1)

    if update_seen:
        keys = sorted(seen | {owner_key(r) for r in run.land})
        open(SEEN, "w").write("\n".join(keys) + "\n")
        json.dump({"date": date, "substations": [s["id"] for s in run.subs], "landowners": len(run.land),
                   "acres": round(acres_total), "lanes": summary["lanes"]}, open(LAST, "w"), indent=1)
    print(json.dumps(summary, indent=1))


CSS = """
:root { --bg: #f5f7f6; --surface: #ffffff; --ink: #18262b; --muted: #5b6b70; --line: #d5dddc;
  --steel: #2c5f86; --olive: #6c7d2f; --amber: #b7791f; --teal: #2f8076;
  --ok: #2f7a4f; --ok-bg: #e3f1e8; --warn: #9a5b0c; --warn-bg: #fbeedb; --hl: #eaf1f6;
  --display: "Barlow Semi Condensed", "Arial Narrow", Arial, sans-serif;
  --body: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11191c; --surface: #172227; --ink: #e4ecec; --muted: #9aabae; --line: #2b3a3f;
  --steel: #7fb2d8; --olive: #a9bd63; --amber: #e0a854; --teal: #6cc1b4;
  --ok: #7fcf9c; --ok-bg: #1d3327; --warn: #f0b768; --warn-bg: #3a2a14; --hl: #1c2c35; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11191c; --surface: #172227; --ink: #e4ecec; --muted: #9aabae; --line: #2b3a3f;
  --steel: #7fb2d8; --olive: #a9bd63; --amber: #e0a854; --teal: #6cc1b4;
  --ok: #7fcf9c; --ok-bg: #1d3327; --warn: #f0b768; --warn-bg: #3a2a14; --hl: #1c2c35; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font: 15px/1.6 var(--body); }
.wrap { max-width: 1000px; margin: 0 auto; padding-block: 40px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; grid-template-columns: minmax(0, 1fr); gap: 44px; }
.wrap > *, section > *, .stage > * { min-width: 0; }
h1, h2, h3, h4 { font-family: var(--display); font-weight: 700; line-height: 1.1; text-wrap: balance; margin: 0; }
h1 { font-size: clamp(34px, 6vw, 52px); letter-spacing: -0.01em; }
h2 { font-size: 26px; } h3 { font-size: 18px; font-weight: 600; } h4 { font-size: 16px; font-weight: 600; margin-top: 6px; }
p { margin: 0; max-width: 68ch; }
a { color: var(--steel); } a:focus-visible { outline: 2px solid var(--steel); outline-offset: 2px; }
.eyebrow { font: 500 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.muted { display: block; color: var(--muted); font-size: 13px; }
.muted-in { color: var(--muted); font-size: 13px; }
section { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
header { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
.status .chip { white-space: normal; line-height: 1.3; }
.lede { font-size: 18px; max-width: 62ch; }
.status { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-block; font: 500 12px/1 var(--mono); padding: 6px 9px; border-radius: 4px; white-space: nowrap; }
td .chip { padding: 3px 6px; font-size: 11px; }
.chip.ok { background: var(--ok-bg); color: var(--ok); } .chip.warn { background: var(--warn-bg); color: var(--warn); }
.chip.off { background: var(--hl); color: var(--steel); }
.banner { background: var(--warn-bg); border-radius: 6px; padding: 12px 14px; font-size: 14px; }
.newstats { display: flex; flex-wrap: wrap; gap: 12px 36px; }
.newstats div { display: grid; font-size: 13px; color: var(--muted); }
.newstats b { font: 600 34px/1 var(--display); color: var(--ink); font-variant-numeric: tabular-nums; }
.pipe { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); position: relative; margin-top: 6px; }
.pipe::before { content: ""; position: absolute; left: 8%; right: 8%; top: 15px; height: 2px; background: var(--steel); opacity: .45; }
.step { position: relative; display: grid; gap: 6px; padding: 0 10px; justify-items: start; min-width: 0; }
.dot { width: 32px; height: 32px; border-radius: 50%; background: var(--bg); border: 2px solid var(--steel);
  display: grid; place-items: center; font: 600 13px/1 var(--mono); color: var(--steel); z-index: 1; }
.big { font: 600 30px/1 var(--display); font-variant-numeric: tabular-nums; margin-top: 8px; }
.step h3 { font-size: 15px; } .step p { font-size: 13px; color: var(--muted); }
@media (max-width: 760px) {
  .pipe { grid-template-columns: 1fr; gap: 18px; }
  .pipe::before { left: 15px; right: auto; top: 16px; bottom: 16px; width: 2px; height: auto; }
  .step { grid-template-columns: 32px 1fr; column-gap: 14px; padding: 0; }
  .step > :not(.dot) { grid-column: 2; } .step .dot { grid-row: 1 / span 4; } .big { margin-top: 0; } }
.table { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }
table { border-collapse: collapse; width: 100%; min-width: 640px; font-size: 14px; }
th { text-align: left; font: 500 11px/1.2 var(--mono); letter-spacing: .06em; text-transform: uppercase; color: var(--muted);
  padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: bottom; }
td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
td.empty { color: var(--muted); }
tr:last-child td { border-bottom: 0; }
.num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
th.num { text-align: right; }
.sub { font-weight: 600; } .score { font-weight: 500; font-size: 15px; }
.ini { font-family: var(--mono); color: var(--muted); font-size: 13px; }
.tel { font-family: var(--mono); white-space: nowrap; }
.bar { display: flex; width: 100%; min-width: 140px; height: 12px; border-radius: 2px; overflow: hidden; background: var(--line); }
.bar i { display: block; height: 100%; }
.s-acres { background: var(--olive); } .s-close { background: var(--steel); } .s-imp { background: var(--amber); } .s-time { background: var(--teal); }
.pen { font: 500 11px/1 var(--mono); color: var(--warn); margin-top: 4px; display: inline-block; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--muted); }
.legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; background: var(--c); }
.lanes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.lanes4 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.lane { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 16px; display: grid; gap: 8px; align-content: start; }
.lanes4 .lane { padding: 12px 14px; font-size: 14px; } .lanes4 .lane b { font: 600 28px/1 var(--display); display: block; }
.lane .who { font-size: 13px; color: var(--muted); }
.lane.wendy { border-color: var(--steel); background: var(--hl); }
@media (max-width: 760px) { .lanes { grid-template-columns: 1fr; } .lanes4 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.split { display: grid; grid-template-columns: 1.2fr 1fr; gap: 28px; align-items: start; }
@media (max-width: 760px) { .split { grid-template-columns: 1fr; } }
.split > * { min-width: 0; }
ul.plain { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
.callout { border-left: 3px solid var(--amber); padding: 4px 0 4px 14px; display: grid; gap: 8px; }
.asks { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 28px; }
.ask { display: grid; gap: 4px; align-content: start; }
.ask .to { font: 500 12px/1 var(--mono); letter-spacing: .06em; text-transform: uppercase; color: var(--steel); }
@media (max-width: 760px) { .asks { grid-template-columns: 1fr; } }
.stage { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; padding-top: 10px; border-top: 1px solid var(--line); }
.head { display: grid; grid-template-columns: 40px 1fr; gap: 14px; align-items: start; }
.no { width: 36px; height: 36px; border-radius: 50%; border: 2px solid var(--steel); color: var(--steel); display: grid; place-items: center; font: 600 15px/1 var(--mono); }
.meta { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--muted); margin-top: 6px; }
.meta .out { font: 600 13px/1.4 var(--mono); color: var(--ink); }
footer { font-size: 13px; color: var(--muted); border-top: 1px solid var(--line); padding-top: 16px; display: grid; gap: 6px; }
code { font: 13px var(--mono); background: var(--hl); padding: 1px 5px; border-radius: 3px; overflow-wrap: anywhere; }
"""

if __name__ == "__main__":
    build(sys.argv[1], "--update-seen" in sys.argv)
