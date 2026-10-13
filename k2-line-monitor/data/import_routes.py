"""Copy route-option links into web/exports/routes/, keeping only known fields.

  python3 import_routes.py SOURCE_DIR

SOURCE_DIR holds <docket>.geojson files (LineStrings in WGS84) and summary.json, made from
utility ArcGIS services and PUCT native-file KMZs. Anything that is not a LineString or
MultiLineString, or a property outside KEEP, is dropped.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "web", "exports", "routes")
KEEP = ("docket", "project", "link", "route_ids", "n_routes", "on_applicant_recommended_route", "kind", "stage",
        "service_layer", "source", "approved")


def clean_coords(c, depth):
    if depth == 0:
        lon, lat = float(c[0]), float(c[1])
        assert -180 <= lon <= 180 and -90 <= lat <= 90
        return [round(lon, 5), round(lat, 5)]
    return [clean_coords(x, depth - 1) for x in c]


def main(src):
    os.makedirs(OUT, exist_ok=True)
    index = []
    for name in sorted(os.listdir(src)):
        if not re.fullmatch(r"\d{5}\.geojson", name):
            continue
        data = json.load(open(os.path.join(src, name), encoding="utf-8"))
        feats = []
        for f in data.get("features", []):
            g = f.get("geometry") or {}
            if g.get("type") not in ("LineString", "MultiLineString"):
                continue
            depth = 1 if g["type"] == "LineString" else 2
            props = {k: v for k, v in (f.get("properties") or {}).items() if k in KEEP}
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": g["type"], "coordinates": clean_coords(g["coordinates"], depth)}})
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
        index.append({"docket": name[:5], "links": len(feats)})
    summary = json.load(open(os.path.join(src, "summary.json"), encoding="utf-8"))
    keep = ("docket", "project", "status", "features", "source", "notes")
    summary = [{k: str(s.get(k, "")) for k in keep} for s in summary]
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(index)


if __name__ == "__main__":
    main(sys.argv[1])
