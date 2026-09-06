# DD News Aggregator

Webapp (Python/FastAPI), die lokale Dresdner News aus verschiedenen Quellen
(z.B. neustadt-ticker.de) sammelt, optional per Google Gemini zusammenfasst
und per gTTS vorliest.

## Setup

### 1. Repo klonen

```
git clone git@github.com:konradgrutz/DD-news-aggregator.git
cd DD-news-aggregator
```

### 2. Umgebungsvariablen anlegen

```
cp .env.example .env
```

`.env` ausfüllen:

| Variable | Beschreibung | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API-Key (für Zusammenfassungen) | — |
| `GEMINI_MODEL` | Gemini-Modell | `gemini-3.1-flash-lite` |
| `SCRAPE_INTERVAL_HOURS` | Abstand zwischen Scrape-Läufen | `4` |
| `ARTICLE_RETENTION_DAYS` | Wie lange Artikel aufbewahrt werden | `7` |

### 3a. Starten mit Docker Compose (empfohlen)

```
docker compose up -d --build
```

Läuft danach unter http://localhost:5005. Daten (SQLite-DB + TTS-Cache)
liegen persistent unter `./data`.

### 3b. Alternativ lokal ohne Docker

```
cd app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DATA_DIR=./data
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Läuft danach unter http://localhost:8080.

## Struktur

- `app/scraper.py` – Sammelt Artikel von den konfigurierten Quellen (`app/sources.py`)
- `app/summarizer.py` – Zusammenfassung via Gemini API
- `app/tts.py` – Text-to-Speech via gTTS, Cache unter `data/tts_cache/`
- `app/scheduler.py` – Periodisches Scraping (APScheduler)
- `app/db.py` – SQLite-Anbindung (`data/news.db`)
- `app/main.py` – FastAPI-App & Routen
