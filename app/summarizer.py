import asyncio
import logging
import os

import google.generativeai as genai

from db import get_article, update_article

logger = logging.getLogger(__name__)

_model = None
_MAX_INPUT_CHARS = 6000

_PROMPT = """\
Fasse folgenden Nachrichtenartikel auf Deutsch zusammen. \
Schreibe etwa {target_words} Wörter (ungefähr die Hälfte des Originals). \
Bleibe sachlich und präzise. Gib nur die Zusammenfassung zurück, keine Einleitung.

Titel: {title}

Text:
{text}"""


def _get_model():
    global _model
    if _model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt")
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        _model = genai.GenerativeModel(model_name)
    return _model


def _call_gemini(title: str, text: str) -> str:
    model = _get_model()
    word_count = len(text.split())
    target_words = max(60, word_count // 2)
    prompt = _PROMPT.format(title=title, text=text[:_MAX_INPUT_CHARS], target_words=target_words)
    response = model.generate_content(prompt)
    return response.text.strip()


async def get_or_create_summary(article_id: int) -> str | None:
    article = await get_article(article_id)
    if not article:
        return None

    if article.get("summary"):
        return article["summary"]

    text = article.get("content") or article.get("teaser")
    if not text:
        return None

    try:
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None, _call_gemini, article["title"], text
        )
        await update_article(article_id, summary=summary)
        return summary
    except Exception as e:
        logger.error("Zusammenfassung fehlgeschlagen für Artikel %d: %s", article_id, e)
        return None
