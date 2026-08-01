import asyncio
import logging
from datetime import datetime, timezone

import feedparser
import httpx
import trafilatura

from db import delete_old_articles, insert_article
from sources import ENABLED_SOURCES

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"
}


def _parse_date(entry) -> str | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return None


def _make_teaser(text: str, length: int = 220) -> str:
    if not text:
        return ""
    # Strip HTML tags from RSS summaries
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text[:length] + "…" if len(text) > length else text


async def _fetch_fulltext(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        resp = await client.get(url, timeout=20.0)
        resp.raise_for_status()
        html = resp.text
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None,
            lambda: trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            ),
        )
        return text
    except Exception as e:
        logger.warning("Volltext fehlgeschlagen %s: %s", url, e)
        return None


async def scrape_source(source: dict, client: httpx.AsyncClient) -> int:
    new_count = 0
    try:
        resp = await client.get(source["rss_url"], timeout=20.0)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        if not feed.entries:
            logger.warning("%s: Feed leer oder nicht parsebar (URL: %s)", source["name"], source["rss_url"])
            return 0
    except Exception as e:
        logger.error("RSS-Abruf fehlgeschlagen %s: %s", source["name"], e)
        return 0

    for entry in feed.entries:
        url = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        if not url or not title:
            continue

        raw_summary = entry.get("summary", "") or entry.get("description", "")
        teaser = _make_teaser(raw_summary)
        published_at = _parse_date(entry)
        content = None

        if not source["paywall"]:
            content = await _fetch_fulltext(url, client)
            if content and not teaser:
                teaser = _make_teaser(content)

        inserted = await insert_article(
            {
                "url": url,
                "title": title,
                "source_name": source["name"],
                "published_at": published_at,
                "fetched_at": datetime.utcnow().isoformat(),
                "teaser": teaser,
                "content": content,
            }
        )
        if inserted:
            new_count += 1

    logger.info("%s: %d neue Artikel", source["name"], new_count)
    return new_count


async def run_all_sources(retention_days: int = None):
    import os

    if retention_days is None:
        retention_days = int(os.getenv("ARTICLE_RETENTION_DAYS", "7"))

    logger.info("Starte Scraping (%d Quellen)…", len(ENABLED_SOURCES))
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
        tasks = [scrape_source(s, client) for s in ENABLED_SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    total = sum(r for r in results if isinstance(r, int))
    errors = sum(1 for r in results if isinstance(r, Exception))
    logger.info("Scraping fertig: %d neue Artikel, %d Fehler", total, errors)

    await delete_old_articles(retention_days)
    return total
