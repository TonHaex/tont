import unittest

from crawler import (
    LinkParser,
    PageTextParser,
    crawl_local_posts,
    post_slug_from_filename,
    public_blog_url_for_post,
    markdown_title,
    markdown_to_text,
    normalize_text,
    read_post_manifest,
)


class CrawlerTests(unittest.TestCase):
    def test_normalize_text_compacts_whitespace(self) -> None:
        self.assertEqual(normalize_text(" Hallo   wereld\n\n\n test "), "Hallo wereld\n\ntest")

    def test_page_text_parser_ignores_script_content(self) -> None:
        parser = PageTextParser()
        parser.feed(
            """
            <html>
              <head><title>Ton Haex</title><script>secret()</script></head>
              <body><h1>Welkom</h1><p>Tekst over de site.</p></body>
            </html>
            """
        )

        self.assertEqual(parser.title, "Ton Haex")
        self.assertIn("Welkom", parser.text)
        self.assertNotIn("secret", parser.text)

    def test_link_parser_finds_markdown_links(self) -> None:
        parser = LinkParser()
        parser.feed('<a href="eerste-post.md">Eerste</a><a href="foto.jpg">Foto</a>')

        self.assertEqual(parser.links, ["eerste-post.md", "foto.jpg"])

    def test_markdown_title_uses_frontmatter(self) -> None:
        markdown = "---\ntitle: Mijn blogpost\n---\n\n# Andere titel\nTekst"

        self.assertEqual(markdown_title("https://tonhaex.nl/cms/posts/post.md", markdown), "Mijn blogpost")

    def test_markdown_to_text_removes_markdown_syntax(self) -> None:
        markdown = "---\ntitle: Test\n---\n\n# Kop\nEen **sterke** [link](https://example.com)."

        self.assertEqual(markdown_to_text(markdown), "Kop\nEen sterke link.")

    def test_read_post_manifest_accepts_relative_and_absolute_urls(self) -> None:
        path = self._write_temp_manifest("eerste.md\nhttps://tonhaex.nl/cms/posts/tweede.md\n")

        self.assertEqual(
            read_post_manifest(path, "https://tonhaex.nl/cms/posts/"),
            ["https://tonhaex.nl/cms/posts/eerste.md", "https://tonhaex.nl/cms/posts/tweede.md"],
        )

    def test_crawl_local_posts_reads_markdown_files(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "2025-01-01-lokale-post.md"
            path.write_text(
                "---\ntitle: Lokale post\ncategory: AI & Technologie\n---\n\n" + "Dit is lokale tekst. " * 8,
                encoding="utf-8",
            )

            pages = crawl_local_posts(temp_dir)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].title, "Lokale post")
        self.assertEqual(pages[0].url, "https://tonhaex.nl/blog/post/?item=lokale-post")

    def test_public_blog_url_for_post_uses_category_and_filename(self) -> None:
        from pathlib import Path

        markdown = "---\ntitle: Test\ncategory: Onderweg met Ton\n---\n\nTekst"

        self.assertEqual(
            public_blog_url_for_post(Path("2024-02-11-trip-in-lombok.md"), markdown),
            "https://tonhaex.nl/blog/post/?item=trip-in-lombok",
        )

    def test_post_slug_from_filename_removes_date(self) -> None:
        from pathlib import Path

        self.assertEqual(post_slug_from_filename(Path("2026-04-13_superintelligent_toekomst.md")), "superintelligent-toekomst")

    def _write_temp_manifest(self, content: str) -> str:
        import tempfile

        file = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        with file:
            file.write(content)
        return file.name


if __name__ == "__main__":
    unittest.main()
