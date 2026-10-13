K2 Line Watch GIS export
All files are WGS84 longitude/latitude (EPSG:4326).

37 projects, 80 end substation pins.

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
