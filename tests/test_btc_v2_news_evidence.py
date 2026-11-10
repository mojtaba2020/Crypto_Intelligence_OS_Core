import unittest
from scripts.btc_v2_news_evidence import EvidenceError, validate_event, validate_batch


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(source="example", url="https://example.org/article/1",
            title="Sample", published_at_utc="2026-11-09T14:00:00Z",
            first_seen_at_utc="2026-11-09T14:01:00Z",
            fetched_at_utc="2026-11-09T14:02:00Z")
        self.cutoff = "2026-11-09T14:03:00Z"

    def test_valid(self):
        self.assertEqual(len(validate_event(self.event, self.cutoff)["evidence_id"]), 64)

    def test_reject_late(self):
        with self.assertRaises(EvidenceError):
            validate_event(self.event, "2026-11-09T14:01:30Z")

    def test_reject_naive(self):
        event = dict(self.event, published_at_utc="2026-11-09T14:00:00")
        with self.assertRaises(EvidenceError):
            validate_event(event, self.cutoff)

    def test_reject_bad_order(self):
        event = dict(self.event, first_seen_at_utc="2026-11-09T13:59:00Z")
        with self.assertRaises(EvidenceError):
            validate_event(event, self.cutoff)

    def test_reject_revision_after_cutoff(self):
        event = dict(self.event, revised_at_utc="2026-11-09T14:04:00Z")
        with self.assertRaises(EvidenceError):
            validate_event(event, self.cutoff)

    def test_reject_duplicate(self):
        with self.assertRaises(EvidenceError):
            validate_batch([self.event, self.event], self.cutoff)

    def test_reject_insecure_url(self):
        event = dict(self.event, url="http://example.org/article/1")
        with self.assertRaises(EvidenceError):
            validate_event(event, self.cutoff)


if __name__ == "__main__":
    unittest.main()
