K2 Line Watch GIS export
All files are WGS84 longitude/latitude (EPSG:4326).

39 projects, 84 end substation pins.

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
k2-all-new-only.geojson / .kml.xml  (and k2-<region>-new-only per region)
  The same layer with what is already there taken out: lines not yet built (every stage but
  built), substations not on HIFLD or OpenStreetMap within 0.2 mi, mapped substations being
  expanded (more power coming), and substations the source calls new whose location is too
  rough to check. new_only_reason says why each substation is in. The full layer below is the
  complete dataset; this is a filter of it.
k2-all-layer.geojson / k2-all-layer.kml  (start here)
  One GIS layer with every line and every end substation in every region (Texas ERCOT, Texas SPP,
  Texas El Paso, Texas MISO, Oklahoma SPP, MISO's 345 kV backbone), all fields on each feature. market (ERCOT,
  SPP, MISO, or WECC for El Paso Electric) and state (TX, OK, ..., or several for a line that crosses a
  state line) say where each feature is.
  Per region, the same layer split: k2-texas-layer (all of Texas), k2-ercot-texas-layer,
  k2-spp-texas-layer (Panhandle, South Plains, Northeast Texas), k2-el-paso-layer, k2-oklahoma-layer,
  k2-miso-texas-layer (Entergy Texas) and k2-miso-layer (all MISO lines).
  feature_type = line: one per new or upgraded line (138 kV and up) or new 345 kV+
  substation project, built in the last 3 years or due in service within the next 5. stage is one of built (in service in the last 3 years), in construction,
  approved (route final or existing corridor, waiting to build), planned (approved, route or site
  not final) or proposed (not approved yet); stage_detail says why. builder is the utility.
  tappable: yes (345 kV and below), maybe (500 kV), no (765 kV, substations only).
  from_status / to_status and location_quality per end. Lines are straight between the end
  substations, NOT routes; a line with only one placeable end is a point at that end.
  feature_type = substation: one per end substation. status is new, existing, expanding
  (there today and a new line, substation work or transformer is coming), existing, or
  unconfirmed (not on public maps by this name). status_reason says why. Substation stage:
  there_now (yes / no / unknown), work (building a new substation / adding to it / upgrading
  lines to it / no new work), work_stage (built ... proposed), work_in_service, work_project.
  on_public_map: yes if any substation (any name) on HIFLD or OpenStreetMap is within 0.2 mi,
  no if none is, can't tell if the point is only a town or county center.
  nearest_mapped / nearest_mapped_miles name the closest mapped substation.
  Line features carry the same per end: from_there_now, from_work, from_work_stage (and to_). location_quality:
  exact / approx (within a mile or two) / town (SPP only: the town the substation is named for) /
  county (placed at the county center because the substation is not on public maps by name).
  ERCOT developers already queued there are included.
  The KML has the same features in folders by stage and by substation status.
k2-all-lines.csv / k2-all-substations.csv (and k2-<region>-lines.csv / -substations.csv)
  The same two tables without geometry (substations keep lat/lon).
k2-all-lines.geojson / k2-texas-lines.geojson
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
