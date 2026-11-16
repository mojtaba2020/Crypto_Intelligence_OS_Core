import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.btc_v2_news_evidence import EvidenceError
from scripts.btc_v2_rss_collector import append_new_evidence


class LedgerTests(unittest.TestCase):
    def test_repeated_poll_does_not_duplicate(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            event = {"evidence_id": "one", "title": "A"}
            self.assertEqual(append_new_evidence(path, [event]), 1)
            self.assertEqual(append_new_evidence(path, [event]), 0)
            contents = path.read_bytes()
            self.assertEqual(contents.count(b"\n"), 1)
            self.assertEqual(len(contents.splitlines()), 1)

    def test_new_event_appends_without_rewriting(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            append_new_evidence(path, [{"evidence_id": "one"}])
            original = path.read_bytes()
            count = append_new_evidence(
                path, [{"evidence_id": "one"}, {"evidence_id": "two"}]
            )
            self.assertEqual(count, 1)
            self.assertTrue(path.read_bytes().startswith(original))
            ids = [json.loads(line)["evidence_id"] for line in path.read_text().splitlines()]
            self.assertEqual(ids, ["one", "two"])
            self.assertEqual(path.read_bytes().count(b"\n"), 2)

    def test_corrupt_ledger_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"title":"no id"}\n')
            before = path.read_bytes()
            with self.assertRaises(EvidenceError):
                append_new_evidence(path, [{"evidence_id": "two"}])
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_existing_json_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"evidence_id":"one"}\nnot-json\n')
            before = path.read_bytes()
            with self.assertRaises(EvidenceError):
                append_new_evidence(path, [{"evidence_id": "two"}])
            self.assertEqual(path.read_bytes(), before)

    def test_duplicate_existing_ids_fail_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"evidence_id":"one"}\n{"evidence_id":"one"}\n')
            before = path.read_bytes()
            with self.assertRaises(EvidenceError):
                append_new_evidence(path, [{"evidence_id": "two"}])
            self.assertEqual(path.read_bytes(), before)

    def test_unterminated_existing_line_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"evidence_id":"one"}')
            before = path.read_bytes()
            with self.assertRaises(EvidenceError):
                append_new_evidence(path, [{"evidence_id": "two"}])
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_later_in_batch_causes_no_partial_append(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            append_new_evidence(path, [{"evidence_id": "one"}])
            before = path.read_bytes()
            with self.assertRaises(EvidenceError):
                append_new_evidence(
                    path,
                    [{"evidence_id": "two"}, {"evidence_id": "three", "bad": object()}],
                )
            self.assertEqual(path.read_bytes(), before)

    def test_missing_evidence_id_does_not_create_file(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            with self.assertRaises(EvidenceError):
                append_new_evidence(path, [{"title": "missing id"}])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
