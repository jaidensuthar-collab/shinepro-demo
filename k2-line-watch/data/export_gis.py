"""Export the K2 Line Watch projects as GIS files for the GIS team.

  python3 export_gis.py            # writes ../web/exports/

Files (all WGS84 lon/lat, EPSG:4326):
  k2-substations.geojson / .csv   end substation pins, with how each was placed
  k2-study-areas.geojson          one feature per project: the counties it could cross
  k2-straight-lines.geojson       straight lines between end substations (NOT routes)
  k2-projects.csv                 one row per project: stage, window, case numbers, links
  k2-line-watch.kml               everything above for Google Earth
County outlines are simplified (about 1 km); use official boundaries for parcel work.
"""
import csv
import json
import os
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "web", "exports")
PROPS = ("id", "name", "kv", "utility", "stage", "stage_label", "window", "importance", "status", "docket", "rpg", "region")


README = """K2 Line Watch GIS export
All files are WGS84 longitude/latitude (EPSG:4326).

{n} projects, {s} end substation pins.

k2-substations.geojson / k2-substations.csv
  End substation pins. location_quality says how exact each pin is:
  exact = matches a mapped substation or a street-level description;
  approx = placed from a distance-and-direction description (usually within 1-2 miles);
  town / county = only the nearest town or county is known.
  how_placed and source explain each pin.
k2-study-areas.geojson
  One feature per project: the counties the line could cross (study area or route counties
  from the PUC application where published, otherwise the end substations' counties).
  County outlines are simplified (about 1 km). Use official boundaries for parcel work.
k2-straight-lines.geojson
  Straight lines between end substations. These are NOT routes; they only show which
  substations a project connects.
k2-projects.csv
  One row per project: stage (2 ERCOT review ... 7 construction), window (Open now /
  Act fast / Late), case numbers, next step and source links.
k2-line-watch.kml
  Everything above for Google Earth.
k2-texas-layer.geojson / k2-texas-layer.kml  (start here)
  One GIS layer with every Texas line and every end substation, all fields on each feature.
  feature_type = line: one per new or upgraded ERCOT line (138 kV and up) or new 345 kV+
  substation project, built in the last 3 years or due in service within the next 5. stage is one of built (in service in the last 3 years), in construction,
  approved (route final or existing corridor, waiting to build), planned (approved, route or site
  not final) or proposed (not approved yet); stage_detail says why. builder is the utility.
  tappable: yes (345 kV and below), maybe (500 kV), no (765 kV, substations only).
  from_status / to_status and location_quality per end. Lines are straight between the end
  substations, NOT routes; a line with only one placeable end is a point at that end.
  feature_type = substation: one per end substation. status is new, existing, expanding
  (there today and a new line, substation work or transformer is coming), existing, or
  unconfirmed (not on public maps by this name). status_reason says why. location_quality:
  exact / approx (within a mile or two) / county (placed at the county center because the
  substation is not on public maps by name). Developers already queued there are included.
  The KML has the same features in folders by stage and by substation status.
k2-texas-lines.csv / k2-texas-substations.csv
  The same two tables without geometry (substations keep lat/lon).
k2-texas-lines.geojson
  The line features only.
k2-texas-developers.csv
  One row per generation or battery project in ERCOT's interconnection queue at a catalog end
  substation: developer as filed with ERCOT (often a project company), project, fuel, MW, expected
  online date, study stage, whether the interconnection agreement is signed, and the lines there.
k2-irp-pilot.csv
  IRP pilot: one row per utility (load growth, data-center load, new generation,
  retirements, transmission, active procurement, plan link). Not map data.
routes/<docket>.geojson
  Route option links for active PUC cases, one file per docket, from the utilities' public
  ArcGIS services and the KMZ files in PUC filings. Each link has the filed routes that use it
  (route_ids) and whether it is on the utility's recommended route. Files marked
  "preliminary" are open-house draft links, not the filed set. routes/summary.json gives
  the source and notes for each docket. Bakersfield to White Baker (59908) filed one route
  only, so it has no alternatives here.

Live version: https://claude.ai/artifact/FCARNQ1KQBr5r5DX9V6XfG
"""


def load():
    projects = json.load(open(os.path.join(HERE, "projects.json"), encoding="utf-8"))
    counties = json.load(open(os.path.join(HERE, "..", "web", "counties.json"), encoding="utf-8"))
    return projects, counties


def segments(p, ends):
    segs = p["geo"].get("segments")
    if segs is None:
        segs = [[0, 1]] if len(ends) == 2 else []
    return [[ends[i] for i in s if i < len(ends)] for s in segs]


def build(projects, counties):
    subs, areas, lines, rows, sub_rows = [], [], [], [], []
    for p in projects:
        base = {k: p.get(k, "") for k in PROPS}
        base["links"] = " | ".join(l["url"] for l in p.get("links", []))
        rows.append(base | {"endpoints": p.get("endpoints", ""), "counties": p.get("counties", ""),
                            "next_step": p.get("next_step", ""), "k2_action": p.get("k2_action", ""),
                            "checked": p.get("checked", ""), "updated": p.get("updated", "")})
        g = p.get("geo")
        if not g:
            continue
        ends = g["endpoints"]
        for e in ends:
            props = {"project_id": p["id"], "project": p["name"], "kv": p["kv"], "stage": p["stage"], "window": p["window"],
                     "substation": e["name"], "county": (e.get("county") or "").replace("|", ": "),
                     "location_quality": e.get("confidence"), "how_placed": e.get("basis"), "source": e.get("source")}
            subs.append({"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]}})
            sub_rows.append(props | {"lat": e["lat"], "lon": e["lon"]})
        polys = [[ring] for key in g["counties"] for ring in counties.get(key, [])]
        if polys:
            areas.append({"type": "Feature", "properties": base | {"counties": ", ".join(k.replace("|", ": ") for k in g["counties"]),
                                                                    "counties_basis": g.get("counties_basis", "")},
                          "geometry": {"type": "MultiPolygon", "coordinates": polys}})
        for seg in segments(p, ends):
            if len(seg) > 1:
                lines.append({"type": "Feature", "properties": base | {"note": "Straight line between end substations, NOT the route"},
                              "geometry": {"type": "LineString", "coordinates": [[e["lon"], e["lat"]] for e in seg]}})
    return subs, areas, lines, rows, sub_rows


def kml(subs, areas, lines):
    def placemark(f, style):
        pr, g = f["properties"], f["geometry"]
        name = pr.get("substation") or pr.get("name")
        desc = "<br>".join("%s: %s" % (escape(str(k)), escape(str(v))) for k, v in pr.items() if v not in ("", None))
        if g["type"] == "Point":
            geom = "<Point><coordinates>%s,%s</coordinates></Point>" % tuple(g["coordinates"])
        elif g["type"] == "LineString":
            geom = "<LineString><coordinates>%s</coordinates></LineString>" % " ".join("%s,%s" % tuple(c) for c in g["coordinates"])
        else:
            geom = "<MultiGeometry>%s</MultiGeometry>" % "".join(
                "<Polygon><outerBoundaryIs><LinearRing><coordinates>%s</coordinates></LinearRing></outerBoundaryIs></Polygon>"
                % " ".join("%s,%s" % tuple(c) for c in poly[0]) for poly in g["coordinates"])
        return "<Placemark><name>%s</name><styleUrl>#%s</styleUrl><description><![CDATA[%s]]></description>%s</Placemark>" % (
            escape(str(name)), style, desc, geom)
    styles = ('<Style id="sub"><IconStyle><color>ff6b13c4</color><scale>1.1</scale></IconStyle></Style>'
              '<Style id="area"><LineStyle><color>ff6b13c4</color><width>1</width></LineStyle><PolyStyle><color>336b13c4</color></PolyStyle></Style>'
              '<Style id="line"><LineStyle><color>ff1b211d</color><width>2</width></LineStyle></Style>')
    folders = [("End substations", subs, "sub"), ("Study-area counties", areas, "area"), ("Straight lines (not routes)", lines, "line")]
    body = "".join("<Folder><name>%s</name>%s</Folder>" % (n, "".join(placemark(f, s) for f in fs)) for n, fs, s in folders)
    return '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>K2 Line Watch</name>%s%s</Document></kml>' % (styles, body)


def irp_rows(irps):
    def total(items):
        vals = [x.get("mw") for x in items or [] if isinstance(x.get("mw"), (int, float))]
        return round(sum(vals)) if vals else ""
    out = []
    for u in irps:
        load, plan = u.get("load") or {}, u.get("irp") or {}
        out.append({"utility": u["utility"], "type": u.get("type", ""), "states": " ".join(u.get("states") or []), "grid": u.get("rto", ""),
                    "plan": plan.get("title", ""), "filed": plan.get("filed", ""), "status": plan.get("status", ""),
                    "data_center_mw": load.get("data_center_mw") if load.get("data_center_mw") is not None else "",
                    "peak_growth_pct_per_year": load.get("peak_growth_pct_per_year") if load.get("peak_growth_pct_per_year") is not None else "",
                    "peak_mw_start": load.get("base_peak_mw") or "", "start_year": load.get("base_year") or "",
                    "peak_mw_end": load.get("end_peak_mw") or "", "end_year": load.get("end_year") or "",
                    "new_generation_mw": total(u.get("generation_adds")), "retirements_mw": total(u.get("retirements")),
                    "transmission_projects": "; ".join(t.get("name", "") for t in u.get("transmission") or []),
                    "buying_power_now": u.get("rfp_or_procurement", ""), "places_named": "; ".join(u.get("places_named") or []),
                    "headline": u.get("headline", ""), "plan_url": plan.get("url", ""),
                    "note": "ERCOT: context only, numbers are queue requests" if u.get("context") else ""})
    return out


def write_csv(path, rows):
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    projects, counties = load()
    subs, areas, lines, rows, sub_rows = build(projects, counties)
    os.makedirs(OUT, exist_ok=True)
    fc = lambda feats: {"type": "FeatureCollection", "crs_note": "WGS84 lon/lat (EPSG:4326)", "features": feats}
    for name, feats in (("k2-substations", subs), ("k2-study-areas", areas), ("k2-straight-lines", lines)):
        json.dump(fc(feats), open(os.path.join(OUT, name + ".geojson"), "w", encoding="utf-8"), separators=(",", ":"))
    write_csv(os.path.join(OUT, "k2-projects.csv"), rows)
    write_csv(os.path.join(OUT, "k2-substations.csv"), sub_rows)
    open(os.path.join(OUT, "k2-line-watch.kml"), "w", encoding="utf-8").write(kml(subs, areas, lines))
    irp_path = os.path.join(HERE, "irps.json")
    if os.path.exists(irp_path):
        write_csv(os.path.join(OUT, "k2-irp-pilot.csv"), irp_rows(json.load(open(irp_path, encoding="utf-8"))))
    readme = README.format(n=len(rows), s=len(subs))
    # The web page serves these and zips them in the browser (.kml and .zip are not served as-is).
    open(os.path.join(OUT, "README.txt"), "w", encoding="utf-8").write(readme)
    open(os.path.join(OUT, "k2-line-watch.kml.xml"), "w", encoding="utf-8").write(kml(subs, areas, lines))
    with zipfile.ZipFile(os.path.join(OUT, "k2-gis-export.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme)
        for name in sorted(os.listdir(OUT)):
            path = os.path.join(OUT, name)
            if os.path.isfile(path) and not name.endswith((".zip", ".kml.xml", "README.txt")):
                z.write(path, name)
        routes = os.path.join(OUT, "routes")
        if os.path.isdir(routes):
            for name in sorted(os.listdir(routes)):
                z.write(os.path.join(routes, name), "routes/" + name)
    print("%d projects, %d substations, %d study areas, %d straight lines -> %s" % (len(rows), len(subs), len(areas), len(lines), OUT))


if __name__ == "__main__":
    main()
