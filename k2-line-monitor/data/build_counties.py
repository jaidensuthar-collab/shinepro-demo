"""Build web/counties.json: simplified county outlines for the K2 Line Watch maps.

Source: the US Census 2010 county outlines as GeoJSON (plotly's copy):
  https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json

  python3 build_counties.py SOURCE.json ../web/counties.json

Output: {"TX|Schleicher": [[[lon, lat], ...]], ...}, one list of outer rings per county,
simplified to about 1 km and rounded to 3 decimals so the file stays small.
"""
import json
import sys

STATES = {"48": "TX", "51": "VA", "54": "WV", "24": "MD"}
TOLERANCE = 0.01  # degrees, about 1 km


def _dist(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5


def simplify(points, tol=TOLERANCE):
    """Douglas-Peucker line simplification."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0, None
        for k in range(i + 1, j):
            d = _dist(points[k], points[i], points[j])
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(points, keep) if k]


def main(src, dst):
    out = {}
    for f in json.load(open(src, encoding="latin-1"))["features"]:
        st = STATES.get(f["properties"]["STATE"])
        if not st:
            continue
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        rings = []
        for poly in polys:
            ring = simplify(poly[0])
            if len(ring) >= 4:
                rings.append([[round(x, 3), round(y, 3)] for x, y in ring])
        out["%s|%s" % (st, f["properties"]["NAME"])] = rings
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("%d counties written to %s" % (len(out), dst))


if __name__ == "__main__":
    main(*sys.argv[1:3])
