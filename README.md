# TonGPT voor tonhaex.nl

Een eenvoudige SiteGPT-achtige chatbot voor tonhaex.nl, zonder SiteGPT. De bot crawlt de sitemap, maakt embeddings, bewaart die in SQLite en beantwoordt vragen via een FastAPI endpoint.

## Bestanden

- `crawler.py`: leest `sitemap.xml` plus Markdown-posts uit `https://tonhaex.nl/cms/posts/` en slaat inhoud op in `data/pages.jsonl`
- `ingest.py`: maakt chunks en embeddings, en slaat die op in SQLite
- `rag_engine.py`: zoekt relevante stukken tekst en maakt een antwoord
- `api.py`: FastAPI server met `/chat`
- `widget.js`: JavaScript chatwidget voor de website
- `tests/`: kleine tests voor tekstverwerking en zoeklogica

## Installatie

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Vul in `.env` je OpenAI API key in:

```bash
OPENAI_API_KEY=...
```

## Kennisbank bouwen

```bash
mkdir -p data
python3 crawler.py --sitemap https://tonhaex.nl/sitemap.xml --out data/pages.jsonl
python3 ingest.py --pages data/pages.jsonl --db data/tongpt.sqlite3
```

De crawler neemt standaard ook Markdown-bestanden mee uit:

```text
https://tonhaex.nl/cms/posts/
```

Als die map geen publieke lijst toont, maak dan een bestand `posts.txt` met per regel een `.md`-bestand. Zie `posts.example.txt`.

Voorbeeld:

```text
eerste-blogpost.md
tweede-blogpost.md
https://tonhaex.nl/cms/posts/derde-blogpost.md
```

Daarna crawl je zo:

```bash
python3 crawler.py --posts-manifest posts.txt
```

Je kunt de Markdown-bestanden ook met Transmit downloaden naar een lokale map, bijvoorbeeld `data/posts`. Daarna neem je ze zo mee:

```bash
python3 crawler.py --no-posts --local-posts-dir data/posts --out data/pages.jsonl --pause 5
```

Bij lokale Markdown-bestanden gebruikt TonGPT publieke bloglinks als bron, bijvoorbeeld:

```text
https://tonhaex.nl/blog/post/?item=naam-van-artikel
```

Wil je alleen de gewone sitemap crawlen:

```bash
python3 crawler.py --no-posts
```

Voor een snelle proef:

```bash
python3 crawler.py --limit 5 --posts-limit 5
python3 ingest.py
```

## API starten

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Test:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Waar gaat tonhaex.nl over?"}'
```

## Render deploy

Voor Render is dit project voorbereid met `render.yaml`.

Gebruik als service:

```text
Web Service
```

Render gebruikt:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn api:app --host 0.0.0.0 --port $PORT
```

Zet bij Environment Variables minimaal:

```text
OPENAI_API_KEY=...
```

De lokale kennisbank staat in `data/tongpt.sqlite3`.

## Widget gebruiken in RapidWeaver Elements

Plaats `widget.js` op je site of server en laad hem in de pagina. Voorbeeld:

```html
<script>
  window.TonGPTConfig = {
    apiUrl: "https://jouw-api-domein.nl/chat",
    title: "TonGPT",
    intro: "Stel een vraag over tonhaex.nl."
  };
</script>
<script src="/pad/naar/widget.js" defer></script>
```

## Gedragsregel

TonGPT gebruikt alleen context uit tonhaex.nl. Als het antwoord niet in de gevonden context staat, hoort TonGPT eerlijk te zeggen:

> Ik kan dit niet met zekerheid terugvinden op tonhaex.nl.

## Instellingen

Deze variabelen kun je aanpassen:

- `OPENAI_API_KEY`: verplicht voor embeddings en antwoorden
- `OPENAI_EMBEDDING_MODEL`: standaard `text-embedding-3-small`
- `OPENAI_CHAT_MODEL`: standaard `gpt-4.1-mini`
- `TONGPT_DB_PATH`: standaard `data/tongpt.sqlite3`
- `TONGPT_ALLOWED_ORIGINS`: toegestane websites voor de API, standaard `https://tonhaex.nl,http://localhost:8000`

## Tests

```bash
pytest
```

Of zonder pytest:

```bash
python3 -m unittest discover -s tests
```
