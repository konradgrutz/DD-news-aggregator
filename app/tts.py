import asyncio
import logging
import os
from pathlib import Path

from gtts import gTTS

from db import get_article

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(os.getenv("DATA_DIR", "./data")) / "tts_cache"
_CHUNK_CHARS = 300  # Zielgröße pro Chunk


def _cache_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def split_into_chunks(text: str, max_chars: int = _CHUNK_CHARS) -> list[str]:
    """Teilt Text an Zeilenumbrüchen auf, max_chars pro Chunk."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    chunks, current, current_len = [], [], 0
    for line in lines:
        if current_len + len(line) > max_chars and current:
            chunks.append("\n".join(current))
            current, current_len = [line], len(line)
        else:
            current.append(line)
            current_len += len(line)
    if current:
        chunks.append("\n".join(current))
    return chunks


def _generate_mp3(text: str, path: Path):
    tts = gTTS(text=text, lang="de", slow=False)
    tts.save(str(path))


async def get_or_create_chunks(article_id: int, tts_type: str = "content") -> list[str] | None:
    """Gibt Liste von Chunk-URLs zurück; fehlende Chunks werden parallel generiert."""
    article = await get_article(article_id)
    if not article:
        return None

    text = (
        (article.get("content") or article.get("teaser") or article.get("title"))
        if tts_type == "content"
        else article.get("summary")
    )
    if not text:
        return None

    chunks_text = split_into_chunks(text)
    if not chunks_text:
        return None

    cache = _cache_dir()
    loop = asyncio.get_event_loop()
    tasks = []
    urls = []

    for i, chunk in enumerate(chunks_text):
        filename = f"{article_id}_{tts_type}_{i}.mp3"
        mp3_path = cache / filename
        urls.append(f"/tts-audio/{filename}")
        if not mp3_path.exists():
            tasks.append(loop.run_in_executor(None, _generate_mp3, chunk, mp3_path))

    if tasks:
        logger.info("Generiere %d TTS-Chunks parallel (Artikel %d, %s)…", len(tasks), article_id, tts_type)
        await asyncio.gather(*tasks)
        logger.info("TTS-Chunks fertig für Artikel %d", article_id)

    return urls
