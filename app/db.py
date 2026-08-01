import os
from datetime import datetime, timedelta

import aiosqlite

DB_PATH = os.path.join(os.getenv("DATA_DIR", "./data"), "news.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS articles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT UNIQUE NOT NULL,
    title            TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    published_at     TEXT,
    fetched_at       TEXT NOT NULL,
    teaser           TEXT,
    content          TEXT,
    summary          TEXT,
    tts_path         TEXT,
    summary_tts_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_source ON articles(source_name);
"""


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_CREATE_TABLE)
        await db.commit()


async def insert_article(article: dict) -> bool:
    """Returns True if inserted (new article), False if duplicate URL."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO articles
                   (url, title, source_name, published_at, fetched_at, teaser, content)
                   VALUES (:url, :title, :source_name, :published_at, :fetched_at, :teaser, :content)""",
                article,
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_articles(source: str = None, limit: int = 150) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if source:
            cur = await db.execute(
                "SELECT * FROM articles WHERE source_name=? ORDER BY published_at DESC, fetched_at DESC LIMIT ?",
                (source, limit),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM articles ORDER BY published_at DESC, fetched_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in await cur.fetchall()]


async def get_article(article_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM articles WHERE id=?", (article_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_article(article_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [article_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE articles SET {sets} WHERE id=?", vals)
        await db.commit()


async def get_sources() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT DISTINCT source_name FROM articles ORDER BY source_name"
        )
        return [r[0] for r in await cur.fetchall()]


async def delete_old_articles(days: int):
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM articles WHERE fetched_at < ? AND (published_at < ? OR published_at IS NULL)",
            (cutoff, cutoff),
        )
        await db.commit()


async def get_article_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM articles")
        row = await cur.fetchone()
        return row[0] if row else 0
