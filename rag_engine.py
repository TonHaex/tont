from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import dataclass

from openai import OpenAI

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


DEFAULT_DB_PATH = os.getenv("TONGPT_DB_PATH", "data/tongpt.sqlite3")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

SYSTEM_PROMPT = """Je bent TonGPT, een vriendelijke website-assistent voor tonhaex.nl.
Beantwoord vragen alleen met informatie uit de meegegeven context van tonhaex.nl.
Als het antwoord niet in de context staat, zeg dan eerlijk dat je het niet op tonhaex.nl kunt vinden.
Houd antwoorden kort, helder en vriendelijk. Verzin geen feiten, prijzen, beloftes of contactgegevens.
Antwoord in dezelfde taal als de gebruiker, tenzij de gebruiker iets anders vraagt."""


@dataclass
class SearchResult:
    url: str
    title: str
    text: str
    score: float


@dataclass
class StoredChunk:
    url: str
    title: str
    text: str
    embedding: list[float]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class RagEngine:
    def __init__(self, db_path: str = DEFAULT_DB_PATH, client: OpenAI | None = None) -> None:
        self.db_path = db_path
        self.client = client or OpenAI()
        self.chunks = self.load_chunks()

    def load_chunks(self) -> list[StoredChunk]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT url, title, text, embedding FROM chunks").fetchall()

        return [
            StoredChunk(
                url=url,
                title=title,
                text=text,
                embedding=json.loads(raw_embedding),
            )
            for url, title, text, raw_embedding in rows
        ]

    def embed_query(self, question: str) -> list[float]:
        response = self.client.embeddings.create(model=EMBEDDING_MODEL, input=question)
        return response.data[0].embedding

    def search(self, question: str, limit: int = 5) -> list[SearchResult]:
        query_embedding = self.embed_query(question)
        results: list[SearchResult] = []

        for chunk in self.chunks:
            score = cosine_similarity(query_embedding, chunk.embedding)
            results.append(SearchResult(url=chunk.url, title=chunk.title, text=chunk.text, score=score))

        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    def answer(self, question: str) -> dict:
        results = self.search(question)
        useful_results = [result for result in results if result.score >= 0.18]

        if not useful_results:
            return {
                "answer": "Ik kan dit niet met zekerheid terugvinden op tonhaex.nl.",
                "sources": [],
            }

        context = "\n\n".join(
            f"Bron: {result.title or result.url}\nURL: {result.url}\nTekst:\n{result.text}"
            for result in useful_results
        )
        response = self.client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context van tonhaex.nl:\n{context}\n\nVraag: {question}",
                },
            ],
        )

        sources = []
        seen_urls = set()
        for result in useful_results:
            if result.url in seen_urls:
                continue
            sources.append({"title": result.title or result.url, "url": result.url})
            seen_urls.add(result.url)

        return {
            "answer": response.choices[0].message.content.strip(),
            "sources": sources[:3],
        }
