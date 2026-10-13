"""Curated K2 project list for the K2 Line Watch database. Run: python3 build_projects.py > projects.json

Every project is a line (or substation) that adds grid capacity K2's partners could use.
'checked' = the facts were read from a primary source (utility, ERCOT or PUCT page) on the date given;
'needs checking' = taken from a project-list title or a secondary source, confirm before relying on it.
Stage numbers follow the Signal Ladder: 2 ERCOT review, 3 project page / open houses,
4 docket-number request, 5 route case at the PUC, 6 route approved, 7 land buying or construction.
"""
import json
import os

STAGE = {2: "ERCOT review", 3: "Open houses / project page", 4: "Docket requested", 5: "Route case at PUC",
         6: "Route approved", 7: "Land buying / construction"}
WINDOW = {2: "Open now", 3: "Open now", 4: "Act fast", 5: "Act fast", 6: "Late", 7: "Late"}

ERCOT_EB = "https://www.ercot.com/files/docs/2025/12/01/14.1-25RPG025-AEP-Texas-CPS-Energy-Oncor-and-CNP-Texas-765-kV-STEP-Eastern-Backbone-Project.pdf"
WHY_EB = ("Part of ERCOT's 765 kV Eastern Backbone, endorsed by the ERCOT Board in December 2025. The end substations "
          "are public but no route options are yet, which is K2's best window: land near both end substations is safe "
          "whichever route wins.")
DO_EB = "Map parcels within about 2 miles of both end substations and find the owners. Watch for open-house notices."


def p(id, name, kv, utility, stage, status, next_step, why, action, importance="High", miles="", endpoints="",
      counties="", docket="", rpg="", links=(), checked="needs checking", region="Texas (ERCOT)", window=None):
    return {"id": id, "name": name, "kv": kv, "utility": utility, "stage": stage, "stage_label": STAGE[stage],
            "window": window or WINDOW[stage], "importance": importance, "status": status, "next_step": next_step,
            "why_k2": why, "k2_action": action, "miles": miles, "endpoints": endpoints, "counties": counties,
            "docket": docket, "rpg": rpg, "region": region,
            "links": [{"label": l, "url": u} for l, u in links], "checked": checked, "updated": "2026-10-12"}


P = [
    p("hillje-blu-lacy", "Hillje to Blu Lacy", "765", "CenterPoint and AEP Texas", 3,
      "Open houses ran late July to August 1, 2026 in Wharton, Victoria, El Campo and nearby towns. Comments closed "
      "August 26. No route has been chosen.",
      "Route filing (CCN) expected early 2027; PUC decision expected fall 2027.",
      "First Eastern Backbone segment to show draft route links. The open-house map shows every segment the line could "
      "use; stretches most options share are the next-safest land after the end substations.",
      "Get the open-house route-link map (AEP virtual open house), mark shared segments, map parcels near Hillje and Blu Lacy.",
      miles="about 155", endpoints="Hillje substation (Wharton County) to Blu Lacy substation (near Nueces County)",
      counties="Wharton, Nueces and counties between (study area)", rpg="25RPG025 (Eastern Backbone)",
      links=[("AEP Texas project page", "https://aeptransmission.com/texas/hillje-blulacy/"),
             ("CenterPoint open-house boards", "https://www.centerpointenergy.com/en-us/Documents/Hillje-Blu-Lacy/Hillje-Blu-Lacy-Transmission-Improvement-Project-Open-House-Board.pdf"),
             ("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("blu-lacy-howard", "Blu Lacy to Howard", "765", "AEP Texas and CPS Energy", 3,
      "Open houses planned for August 25 to 27, 2026 are being rescheduled. No route has been chosen.",
      "New open-house dates, then route filing (CCN) early 2027; PUC decision expected fall 2027.",
      "Open houses have not happened yet, so almost nobody has seen draft routes. End substations are known.",
      "Watch AEP and CPS pages for the new open-house dates. Map parcels near Howard (Bexar) and Blu Lacy now.",
      miles="about 150", endpoints="Blu Lacy substation (near Nueces County) to Howard substation (Bexar County)",
      counties="Nueces area to Bexar (study area not yet published)", rpg="25RPG025 (Eastern Backbone)",
      links=[("AEP Texas project page", "https://aeptransmission.com/texas/blulacy-howard/"),
             ("CPS Energy project page", "https://www.cpsenergy.com/content/corporate/en/about-us/new-infrastructure/blulacy-howard.html"),
             ("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("dinosaur-watermill", "Dinosaur to Watermill", "765", "Eastern Backbone utilities (AEP Texas, CPS, Oncor, CenterPoint)", 2,
      "Endorsed by the ERCOT Board in December 2025 as part of the Eastern Backbone. No open houses found yet.",
      "Open houses, then a route filing. In service 2030 to 2032.", WHY_EB, DO_EB, miles="about 78",
      endpoints="Dinosaur substation to Watermill substation (Dallas County)", rpg="25RPG025",
      links=[("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("watermill-martin-lake", "Watermill to Martin Lake", "765", "Eastern Backbone utilities (AEP Texas, CPS, Oncor, CenterPoint)", 2,
      "Endorsed by the ERCOT Board in December 2025. No open houses found yet.",
      "Open houses, then a route filing. In service 2030 to 2032.", WHY_EB, DO_EB, miles="about 152",
      endpoints="Watermill (Dallas County) to Martin Lake (Rusk County)", rpg="25RPG025",
      links=[("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("martin-lake-hillje", "Martin Lake to Hillje", "765", "Eastern Backbone utilities (AEP Texas, CPS, Oncor, CenterPoint)", 2,
      "Endorsed by the ERCOT Board in December 2025. The longest Eastern Backbone segment. No open houses found yet.",
      "Open houses, then a route filing. In service 2030 to 2032.", WHY_EB, DO_EB, miles="about 293",
      endpoints="Martin Lake (Rusk County) to Hillje (Wharton County)", rpg="25RPG025",
      links=[("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("howard-bell-east", "Howard to Bell County East", "765", "Eastern Backbone utilities (AEP Texas, CPS, Oncor, CenterPoint)", 2,
      "Endorsed by the ERCOT Board in December 2025. No open houses found yet.",
      "Open houses, then a route filing. In service 2030 to 2032.", WHY_EB, DO_EB, miles="about 170",
      endpoints="Howard (Bexar County) to Bell County East (Bell County)", rpg="25RPG025",
      links=[("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("bell-east-watermill", "Bell County East to Watermill", "765", "Eastern Backbone utilities (AEP Texas, CPS, Oncor, CenterPoint)", 2,
      "Endorsed by the ERCOT Board in December 2025. No open houses found yet.",
      "Open houses, then a route filing. In service 2030 to 2032.", WHY_EB, DO_EB, miles="about 133",
      endpoints="Bell County East (Bell County) to Watermill (Dallas County)", rpg="25RPG025",
      links=[("ERCOT Board item 14.1", ERCOT_EB)], checked="checked 2026-10-09"),
    p("euclid-765", "Euclid 765 kV substation and line", "765", "LCRA TSC and CenterPoint", 2,
      "Tier 1 project endorsed by the ERCOT Board on June 1, 2026. ERCOT documents give a 2031 in-service target for a "
      "Euclid to Hillje segment.", "Route filings and open houses to come; details to confirm.",
      "A brand-new 765 kV hub plus line, endorsed but early. Endpoint land is the play.",
      "Find the Euclid substation location in the ERCOT documents and map nearby parcels.", rpg="26RPG001",
      links=[("ERCOT RPG April 2026 status update", "https://www.ercot.com/files/docs/2026/04/10/EIR-Euclid-765-kV-Substation-and-Transmission-Line-Addition-Status-Update-RPG-April_2026.pdf")]),
    p("bell-east-big-hill", "Bell County East to Big Hill", "765", "LCRA TSC and Oncor", 5,
      "Route case filed March 26, 2026 with 122 route options. In August the state judges (SOAH) recommended denying it: "
      "need not shown, and about 1,400 landowners may not have been properly notified. On Sept. 11 the PUC sent it back to "
      "the judges for a supplemental recommendation on two points, so the decision is delayed and no route is chosen yet.",
      "Waiting on the judges' supplemental recommendation, then a PUC vote. The PUC can still approve it. Energize target "
      "was end of 2030.",
      "Route options and the landowner list are public. The end substations (Big Hill, Schleicher County; Bell County "
      "East, Bell County) are fixed.",
      "Pull the landowner list and route map from Docket 59475; focus on parcels near both end substations. With the case "
      "delayed and possibly denied, weigh land near Big Hill (which other 765 kV lines also use) over land along the "
      "middle of the route.",
      miles="214 to 244 (endpoints 199 miles apart)", endpoints="Big Hill (Schleicher County) to Bell County East (Bell County)",
      counties="Study area: Bell, Burnet, Concho, Coryell, Lampasas, Llano, Mason, McCulloch, Menard, Milam, San Saba, Schleicher, Tom Green, Williamson",
      docket="59475", links=[("LCRA project page", "https://www.lcra.org/energy/electric-transmission/transmission-line-routing/bell-county-east-to-big-hill-765-kv-transmission-project/"),
                             ("PUCT Docket 59475", "https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber=59475&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending"),
                             ("DailyTrib: decision delayed by remand (Sept. 25, 2026)", "https://www.dailytrib.com/2026/09/25/transmission-line-decision-delayed/")],
      checked="checked 2026-10-12"),
    p("big-hill-sand-lake", "Big Hill to Sand Lake", "765", "LCRA TSC and Oncor", 5,
      "One of the three PUCT-approved 765 kV Permian import paths (plan approved April 24, 2025). Route-case status "
      "needs checking: the PUC acted on several 765 kV route cases in August and September 2026.",
      "Confirm whether the final route is approved.",
      "Ends at Sand Lake in Reeves County, next to the Pecos County queue pile-up (56 projects waiting).",
      "Confirm status on the LCRA page; map parcels near Sand Lake and Big Hill.",
      endpoints="Big Hill (Schleicher County) to Sand Lake (Reeves County)",
      links=[("LCRA project page", "https://www.lcra.org/energy/electric-transmission/transmission-line-routing/big-hill-to-sand-lake-765-kv-transmission-project/"),
             ("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/big-hill-switch-to-sand-lake-switch-765-kv-transmission-line-project.html")]),
    p("howard-solstice", "Howard to Solstice", "765", "AEP Texas and CPS Energy", 5,
      "About 370 miles from Bexar County to Pecos County. Open houses were held in August 2025 (Atascosa, Uvalde, Del Rio, "
      "Fort Stockton). Secondary sources report PUC action in September 2026; needs checking.",
      "Confirm the PUC decision and the approved route.",
      "A 765 kV import path into the Permian; Solstice (Pecos County) becomes a major hub.",
      "Confirm status; map parcels near Solstice and Howard.", miles="about 370",
      endpoints="Howard (Bexar County) to Solstice (Pecos County)",
      counties="Bexar, Atascosa, Uvalde, Val Verde, Pecos and counties between",
      links=[("AEP Texas project page", "https://aeptransmission.com/texas/howard-solstice/"),
             ("CPS Energy project page", "https://www.cpsenergy.com/content/corporate/en/about-us/new-infrastructure/howard-solstice-transmission.html")]),
    p("dinosaur-longshore", "Dinosaur to Longshore", "765", "Oncor", 6,
      "Part of the PUCT-approved Permian import path (Dinosaur to Longshore to Drill Hole). A secondary source reports the "
      "PUC approved two Oncor 765 kV route amendments on August 28, 2026; needs checking which.",
      "If approved, right-of-way buying follows.", "Large new 765 kV corridor; route likely fixed, so K2 is late on the line "
      "itself but early on new substations along it.", "Confirm status; focus on the new substations.",
      links=[("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/dinosaur-to-longshore-765-kv-transmission-line-project.html")]),
    p("longshore-drill-hole", "Longshore to Drill Hole", "765", "Oncor", 6,
      "Second half of the Dinosaur-Longshore-Drill Hole Permian import path. Status needs checking (see Dinosaur to Longshore).",
      "If approved, right-of-way buying follows.", "Drill Hole becomes a 765 kV hub in the Delaware Basin.",
      "Confirm status; map parcels near Drill Hole.",
      links=[("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/longshore-switch---drill-hole-switch-765-kv-transmission-line-pr.html")]),
    p("white-baker-bottlebrush", "White Baker to Bottlebrush", "345", "TNMP", 5,
      "TNMP opened a route case at the PUC in the week of October 8, 2026 (Docket 60382).",
      "Application with route options and landowner list; PUC decision in about 6 months.",
      "Brand new case in Pecos County, the busiest Permian queue county. Bottlebrush also connects to Solstice (765 kV hub).",
      "Open Docket 60382, get the route map and end substations, map parcels around Bottlebrush.",
      counties="Pecos", docket="60382",
      links=[("PUCT Docket 60382", "https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber=60382&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending")],
      checked="checked 2026-10-12", window="Act fast"),
    p("bottlebrush-solstice", "Bottlebrush to Solstice", "345", "AEP Texas", 3,
      "AEP Texas project page is live. Stage and dates need checking.", "Check the page for open houses and filing date.",
      "Links Bottlebrush to the Solstice 765 kV hub in Pecos County.", "Read the project page; note end substations.",
      links=[("AEP Texas project page", "https://aeptransmission.com/texas/bottlebrush-solstice/")]),
    p("bakersfield-white-baker", "Bakersfield to White Baker", "345", "LCRA TSC", 3,
      "LCRA project page is live. Stage and dates need checking.", "Check the page for open houses and filing date.",
      "Feeds White Baker, the start of TNMP's new White Baker to Bottlebrush case.", "Read the project page; note end substations.",
      links=[("LCRA project page", "https://www.lcra.org/energy/electric-transmission/transmission-line-routing/bakersfield-to-white-baker-345-kv-transmission-line-project/")]),
    p("consavvy-long-creek", "Consavvy to Long Creek", "345", "Oncor", 5,
      "Route case filed late August or early September 2026 (Docket 60190).", "PUC decision in about 6 months from filing.",
      "Crosses eight West-Central Texas counties; route options and landowners are public now.",
      "Get the route map from Docket 60190; map parcels near both end switches.",
      counties="Glasscock, Howard, Jones, Midland, Mitchell, Nolan, Shackelford, Taylor", docket="60190",
      links=[("PUCT Docket 60190", "https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber=60190&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending"),
             ("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/Consavvy-to-Long-Creek-Switch-345kV.html")],
      checked="checked 2026-10-12"),
    p("pine-mccloud", "Pine to McCloud", "345", "El Paso Electric", 5,
      "Route case opened September 2026 (Docket 60319); the full application with routes was filed October 9, 2026.",
      "PUC decision in about 6 months.", "New 345 kV line in El Paso County, outside ERCOT (El Paso Electric is in the Western grid).",
      "Lower priority unless K2 works El Paso; check route map.", importance="Medium", counties="El Paso", docket="60319",
      region="Texas (Western grid, El Paso)",
      links=[("PUCT Docket 60319", "https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber=60319&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending")],
      checked="checked 2026-10-12"),
    p("tuskegee-pine", "Tuskegee to Pine", "345", "El Paso Electric", 5,
      "Route case filed August 2026 (Docket 60152). An intervenor asked for a route-adequacy hearing.",
      "PUC decision in about 6 months.", "New 345 kV lines in El Paso County (Western grid).",
      "Lower priority unless K2 works El Paso.", importance="Medium", counties="El Paso", docket="60152",
      region="Texas (Western grid, El Paso)",
      links=[("PUCT Docket 60152", "https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber=60152&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending")],
      checked="checked 2026-10-12"),
    p("rockhound-longshore", "Rockhound to Longshore (double circuit)", "345", "Oncor", 2,
      "Oncor submitted a 345 kV double-circuit line to ERCOT's planning review in June 2026; Oncor also has a project page.",
      "ERCOT review, then open houses and a route filing.", "Connects into Longshore, a new 765 kV hub. Early stage.",
      "Read the ERCOT submission for end substations and counties.",
      links=[("ERCOT submission (June 2026)", "https://www.ercot.com/files/docs/2026/06/19/8.-Oncor_Rockhound-to-Longshore-345-kV-Double-Circuit-Line_Project_RPG_06192026.pdf"),
             ("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/longshore-to-rockhound-345-kv-transmission-line-project.html")],
      checked="checked 2026-10-12"),
    p("panhandle-plan", "Panhandle Reliability Transmission Plan", "", "Cross Texas and AEP", 2,
      "Presented to ERCOT's planning group in July 2026; ERCOT is reviewing a combined AEP and Cross Texas Panhandle project.",
      "ERCOT recommendation, then route filings.", "Regional build-out in the Panhandle, a strong wind and solar area.",
      "Read the July 2026 presentation for line voltages and substations.", importance="Medium",
      links=[("Cross Texas presentation (July 2026)", "https://www.ercot.com/files/docs/2026/07/20/12.-ERCOT-RPG_CTT-PH-Reliability-Transmission-Plan_Presentation_July_21_2026.pdf")]),
    p("border-clearfork", "Border to Clearfork", "345", "Oncor", 6,
      "Route case filed May 29, 2025 (Docket 58126), Loving to Andrews counties, 58 to 77 miles; completion planned 2028. "
      "Decision status needs checking.", "Right-of-way buying and construction.", "Delaware Basin capacity; likely approved, so late.",
      "Confirm the approved route; check for new substations along it.", importance="Medium", counties="Loving, Andrews",
      docket="58126", links=[("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/border-switch-clearfork-switch-345-kv-transmission-line-project.html")]),
    p("el-capitan-dry-lake", "El Capitan to Dry Lake", "345", "Oncor", 6,
      "Route case filed February 26, 2026 (Docket 59353); Oncor's page says the PUC approved it August 20, 2026.",
      "Right-of-way buying next.", "Approved, so the route is fixed; utility land agents are likely active.",
      "Low priority for new land; note the substations.", importance="Medium", miles="about 25", counties="Culberson, Reeves",
      docket="59353", links=[("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/el-capitan-to-dry-lake-345kv-transmission-line-project.html")]),
    p("rockhound-connell", "Rockhound to Connell", "345", "Oncor", 6,
      "Route case filed September 2025 (Docket 58519); notice of approval signed March 12, 2026.", "Right-of-way buying and construction.",
      "Approved; late for the line itself.", "Low priority.", importance="Medium", docket="58519",
      links=[("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/rockhound-switch---connell-switch-345-kv-transmission-line-proje.html")]),
    p("ranger-camp-tonkawa", "Ranger Camp to Tonkawa", "345", "Oncor", 6,
      "Notice of approval signed February 19, 2026 (Docket 58848).", "Right-of-way buying and construction.",
      "Approved; late for the line itself.", "Low priority.", importance="Medium", docket="58848",
      links=[("Oncor project page", "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/ranger-camp-to-tonkawa-345-kV-transmission-line-project.html")]),
]

ONCOR_PAGES = [
    ("Liggett to Skyview", "liggett-switch-to-skyview-switch-345-kv-transmission-line-projec.html"),
    ("Ranger Camp to Midland East", "ranger-camp-switch-to-midland-east-switch-345kv-transmission-lin.html"),
    ("Temple to Salado", "temple-switch---salado-switch-345-138-kv-transmission-line-proje.html"),
    ("Lamesa to Faraday", "lamesa---faraday-345kv.html"),
    ("Mascho to Lamesa", "mascho-switch-to-lamesa-switch-345kv-transmission-line-project.html"),
    ("Border to Quarry Field", "border-switch---quarry-field-switch-345-kv-transmission-line-pro.html"),
    ("Drill Hole to Border", "drill-hole-switch-border-switch-345-kv-transmission-line-proje.html"),
    ("Drill Hole to El Capitan", "Drill_Hole_Switch_to_El_Capitan_Switch_345_kV_Transmission_Line_Project.html"),
    ("Drill Hole to Riverton", "drill-hole-switch---riverton-switch-345-kv-transmission-line-pro.html"),
    ("Dry Lake to Faulkner", "dry-lake-to-faulkner-345kv-transmission-line-project.html"),
    ("Redland to Longleaf", "REDLAND_LONGLEAF_345_kV_TRANSMISSION_LINE_PROJECT.html"),
]
BASE = "https://www.oncor.com/content/oncorwww/us/en/home/about-us/transmission-systems/current-transmission-line-projects/"
for name, slug in ONCOR_PAGES:
    pid = "oncor-" + name.lower().replace(" ", "-")
    P.append(p(pid, name, "345", "Oncor", 3, "Oncor project page is live. Stage and dates not yet reviewed.",
               "Open the page for open-house dates, route case number and in-service date.",
               "A new 345 kV line on Oncor's current-projects list.", "Review the page and update this record.",
               importance="Medium", links=[("Oncor project page", BASE + slug)]))

P += [
    p("valley-link", "Valley Link", "765", "Valley Link Transmission (PJM)", 3,
      "Billion-dollar 765 kV line in the PJM region; Campbell County, Virginia passed a resolution opposing it (Oct 2026 news).",
      "State route approvals in Virginia and neighboring states.", "Outside Texas, but K2 works US-wide; a major new corridor.",
      "Read the news story; add PJM routing filings to the US Regions watch.", importance="Medium", region="Other US (PJM: Virginia area)",
      links=[("News (Lynchburg News and Advance)", "https://news.google.com/rss/articles/CBMipwFBVV95cUxOQjJmelJWallUT1ZBczEza1ZDSENCLWJwWVN2MGVYdmVlX21oeWw5a0NRcEhoRW4zTzBwZmJsOElLS2RxOHFrbk9ZemhsN3lLbzVJdWFTekE1ZGpkbEJyc0JOdmZWWUhOZFdLYTN2UlBHaTdwM05qTGFrUGdScXdDSjNhYkRybHRJXzNDVjBWLTlBNDVJQmI4YmF5NmYybXY1aVNRVWZJMA?oc=5")]),
]

# Status found while researching the maps (2026-10-13): PUCT case records, utility pages and news.
DOCKET_URL = "https://interchange.puc.texas.gov/search/filings/?UtilityType=A&ControlNumber={}&ItemMatch=Equal&DocumentType=ALL&SortOrder=Ascending"
FOUND = "checked 2026-10-13"
UPDATES = {
    "big-hill-sand-lake": dict(stage=5, docket="59182", checked=FOUND,
        status="Route case filed January 15, 2026 with 106 route options. The judges' proposal for decision came in June 2026; "
               "as of September no final order had been signed.",
        next_step="PUC vote on the route. Target in service winter 2030.",
        why_k2="Route options and the landowner list are public. Ends at Sand Lake (Ward County, about 6 miles northeast of Pecos) "
               "and Big Hill (Schleicher County).",
        k2_action="Pull the route map and landowner list from Docket 59182; focus on parcels near both end substations.",
        endpoints="Big Hill (Schleicher County) to Sand Lake (Ward County)"),
    "howard-solstice": dict(stage=6, docket="59336", checked=FOUND,
        status="Route case at the PUC (Docket 59336). Final order on September 18, 2026 approved Route 4-Mod 1.",
        next_step="AEP Texas and CPS Energy buy easements along the approved route, then build.",
        why_k2="The route is fixed, so land along it is already priced in. Solstice (Pecos County) and Howard (Bexar County) "
               "become 765 kV hubs that new lines and projects will connect to.",
        k2_action="Look at land near the two hubs, not along the route."),
    "dinosaur-longshore": dict(stage=6, docket="59315", checked=FOUND,
        status="The PUC unanimously approved the route on August 28, 2026 (Docket 59315). Oncor expects to finish in 2028.",
        next_step="Oncor buys easements along the approved route, then builds."),
    "longshore-drill-hole": dict(stage=6, docket="59029", checked=FOUND,
        status="The PUC unanimously approved the route on August 28, 2026 (Docket 59029). About 160 miles; Oncor expects to finish in 2029.",
        next_step="Oncor buys easements along the approved route, then builds."),
    "bakersfield-white-baker": dict(stage=5, docket="59908", checked=FOUND,
        status="LCRA TSC filed the route case on June 23, 2026 (Docket 59908). The line is in Pecos County.",
        next_step="PUC decision expected about 6 months after filing.",
        k2_action="Pull the route map and landowner list from Docket 59908; focus on parcels near White Baker."),
    "rockhound-longshore": dict(next_step="Oncor expects to file the route case in February 2027.", checked=FOUND),
    "oncor-border-to-quarry-field": dict(stage=6, docket="57837", checked=FOUND,
        status="Route approved by the PUC on July 11, 2025 (Docket 57837). Loving County."),
    "oncor-redland-to-longleaf": dict(stage=6, docket="57553", checked=FOUND,
        status="Route case decided (Docket 57553; Oncor has sent landowners notice of the final order). Angelina County. "
               "Longleaf is the hookup point for a new power plant, so this is mostly a plant connection."),
    "oncor-mascho-to-lamesa": dict(stage=5, docket="60082", checked=FOUND,
        status="Oncor filed the route case on August 21, 2026 (Docket 60082). Andrews, Dawson, Gaines and Martin counties."),
    "oncor-lamesa-to-faraday": dict(stage=5, docket="60083", checked=FOUND,
        status="Oncor and Wind Energy Transmission Texas filed the route case in August 2026 (Docket 60083). Borden and Dawson counties."),
    "oncor-dry-lake-to-faulkner": dict(stage=5, docket="59487", checked=FOUND,
        status="Route case with Texas-New Mexico Power (Docket 59487). The judges' proposal for decision came on August 13, 2026; "
               "the PUC vote may already have happened. Reeves County."),
    "oncor-drill-hole-to-el-capitan": dict(stage=5, docket="57828",
        status="Route case filed in 2025 (Docket 57828); the judges' proposal for decision came in August 2025, so the route "
               "has probably been decided. Confirm in the docket. Culberson County."),
    "oncor-drill-hole-to-riverton": dict(stage=5, docket="58007",
        status="Route case filed in 2025 (Docket 58007), so the route has probably been decided. Confirm in the docket. "
               "Culberson, Loving and Reeves counties."),
    "oncor-drill-hole-to-border": dict(stage=5, docket="58050",
        status="Route case filed in 2025 (Docket 58050), so the route has probably been decided. Confirm in the docket. "
               "Culberson, Reeves and Loving counties."),
    "valley-link": dict(endpoints="Two lines: Joshua Falls (Campbell County, VA) to Yeat (Culpeper County, VA), and Amos "
                                  "(Putnam County, WV) to Welton Spring (Hardy County, WV) to Rocky Point (Frederick County, MD)"),
    "oncor-temple-to-salado": dict(next_step="Oncor expects to file the route case in December 2026.", checked=FOUND,
        status="Oncor project page is live; no route case yet. Bell County."),
}
for _p in P:
    _u = UPDATES.get(_p["id"])
    if not _u:
        continue
    _p.update(_u)
    _p["stage_label"], _p["window"] = STAGE[_p["stage"]], WINDOW[_p["stage"]]
    _p["updated"] = "2026-10-13"
    if _u.get("docket") and not any("PUCT Docket" in l["label"] for l in _p["links"]):
        _p["links"].append({"label": "PUCT Docket " + _u["docket"], "url": DOCKET_URL.format(_u["docket"])})
    if _p["id"].startswith("oncor-") and _p["stage"] >= 5 and "Review the page" in _p["k2_action"]:
        _p["k2_action"] = ("Pull the approved route map from the docket and look at land near the end substations."
                           if _p["stage"] == 6 else "Pull the route map and landowner list from the docket; focus on parcels near the end substations.")
        _p["next_step"] = ("Oncor buys easements along the approved route, then builds." if _p["stage"] == 6
                           else "PUC decision on the route (usually about 6 months after filing).")

# Map data (end substation pins and shaded counties), researched separately: see merge_geo.py.
# Which pins a straight line joins, by position in geo endpoints, when a project is more than one line.
SEGMENTS = {"valley-link": [[0, 1], [2, 3, 4]], "panhandle-plan": []}
_GEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo.json")
if os.path.exists(_GEO):
    with open(_GEO, encoding="utf-8") as _fh:
        _geo = json.load(_fh)
    for _p in P:
        if _p["id"] in _geo:
            _g = _geo[_p["id"]]
            _p["geo"] = {"endpoints": _g["endpoints"], "counties": _g["counties"], "counties_basis": _g["counties_basis"]}
            if _p["id"] in SEGMENTS:
                _p["geo"]["segments"] = SEGMENTS[_p["id"]]
            _ends = [e for e in _g["endpoints"] if e.get("county")]
            if not _p["endpoints"] and len(_ends) == 2:
                _p["endpoints"] = " to ".join("%s (%s County)" % (e["name"].split(" (")[0], e["county"].split("|")[1]) for e in _ends)
            if not _p["counties"] and _g["counties"]:
                _p["counties"] = ", ".join(k.split("|")[1] for k in _g["counties"])

if __name__ == "__main__":
    print(json.dumps(P, indent=1))
