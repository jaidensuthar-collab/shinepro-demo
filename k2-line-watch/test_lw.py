"""Tests for lw.py (no network: the monitor is faked). Run: python3 -m unittest test_lw.py"""
import argparse
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import lw

REC = {"id": "puct:60999", "importance": "High", "what_happened": "Oncor asked the PUC to approve a route.",
       "url": "https://example.test/60999", "kv": "345", "found": "2026-11-05", "status": "New"}
ROW = ["2026-11-05", "High", "Oncor asked the PUC to approve a route.", "X - Y 345 kV", "Oncor", "'345", "",
       "Route case", "Why", "Next", "https://example.test/60999", "puct:60999", "New"]


def fake_monitor(records, rows):
    def run(script, *args, **kw):
        a = dict(zip(args[::2], args[1::2]))
        with open(a["--json"], "w") as fh:
            json.dump({"checked": "2026-11-05", "total_found": 10, "dropped_not_k2": 2, "new": records, "errors": []}, fh)
        with open(a["--rows"], "w") as fh:
            json.dump(rows, fh)
        return 0, "", ""
    return run


class WatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "seen.txt"), "w") as fh:
            fh.write("old:1\n")

    def watch(self, records, rows, quiet=False):
        out = io.StringIO()
        with mock.patch.object(lw, "py", fake_monitor(records, rows)), contextlib.redirect_stdout(out):
            code = lw.cmd_watch(argparse.Namespace(quiet=quiet, puct_days=14), state=self.tmp)
        return code, out.getvalue()

    def test_new_signal_is_stored_everywhere(self):
        code, out = self.watch([REC], [ROW])
        self.assertEqual(code, 0)
        self.assertIn("1 new K2 signal", out)
        self.assertEqual(lw.read_seen(self.tmp), ["old:1", "puct:60999"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "signals", "puct_60999.json")))
        with open(os.path.join(self.tmp, "k2-watch.csv")) as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], lw.SHEET_HEADER)
        self.assertEqual(rows[1][5], "345")  # the sheet's text apostrophe is dropped in the CSV
        status = lw.read_json(os.path.join(self.tmp, "status.json"))
        self.assertEqual(status["last_run_new_for_k2"], 1)
        self.assertEqual(status["dropped_not_k2"], 2)

    def test_quiet_run_with_nothing_new_prints_nothing(self):
        code, out = self.watch([], [], quiet=True)
        self.assertEqual((code, out), (0, ""))

    def test_missing_seen_list_refuses_to_run(self):
        os.remove(os.path.join(self.tmp, "seen.txt"))
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.watch([REC], [ROW])
        self.assertEqual(code, 1)


class HelpersTest(unittest.TestCase):
    def test_tpit_edition(self):
        self.assertEqual(lw.tpit_edition("https://x/ERCOT-October-TPIT-No-Cost-100126.xlsx"), (2026, 10, 1))
        self.assertIsNone(lw.tpit_edition("https://x/other.xlsx"))

    def test_lines_diff(self):
        a = {"lines": [{"id": "1", "lifecycle": "planned"}, {"id": "2", "lifecycle": "built"}]}
        b = {"lines": [{"id": "1", "lifecycle": "approved"}, {"id": "3", "lifecycle": "proposed"}]}
        added, removed, stages = lw.lines_diff(a, b)
        self.assertEqual([x["id"] for x in added], ["3"])
        self.assertEqual([x["id"] for x in removed], ["2"])
        self.assertEqual([(x["id"], s0, s1) for x, s0, s1 in stages], [("1", "planned", "approved")])

    def test_doc_id_matches_monitor(self):
        self.assertEqual(lw.doc_id("puct:60319:83"), "puct_60319_83")

    def test_now_ct_is_central(self):
        delta = lw.dt.datetime.utcnow() - lw.now_ct()
        self.assertIn(round(delta.total_seconds() / 3600), (5, 6))


if __name__ == "__main__":
    unittest.main()
