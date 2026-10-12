"""Tests for the K2 relevance filter, using real titles the monitor has seen.
Run: python3 -m unittest test_k2filter.py"""

import unittest

from k2filter import explain


def sig(step, title, utility="", kv="", priority="", source=""):
    return {"step": step, "title": title, "utility": utility, "voltage_kv": kv,
            "priority": priority, "source": source}


class K2FilterTests(unittest.TestCase):
    def test_new_route_case_is_kept_and_explained(self):
        out = explain(sig("4-5 PUCT route case opened",
                          "Application Of Texas-New Mexico Power Company To Amend Its Certificate Of Convenience "
                          "And Necessity For The White Baker To Bottlebrush 345-Kv Transmission Line Project In "
                          "Pecos County", "TNMP", "345"))
        self.assertEqual(out["importance"], "High")
        self.assertEqual(out["project"], "White Baker To Bottlebrush 345-kV")
        self.assertEqual(out["where"], "Pecos County")
        self.assertIn("TNMP asked the Texas PUC", out["what_happened"])

    def test_multi_county_case(self):
        out = explain(sig("4-5", "Application Of Oncor To Amend Its Certificate Of Convenience And Necessity For "
                                 "The Consavvy Switch To Long Creek Switch 345 Kv Transmission Line Project In "
                                 "Glasscock, Howard, And Taylor Counties", "Oncor", "345"))
        self.assertEqual(out["where"], "Glasscock, Howard, Taylor counties")

    def test_rebuilds_small_lines_and_gen_ties_are_dropped(self):
        self.assertIsNone(explain(sig("4-5", "For The Mt Pleasant-Petty 69-Kv Rebuild And Upgrade Transmission "
                                             "Line In Titus County", "SWEPCO", "69")))
        self.assertIsNone(explain(sig("4-5", "For The Proposed Egan To Highpoint 138-Kv Transmission Line "
                                             "Rebuild Project In Johnson County", "Brazos Electric", "138")))
        self.assertIsNone(explain(sig("4-5", "For The Sand Bluff To Bob Creek Wind 345-Kv Transmission Line In "
                                             "Glasscock And Sterling Counties", "WETT", "345")))
        self.assertIsNone(explain(sig("3 utility", "McGee Switch - Sisters Solar POI 345kV Transmission Line "
                                                   "Project", "Oncor", "345")))
        self.assertIsNone(explain(sig("3 utility", "Fair Oaks Ranch Communities Reliability Project", "CPS Energy")))

    def test_ercot_status_updates_dropped_scopes_kept(self):
        self.assertIsNone(explain(sig("2", "EIR Status Update TNMP Climax to Bells Area Project", "TNMP")))
        out = explain(sig("2", "Oncor Rockhound to Longshore 345 kV Double Circuit Line Project", "Oncor", "345"))
        self.assertEqual(out["importance"], "High")
        self.assertIsNone(explain(sig("2", "EIR Scope Oncor Rockhound to Longshore 345 kV Line", "Oncor", "345")))
        self.assertIsNone(explain(sig("2", "26RPG022 AEN Dunlap to Decker 138-kV Line Project Overview", "", "138")))
        self.assertIsNotNone(explain(sig("2", "ERCOT RPG CTT PH Reliability Transmission Plan Presentation")))

    def test_project_pages_need_big_unbuilt_lines(self):
        self.assertIsNone(explain(sig("3 utility", "Laredo - University Transmission Improvements Project", "AEP Texas")))
        self.assertIsNone(explain({"step": "3 utility", "title": "North McCamey to Sand Lake", "utility": "LCRA TSC",
                                   "voltage_kv": "345", "note": "completed"}))
        self.assertIsNotNone(explain(sig("3 utility", "Hillje-Blu Lacy Transmission Improvement Project",
                                         "AEP Texas", "765")))

    def test_route_case_paperwork_dropped_decisions_kept(self):
        self.assertIsNone(explain(sig("5-6", "EPE'S RESPONSE TO SOAH ORDER NO. 2 REGARDING INTERVENORS WHO DID "
                                             "NOT FILE TESTIMONY", "El Paso Electric", priority="Medium")))
        out = explain(sig("5-6", "NOTICE OF APPROVAL", "PUC", priority="High", source="PUCT Docket 59475 item 7000"))
        self.assertEqual(out["importance"], "High")
        self.assertIn("Decision news", out["what_happened"])

    def test_news_needs_a_specific_line(self):
        self.assertIsNone(explain(sig("3+", "Competitive transmission in Texas could save ratepayers billions")))
        out = explain(sig("3+", "Open house set for 765-kV line near Victoria - Victoria Advocate"))
        self.assertEqual(out["importance"], "High")


if __name__ == "__main__":
    unittest.main()
