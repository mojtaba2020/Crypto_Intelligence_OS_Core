import unittest
from scripts.btc_v2_news_dataset import build_dataset
from scripts.btc_v2_news_evidence import EvidenceError


class DatasetTests(unittest.TestCase):
    def test_empty_coverage_is_explicit(self):
        rows = build_dataset([{"cutoff_utc": "2026-11-09T14:00:00Z", "events": []}])
        self.assertEqual(rows[0]["count"], 0)
        self.assertFalse(rows[0]["has_news_coverage"])

    def test_reject_duplicate_cutoff(self):
        row = {"cutoff_utc": "2026-11-09T14:00:00Z", "events": []}
        with self.assertRaises(EvidenceError):
            build_dataset([row, row])

    def test_reject_out_of_order_cutoffs(self):
        with self.assertRaises(EvidenceError):
            build_dataset([
                {"cutoff_utc": "2026-11-09T15:00:00Z", "events": []},
                {"cutoff_utc": "2026-11-09T14:00:00Z", "events": []},
            ])

    def test_reject_invalid_events_shape(self):
        with self.assertRaises(EvidenceError):
            build_dataset([{"cutoff_utc": "2026-11-09T14:00:00Z", "events": {}}])


if __name__ == "__main__":
    unittest.main()
