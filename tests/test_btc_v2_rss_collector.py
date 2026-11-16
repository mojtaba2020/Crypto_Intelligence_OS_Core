import unittest

from scripts.btc_v2_news_evidence import EvidenceError
from scripts.btc_v2_rss_collector import _PublisherHTTPSRedirect, collect_feed


def feed(url: str, published: str = "Mon, 09 Nov 2026 12:00:00 GMT") -> bytes:
    return (
        "<rss><channel><item><title>Example</title>"
        f"<link>{url}</link>"
        f"<pubDate>{published}</pubDate>"
        "</item></channel></rss>"
    ).encode("utf-8")


class RSSCollectorTests(unittest.TestCase):
    def test_observation_time_is_not_backdated(self):
        xml = feed("https://www.federalreserve.gov/newsevents/pressreleases/a.htm")
        rows = collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["first_seen_at_utc"], "2026-11-10T12:00:00Z")

    def test_future_dated_is_rejected(self):
        xml = feed(
            "https://www.federalreserve.gov/a",
            published="Wed, 11 Nov 2026 12:00:00 GMT",
        )
        self.assertEqual(
            collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z"), []
        )

    def test_missing_pubdate_is_rejected(self):
        xml = (
            b"<rss><channel><item><title>Example</title>"
            b"<link>https://www.federalreserve.gov/a</link>"
            b"</item></channel></rss>"
        )
        self.assertEqual(
            collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z"), []
        )

    def test_offdomain_and_spoofed_publisher_links_are_not_news(self):
        for url in (
            "https://example.org/a",
            "https://www.federalreserve.gov.evil.example/a",
            "http://www.federalreserve.gov/a",
            "https://evil.example@www.federalreserve.gov/a",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    collect_feed(feed(url), "federal_reserve", "2026-11-10T12:00:00Z"),
                    [],
                )

    def test_sec_official_feed_link_allowed(self):
        rows = collect_feed(
            feed("https://www.sec.gov/news/press-release/example"),
            "sec_press",
            "2026-11-10T12:00:00Z",
        )
        self.assertEqual(len(rows), 1)

    def test_doctype_and_entities_are_rejected_before_xml_parse(self):
        xml = b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel/></rss>'
        with self.assertRaisesRegex(EvidenceError, "DTD or entity"):
            collect_feed(xml, "federal_reserve", "2026-11-10T12:00:00Z")

    def test_bad_encoding_rejected(self):
        with self.assertRaisesRegex(EvidenceError, "UTF-8"):
            collect_feed(b"\xff", "federal_reserve", "2026-11-10T12:00:00Z")

    def test_redirect_off_publisher_domain_is_blocked(self):
        handler = _PublisherHTTPSRedirect("federal_reserve")
        with self.assertRaisesRegex(EvidenceError, "redirect"):
            handler.redirect_request(
                None, None, 302, "redirect", {}, "https://evil.example/path"
            )


if __name__ == "__main__":
    unittest.main()
