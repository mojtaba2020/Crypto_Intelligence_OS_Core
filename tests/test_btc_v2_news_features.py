import unittest
from scripts.btc_v2_news_features import summarize_news
from scripts.btc_v2_news_evidence import EvidenceError


class NewsFeatureTests(unittest.TestCase):
    def setUp(self):
        self.cutoff = "2026-11-09T14:03:00Z"
        self.event = dict(source="example", url="https://example.org/article/1",
            title="Sample", published_at_utc="2026-11-09T14:00:00Z",
            first_seen_at_utc="2026-11-09T14:01:00Z",
            fetched_at_utc="2026-11-09T14:02:00Z")

    def test_unlabeled_is_unknown(self):
        result = summarize_news([self.event], self.cutoff)
        self.assertEqual(result["stance_counts"]["unknown"], 1)
        self.assertEqual(result["net_labeled_stance"], 0)

    def test_labeled_with_timestamp(self):
        event = dict(self.event, topic="macro", stance="positive",
                     classified_at_utc="2026-11-09T14:02:00Z")
        result = summarize_news([event], self.cutoff)
        self.assertEqual(result["net_labeled_stance"], 1)
        self.assertEqual(result["topic_counts"]["macro"], 1)

    def test_reject_future_classification(self):
        event = dict(self.event, stance="negative",
                     classified_at_utc="2026-11-09T14:04:00Z")
        with self.assertRaises(EvidenceError):
            summarize_news([event], self.cutoff)

    def test_reject_unstamped_label(self):
        with self.assertRaises(EvidenceError):
            summarize_news([dict(self.event, stance="positive")], self.cutoff)

    def test_reject_unknown_topic(self):
        with self.assertRaises(EvidenceError):
            summarize_news([dict(self.event, topic="unknown_topic")], self.cutoff)

    def test_empty_coverage(self):
        result = summarize_news([], self.cutoff)
        self.assertFalse(result["has_news_coverage"])
        self.assertEqual(result["count"], 0)

    def test_reject_bad_lookback(self):
        with self.assertRaises(EvidenceError):
            summarize_news([], self.cutoff, lookback_hours=0)


if __name__ == "__main__":
    unittest.main()
