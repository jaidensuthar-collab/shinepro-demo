"""Build web/counties.json: simplified county outlines (every US county) for the K2 Line Watch maps.

Source: the US Census 2010 county outlines as GeoJSON (plotly's copy):
  https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json

  python3 build_counties.py SOURCE.json ../web/counties.json

Output: {"TX|Schleicher": [[[lon, lat], ...]], ...}, one list of outer rings per county,
simplified to about 1 km and rounded to 3 decimals so the file stays small.
"""
import json
import sys

# Every state plus DC (Census state FIPS -> postal code). Puerto Rico is left out.
STATES = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
          "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
          "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
          "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
          "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
          "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}
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
        key = "%s|%s" % (st, f["properties"]["NAME"])
        # A few independent cities share a county's name (VA|Richmond): the county keeps the plain key.
        if f["properties"].get("LSAD") == "city" and key in out:
            key += " (city)"
        elif key in out:
            out[key + " (city)"] = out[key]
        out[key] = rings
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("%d counties written to %s" % (len(out), dst))


if __name__ == "__main__":
    main(*sys.argv[1:3])
