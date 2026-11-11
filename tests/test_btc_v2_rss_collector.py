import unittest
from scripts.btc_v2_rss_collector import collect_feed


class RSSCollectorTests(unittest.TestCase):
    def test_observation_time_is_not_backdated(self):
        xml = b'<rss><channel><item><title>Example</title><link>https://example.org/a</link><pubDate>Mon, 09 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'
        rows = collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["first_seen_at_utc"], "2026-11-10T12:00:00Z")

    def test_future_dated_is_rejected(self):
        xml = b'<rss><channel><item><title>Example</title><link>https://example.org/a</link><pubDate>Wed, 11 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z"), [])

    def test_missing_pubdate_is_rejected(self):
        xml = b'<rss><channel><item><title>Example</title><link>https://example.org/a</link></item></channel></rss>'
        self.assertEqual(collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z"), [])


if __name__ == "__main__":
    unittest.main()
