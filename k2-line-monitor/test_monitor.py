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

    def test_guess_utility(self):
        self.assertEqual(monitor.guess_utility("EIR - Oncor and LCRA TSC - Muscovy Voss"), "Oncor, LCRA TSC")
        self.assertEqual(monitor.guess_utility("AEPSC Laredo Area Upgrades"), "AEP")


if __name__ == "__main__":
    unittest.main()
