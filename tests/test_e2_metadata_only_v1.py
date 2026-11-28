"""Synthetic-only contract tests; no market data or network."""

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.e2_metadata_only_v1 import HORIZONS, VENUES, audit, projection_digest


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2014, 1, 1, tzinfo=UTC)
        self.end = datetime(2014, 3, 1, tzinfo=UTC)
        self.approval = {
            "start": "2014-01-01T00:00:00Z", "end": "2014-03-01T00:00:00Z",
            "development_end": "2014-03-01T00:00:00Z", "receipt_sha256": "a" * 64,
            "projections": {},
        }
        self.packets = []
        for venue in VENUES:
            for family in HORIZONS:
                rows = []
                for i in range(59 * 24):
                    t = self.start + timedelta(hours=i)
                    days = {"1h": 0, "1d": 1, "1w": 7, "1mo": 31 if t.month == 1 else 28}[family]
                    if family != "1h" and (t.hour or t + timedelta(days=days) > self.end):
                        continue
                    if family == "1w" and t.weekday() != 0:
                        continue
                    if family == "1mo" and t.day != 1:
                        continue
                    row = {"timestamp": int(t.timestamp())}
                    if family != "1h":
                        row.update(source_bars=days, expected_source_bars=days, is_complete=True)
                    rows.append(row)
                packet = dict(venue=venue, family=family, rows=rows, upstream_sha256="b" * 64)
                self.packets.append(packet)
                self.bind(packet)

    def bind(self, packet):
        packet["projection_sha256"] = projection_digest(packet["rows"])
        key = f'{packet["venue"]}:{packet["family"]}'
        self.approval["projections"][key] = {
            k: packet[k] for k in ("projection_sha256", "upstream_sha256")
        }

    def run_audit(self):
        return audit(self.approval, self.packets, now=datetime(2026, 11, 28, tzinfo=UTC))

    def test_full_calendar(self):
        report = self.run_audit()
        self.assertEqual(len(report["horizons"]), 15)
        for family, expected in (("1h", 1416), ("1d", 59), ("1w", 7), ("1mo", 2)):
            row = report["horizons"][family]
            self.assertEqual((row["expected"], row["shared"], row["longest"], row["missing"]),
                             (expected, expected, expected, 0))
        self.assertTrue(report["horizons"]["1y"]["exploratory"])
        self.assertFalse(report["upstream_prices_verified"])
        self.assertFalse(report["independent_custody_verified"])

    def test_two_venue_full_projection_parity(self):
        # Independent synthetic full-row intersection, with opposite edge and interior gaps.
        self.packets[0]["rows"] = self.packets[0]["rows"][1:]
        self.packets[4]["rows"].pop(699)
        self.packets[4]["rows"].pop()
        for packet in (self.packets[0], self.packets[4]):
            self.bind(packet)
        full = [[dict(row, open=100, high=101, low=99, close=100, volume=2)
                 for row in packet["rows"]] for packet in (self.packets[0], self.packets[4])]
        common = sorted(set(r["timestamp"] for r in full[0]) & set(r["timestamp"] for r in full[1]))
        runs = [1]
        for a, b in zip(common, common[1:]):
            if b - a == 3600:
                runs[-1] += 1
            else:
                runs.append(1)
        row = self.run_audit()["horizons"]["1h"]
        self.assertEqual((row["shared"], row["longest"], row["missing"]),
                         (len(common), max(runs), 1416 - len(common)))
        self.assertEqual((row["shared"], row["longest"], row["missing"]), (1413, 715, 3))

    def test_incomplete(self):
        p = self.packets[1]
        p["rows"][10].update(source_bars=0, is_complete=False)
        self.bind(p)
        row = self.run_audit()["horizons"]["1d"]
        self.assertEqual((row["shared"], row["longest"], row["missing"]), (58, 48, 1))

    def test_missing_digest(self):
        del self.packets[0]["projection_sha256"]
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_mutated_flag(self):
        self.packets[1]["rows"][0].update(source_bars=0, is_complete=False)
        with self.assertRaisesRegex(ValueError, "projection digest mismatch"):
            self.run_audit()

    def test_duplicate_and_unordered(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                original = copy.deepcopy(self.packets[0])
                p = self.packets[0]
                p["rows"][1] = p["rows"][0] if not reverse else p["rows"][2]
                self.bind(p)
                with self.assertRaises(ValueError):
                    self.run_audit()
                self.packets[0] = original
                self.bind(original)

    def test_partial_and_outside(self):
        for i, dt in ((0, self.end), (2, self.start - timedelta(days=2)), (3, self.end)):
            with self.subTest(i=i):
                original = copy.deepcopy(self.packets[i])
                p = self.packets[i]
                p["rows"][0]["timestamp"] = int(dt.timestamp())
                self.bind(p)
                with self.assertRaises(ValueError):
                    self.run_audit()
                self.packets[i] = original
                self.bind(original)

    def test_reject_prices_even_with_matching_digest(self):
        self.packets[0]["rows"][0]["close"] = 100
        self.bind(self.packets[0])
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_approval_binding(self):
        self.packets[0]["upstream_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "approval digest mismatch"):
            self.run_audit()

    def test_missing_packet(self):
        self.packets.pop()
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_inconsistent_flag(self):
        self.packets[1]["rows"][0]["is_complete"] = False
        self.bind(self.packets[1])
        with self.assertRaisesRegex(ValueError, "completeness"):
            self.run_audit()

    def test_approval_window(self):
        self.approval["development_end"] = "2014-02-01T00:00:00Z"
        with self.assertRaises(ValueError):
            self.run_audit()
