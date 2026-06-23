import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from rag_engine import RagEngine, cosine_similarity


class FakeEmbeddings:
    def create(self, model: str, input):
        text = input if isinstance(input, str) else input[0]
        embedding = [1.0, 0.0] if "prijs" in text.lower() else [0.0, 1.0]
        return type("Response", (), {"data": [type("Item", (), {"embedding": embedding})()]})()


class FakeClient:
    embeddings = FakeEmbeddings()


class RagEngineTests(unittest.TestCase):
    def test_cosine_similarity(self) -> None:
        self.assertEqual(cosine_similarity([1, 0], [1, 0]), 1)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0)

    def test_search_returns_best_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "CREATE TABLE chunks (id INTEGER PRIMARY KEY, url TEXT, title TEXT, text TEXT, embedding TEXT)"
                )
                conn.execute(
                    "INSERT INTO chunks (url, title, text, embedding) VALUES (?, ?, ?, ?)",
                    ("https://tonhaex.nl/prijs", "Prijs", "Informatie over prijs", json.dumps([1.0, 0.0])),
                )
                conn.execute(
                    "INSERT INTO chunks (url, title, text, embedding) VALUES (?, ?, ?, ?)",
                    ("https://tonhaex.nl/contact", "Contact", "Informatie over contact", json.dumps([0.0, 1.0])),
                )

            engine = RagEngine(db_path=str(db_path), client=FakeClient())
            results = engine.search("Wat is de prijs?", limit=1)

            self.assertEqual(results[0].url, "https://tonhaex.nl/prijs")

    def test_search_uses_loaded_chunks_after_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "CREATE TABLE chunks (id INTEGER PRIMARY KEY, url TEXT, title TEXT, text TEXT, embedding TEXT)"
                )
                conn.execute(
                    "INSERT INTO chunks (url, title, text, embedding) VALUES (?, ?, ?, ?)",
                    ("https://tonhaex.nl/prijs", "Prijs", "Informatie over prijs", json.dumps([1.0, 0.0])),
                )

            engine = RagEngine(db_path=str(db_path), client=FakeClient())
            Path(db_path).unlink()
            results = engine.search("Wat is de prijs?", limit=1)

            self.assertEqual(results[0].title, "Prijs")


if __name__ == "__main__":
    unittest.main()
