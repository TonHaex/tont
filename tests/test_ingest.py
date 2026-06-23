import unittest

from ingest import chunk_text


class IngestTests(unittest.TestCase):
    def test_chunk_text_keeps_short_text_together(self) -> None:
        chunks = chunk_text("Eerste alinea.\n\nTweede alinea.", max_chars=100)

        self.assertEqual(chunks, ["Eerste alinea.\n\nTweede alinea."])

    def test_chunk_text_splits_long_text(self) -> None:
        chunks = chunk_text("a" * 250, max_chars=100, overlap=10)

        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
