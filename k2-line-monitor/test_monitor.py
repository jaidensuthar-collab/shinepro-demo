"""Offline tests for the page parsers. Run: python3 -m unittest test_monitor.py"""

import datetime as dt
import unittest

import monitor


class ParserTests(unittest.TestCase):
    def test_voltage(self):
        self.assertEqual(monitor.voltage("Temple to Salado Switch 345/138 kV Line"), "345/138")
        self.assertEqual(monitor.voltage("SAND BLUFF TO BOB CREEK WIND 345-KV T"), "345")
        self.assertEqual(monitor.voltage("Euclid 765-kV Substation"), "765")
        self.assertEqual(monitor.voltage("no voltage here"), "")

    def test_transmission_case_filter(self):
        yes = ("APPLICATION OF EL PASO ELECTRIC COMPANY TO AMEND ITS CERTIFICATE OF CONVENIENCE AND "
               "NECESSITY FOR THE PINE TO MCCLOUD 345 KV TRANSMISSION LINE IN EL PASO COUNTY")
        battery = ("APPLICATION OF SOUTHWESTERN ELECTRIC POWER COMPANY TO AMEND ITS CERTIFICATE OF "
                   "CONVENIENCE AND NECESSITY TO PURCHASE A 200 MW BATTERY ENERGY STORAGE S")
        other = "APPLICATION OF MALLARD ENERGY STORAGE, LLC FOR A POWER GENERATION COMPANY REGISTRATION"
        self.assertTrue(monitor.is_transmission_case(yes))
        self.assertFalse(monitor.is_transmission_case(battery))
        self.assertFalse(monitor.is_transmission_case(other))

    def test_parse_puct_dockets(self):
        page = ("<table><tr><th>Control</th></tr>"
                "<tr><td><a href='x'>60319</a></td><td>1</td><td>EL PASO ELECTRIC COMPANY</td>"
                "<td>APPLICATION ... 345 KV TRANSMISSION LINE</td></tr></table>")
        rows = monitor.parse_puct_dockets(page)
        self.assertEqual(rows, [{"control": "60319", "party": "EL PASO ELECTRIC COMPANY",
                                 "description": "APPLICATION ... 345 KV TRANSMISSION LINE"}])

    def test_parse_rpg_page(self):
        page = ('<a href="https://www.ercot.com/calendar/07212026-RPG-Meeting">Jul 21</a>'
                '<a href="https://www.ercot.com/files/docs/2026/04/09/13.-26RPG005-DME-Denton.pdf">'
                '13. 26RPG005-DME-Denton Area Transmission Improvements-Final</a>'
                '<a href="/files/docs/2026/04/10/2.-Miscellaneous-Update.pdf">2. Miscellaneous Update</a>')
        meetings, docs = monitor.parse_rpg_page(page)
        self.assertEqual(meetings, {"https://www.ercot.com/calendar/07212026-RPG-Meeting"})
        self.assertEqual(len(docs), 2)
        self.assertTrue(docs[1][1].startswith("https://www.ercot.com/files/docs/"))
        self.assertTrue(monitor.is_relevant_rpg_doc(docs[0][0]))
        self.assertFalse(monitor.is_relevant_rpg_doc(docs[1][0]))
        self.assertEqual(monitor.meeting_date("https://www.ercot.com/calendar/07212026-RPG-Meeting"),
                         dt.date(2026, 7, 21))

    def test_parse_utility_projects(self):
        page = ('<a href="Hillje-BluLacy/">Hillje - Blu Lacy Transmission Improvement Project</a>'
                '<a href="/projects.php">Projects</a>'
                '<a href="Hillje-BluLacy/docs/map.pdf">Map</a>'
                '<a href="https://aeptransmission.com/texas/hillje-blulacy/">duplicate</a>')
        projects = monitor.parse_utility_projects(page, "https://aeptransmission.com/texas/",
                                                  "https://aeptransmission.com/texas/")
        self.assertEqual(projects, [("Hillje - Blu Lacy Transmission Improvement Project",
                                     "https://aeptransmission.com/texas/Hillje-BluLacy/")])

    def test_priority_and_underscores(self):
        title = monitor.clean("Oncor_Rockhound_to_Longshore_345_kV_Double_Circuit_Line")
        self.assertEqual(monitor.voltage(title), "345")
        self.assertEqual(monitor.priority("345", title), "High")
        self.assertEqual(monitor.priority("", "EIR Status Update TNMP Climax to Bells"), "Low")
        self.assertEqual(monitor.priority("69", "Mt Pleasant-Petty 69-kV line"), "Low")
        self.assertEqual(monitor.priority("", "Hillje-Blu Lacy Transmission Improvement Project"), "Medium")

    def test_watched_case_filings(self):
        page = ("<tr><td>6608</td><td>9/28/2026</td><td>SOAH</td><td>PL</td>"
                "<td>SOAH ORDER NO. 36 IN DOCKET NO. 59475- NOTICE TO PARTIES</td></tr>"
                "<tr><td>6620</td><td>10/8/2026</td><td>PUC OPDM</td><td>PL</td>"
                "<td>ORDER ON REHEARING</td></tr>"
                "<tr><td>6621</td><td>10/8/2026</td><td>Gail Perez</td><td>COM</td><td>STOP ALL 765kV lines</td></tr>"
                "<tr><td>6622</td><td>10/9/2026</td><td>ONCOR ELECTRIC DELIVERY COMPANY LLC</td><td>PL</td>"
                "<td>NOTICE OF ERRATA TO ROUTE MAP</td></tr>"
                "<tr><td>6623</td><td>10/9/2026</td><td>ONCOR ELECTRIC DELIVERY COMPANY LLC</td><td>PL</td>"
                "<td>NOTICE OF CHANGE OF COUNSEL</td></tr>"
                "<tr><td>6626</td><td>10/9/2026</td><td>PUC OPDM</td><td>PL</td><td>ORDER NO. 5- GRANTING INTERVENTION</td></tr>"
                "<tr><td>6624</td><td>10/9/2026</td><td>PUC LEGAL</td><td>PL</td><td>PROTECTIVE ORDER CERTIFICATIONS</td></tr>"
                "<tr><td>6625</td><td>10/9/2026</td><td>ONCOR ELECTRIC DELIVERY COMPANY LLC</td><td>PL</td>"
                "<td>ONCOR'S SUPPLEMENTAL RESPONSE TO FIRST REQUEST FOR INFORMATION</td></tr>")
        rows = monitor.parse_puct_filings(page)
        self.assertEqual([r["item"] for r in rows], ["6608", "6620", "6621", "6622", "6623", "6626", "6624", "6625"])
        levels = [monitor.classify_filing(r) for r in rows]
        self.assertEqual(levels, [None, "High", None, "Medium", None, None, None, None])

    def test_parse_news(self):
        xml = ("<rss><channel><item><title>Open house set for 765-kV line - Victoria Advocate</title>"
               "<link>https://news.example/a</link><pubDate>Thu, 08 Oct 2026 10:00:00 GMT</pubDate>"
               "<source url='x'>Victoria Advocate</source></item></channel></rss>")
        items = monitor.parse_news(xml)
        self.assertEqual(items[0]["source"], "Victoria Advocate")
        self.assertIn("765-kV", items[0]["title"])

    def test_guess_utility(self):
        self.assertEqual(monitor.guess_utility("EIR - Oncor and LCRA TSC - Muscovy Voss"), "Oncor, LCRA TSC")
        self.assertEqual(monitor.guess_utility("AEPSC Laredo Area Upgrades"), "AEP")


if __name__ == "__main__":
    unittest.main()
