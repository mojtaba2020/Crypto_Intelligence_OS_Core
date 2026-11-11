"""BTC V2 source registry. Collection is forward-only; never backdate first_seen.

Feeds are candidates, not guaranteed authentic or available. Review terms and
publisher attribution before enabling continuous collection.
"""
SOURCES = {
    "federal_reserve": {"kind": "rss", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "topic": "macro"},
    "sec_press": {"kind": "rss", "url": "https://www.sec.gov/news/pressreleases.rss", "topic": "regulation"},
}
# X accounts, ETF flows and paid datasets intentionally disabled until a
# licensed API and verified identity mapping are configured.
