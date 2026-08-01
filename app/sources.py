# Jede Quelle: name, rss_url, paywall (bool), enabled (bool)
# Bei paywall=True wird nur der RSS-Teaser gespeichert, kein Volltext-Scraping.
# RSS-URLs beim ersten Start im Log prüfen – bei 404/Fehler hier anpassen.

SOURCES = [
    {
        "name": "MDR Dresden",
        "rss_url": "https://www.mdr.de/nachrichten/sachsen/dresden/index-rss.xml",
        "paywall": False,
        "enabled": True,
    },
    {
        "name": "Tag24 Dresden",
        "rss_url": "https://www.tag24.de/dresden/feed/",
        "paywall": False,
        "enabled": True,
    },
    {
        "name": "Pieschen Aktuell",
        "rss_url": "https://www.pieschen-aktuell.de/feed/",
        "paywall": False,
        "enabled": True,
    },
    {
        "name": "Neustadt-Ticker",
        "rss_url": "https://www.neustadt-ticker.de/feed/",
        "paywall": False,
        "enabled": True,
    },
]

ENABLED_SOURCES = [s for s in SOURCES if s["enabled"]]
