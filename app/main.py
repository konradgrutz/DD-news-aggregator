import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
import scheduler
import scraper
import summarizer
import tts

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
_TTS_CACHE_DIR = _DATA_DIR / "tts_cache"
_TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _fmt_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    asyncio.create_task(scraper.run_all_sources())
    scheduler.start(scraper.run_all_sources)
    yield
    scheduler.stop()


app = FastAPI(title="Dresdner Nachrichten", lifespan=lifespan)
app.mount("/static", NoCacheStaticFiles(directory="static"), name="static")
app.mount("/tts-audio", StaticFiles(directory=str(_TTS_CACHE_DIR)), name="tts-audio")

templates = Jinja2Templates(directory="templates")
templates.env.filters["fmt_date"] = _fmt_date


@app.get("/health")
async def health():
    count = await db.get_article_count()
    return {"status": "ok", "articles": count}


@app.get("/")
async def index(request: Request, quelle: str = None):
    articles = await db.get_articles(source=quelle)
    sources = await db.get_sources()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "articles": articles,
            "sources": sources,
            "active_source": quelle,
        },
    )


@app.get("/artikel/{article_id}")
async def article_detail(request: Request, article_id: int):
    article = await db.get_article(article_id)
    if not article:
        raise HTTPException(404, "Artikel nicht gefunden")
    return templates.TemplateResponse(
        request,
        "article.html",
        {"article": article},
    )


@app.post("/summarize/{article_id}")
async def summarize(article_id: int):
    result = await summarizer.get_or_create_summary(article_id)
    if result is None:
        raise HTTPException(500, "Zusammenfassung fehlgeschlagen")
    return JSONResponse({"summary": result})


@app.post("/tts/{article_id}")
async def generate_tts(article_id: int, type: str = "content"):
    if type not in ("content", "summary"):
        raise HTTPException(400, "type muss 'content' oder 'summary' sein")
    urls = await tts.get_or_create_chunks(article_id, tts_type=type)
    if urls is None:
        raise HTTPException(500, "TTS-Generierung fehlgeschlagen")
    return JSONResponse({"urls": urls})


@app.get("/artikel/{article_id}/data")
async def article_data(article_id: int):
    article = await db.get_article(article_id)
    if not article:
        raise HTTPException(404, "Artikel nicht gefunden")
    return JSONResponse({
        "id": article["id"],
        "title": article["title"],
        "source_name": article["source_name"],
        "content": article["content"],
        "teaser": article["teaser"],
        "summary": article["summary"],
        "url": article["url"],
    })


@app.post("/scrape")
async def trigger_scrape():
    asyncio.create_task(scraper.run_all_sources())
    return JSONResponse({"status": "Scraping gestartet"})
