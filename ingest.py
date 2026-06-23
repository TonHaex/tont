from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


DEFAULT_DB_PATH = "data/tongpt.sqlite3"
DEFAULT_PAGES_PATH = "data/pages.jsonl"
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


@dataclass
class Chunk:
    url: str
    title: str
    text: str


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_url ON chunks(url)")


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 180) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        current = paragraph

        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars - overlap :]

    if current:
        chunks.append(current)

    return chunks


def load_pages(path: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    with open(path, encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            page = json.loads(line)
            for text in chunk_text(page["text"]):
                chunks.append(Chunk(url=page["url"], title=page.get("title", ""), text=text))
    return chunks


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def ingest(pages_path: str, db_path: str, batch_size: int = 64) -> int:
    init_db(db_path)
    chunks = load_pages(pages_path)
    client = OpenAI()

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM chunks")
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            embeddings = embed_texts(client, [chunk.text for chunk in batch])
            conn.executemany(
                "INSERT INTO chunks (url, title, text, embedding) VALUES (?, ?, ?, ?)",
                [
                    (chunk.url, chunk.title, chunk.text, json.dumps(embedding))
                    for chunk, embedding in zip(batch, embeddings, strict=True)
                ],
            )
            print(f"Stored {min(start + batch_size, len(chunks))}/{len(chunks)} chunks")
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create TonGPT embeddings in SQLite")
    parser.add_argument("--pages", default=DEFAULT_PAGES_PATH)
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    count = ingest(args.pages, args.db, batch_size=args.batch_size)
    print(f"Ready: {count} chunks stored in {args.db}")


if __name__ == "__main__":
    main()
