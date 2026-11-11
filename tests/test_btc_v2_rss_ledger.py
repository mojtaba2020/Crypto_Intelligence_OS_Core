import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.btc_v2_rss_collector import append_new_evidence
from scripts.btc_v2_news_evidence import EvidenceError


class LedgerTests(unittest.TestCase):
    def test_repeated_poll_does_not_duplicate(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            event = {"evidence_id": "one", "title": "A"}
            self.assertEqual(append_new_evidence(path, [event]), 1)
            self.assertEqual(append_new_evidence(path, [event]), 0)
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_new_event_appends_without_rewriting(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            append_new_evidence(path, [{"evidence_id": "one"}])
            original = path.read_bytes()
            self.assertEqual(append_new_evidence(path, [{"evidence_id": "one"}, {"evidence_id": "two"}]), 1)
            self.assertTrue(path.read_bytes().startswith(original))
            self.assertEqual([json.loads(line)["evidence_id"] for line in path.read_text().splitlines()], ["one", "two"])

    def test_corrupt_ledger_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"title":"no id"}')
            with self.assertRaises(EvidenceError):
                append_new_evidence(path, [{"evidence_id": "two"}])


if __name__ == "__main__":
    unittest.main()
