from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

import certifi


DEFAULT_SITEMAP_URL = "https://tonhaex.nl/sitemap.xml"
DEFAULT_POSTS_URL = "https://tonhaex.nl/cms/posts/"
DEFAULT_BLOG_POST_URL = "https://tonhaex.nl/blog/post/"
USER_AGENT = "TonGPTBot/0.1 (+https://tonhaex.nl)"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


@dataclass
class CrawledPage:
    url: str
    title: str
    text: str


class PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "section", "article"}:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._hidden_depth:
            self._hidden_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "li", "h1", "h2", "h3", "h4"}:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if not clean:
            return
        if self._in_title:
            self._title_parts.append(clean)
        if self._hidden_depth == 0:
            self._text_parts.append(clean)

    @property
    def title(self) -> str:
        return normalize_text(" ".join(self._title_parts))

    @property
    def text(self) -> str:
        return normalize_text(" ".join(self._text_parts))


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.links.append(unescape(value))


def normalize_text(value: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in value.splitlines()]
    value = "\n".join(lines)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def fetch_text(url: str, timeout: int = 20, retries: int = 3, retry_pause: float = 8.0) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except HTTPError as exc:
            if exc.code != 429 or attempt == retries:
                raise
            wait_seconds = retry_pause * attempt
            print(f"[wacht] {url}: te veel verzoeken, opnieuw over {wait_seconds:.0f} sec", file=sys.stderr)
            time.sleep(wait_seconds)

    raise RuntimeError(f"Kon {url} niet ophalen")


def sitemap_urls(sitemap_url: str) -> list[str]:
    xml_text = fetch_text(sitemap_url)
    root = ET.fromstring(xml_text)
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"

    if root.tag.endswith("sitemapindex"):
        urls: list[str] = []
        for loc in root.findall(f".//{namespace}loc"):
            child_url = loc.text.strip() if loc.text else ""
            if child_url:
                urls.extend(sitemap_urls(child_url))
        return urls

    return [
        loc.text.strip()
        for loc in root.findall(f".//{namespace}loc")
        if loc.text and loc.text.strip()
    ]


def is_allowed_page(url: str, base_domain: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != base_domain:
        return False
    lowered = parsed.path.lower()
    blocked_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".pdf",
        ".zip",
        ".xml",
    )
    return not lowered.endswith(blocked_extensions)


def parse_page(url: str) -> CrawledPage | None:
    html = fetch_text(url)
    parser = PageTextParser()
    parser.feed(html)
    if len(parser.text) < 80:
        return None
    return CrawledPage(url=url, title=parser.title, text=parser.text)


def markdown_title(url: str, markdown: str) -> str:
    title = frontmatter_value(markdown, "title")
    if title:
        return normalize_text(title)

    heading_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    if heading_match:
        return normalize_text(heading_match.group(1))

    filename = Path(unquote(urlparse(url).path)).stem
    return filename.replace("-", " ").replace("_", " ").strip().title()


def frontmatter_value(markdown: str, key: str) -> str | None:
    frontmatter = re.match(r"^---\s*\n(.*?)\n---\s*\n", markdown, flags=re.DOTALL)
    if not frontmatter:
        return None

    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", frontmatter.group(1), flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip("\"'")


def public_blog_url_for_post(path: Path, markdown: str, blog_post_url: str = DEFAULT_BLOG_POST_URL) -> str:
    post_slug = post_slug_from_filename(path)
    separator = "&" if "?" in blog_post_url else "?"
    return f"{blog_post_url}{separator}item={post_slug}"


def post_slug_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^\d{4}[-_]\d{2}[-_]\d{2}[-_]?", "", stem)
    return slugify(stem)


def slugify(value: str) -> str:
    value = value.lower().replace("&", " en ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def markdown_to_text(markdown: str) -> str:
    markdown = re.sub(r"^---\s*\n.*?\n---\s*\n", "", markdown, flags=re.DOTALL)
    markdown = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
    markdown = re.sub(r"`([^`]+)`", r"\1", markdown)
    markdown = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", markdown)
    markdown = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    markdown = re.sub(r"^#{1,6}\s*", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"^[>\-*+]\s+", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"\*\*([^*]+)\*\*", r"\1", markdown)
    markdown = re.sub(r"\*([^*]+)\*", r"\1", markdown)
    markdown = re.sub(r"__([^_]+)__", r"\1", markdown)
    markdown = re.sub(r"_([^_]+)_", r"\1", markdown)
    return normalize_text(markdown)


def parse_markdown_post(url: str) -> CrawledPage | None:
    markdown = fetch_text(url)
    return parse_markdown_content(url, markdown)


def parse_markdown_content(url: str, markdown: str) -> CrawledPage | None:
    text = markdown_to_text(markdown)
    if len(text) < 80:
        return None
    return CrawledPage(url=url, title=markdown_title(url, markdown), text=text)


def markdown_urls(posts_url: str) -> list[str]:
    index_text = fetch_text(posts_url)
    parser = LinkParser()
    parser.feed(index_text)
    urls: list[str] = []
    for link in parser.links:
        full_url = urljoin(posts_url, link)
        if urlparse(full_url).path.lower().endswith(".md") and full_url not in urls:
            urls.append(full_url)
    return urls


def read_post_manifest(path_or_url: str, base_url: str) -> list[str]:
    if path_or_url.startswith(("http://", "https://")):
        text = fetch_text(path_or_url)
    else:
        text = Path(path_or_url).read_text(encoding="utf-8")

    urls: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        full_url = clean if clean.startswith(("http://", "https://")) else urljoin(base_url, clean)
        if full_url not in urls:
            urls.append(full_url)
    return urls


def crawl_posts(
    posts_url: str,
    posts_manifest: str | None = None,
    limit: int | None = None,
    pause: float = 2.0,
) -> list[CrawledPage]:
    if posts_manifest:
        urls = read_post_manifest(posts_manifest, posts_url)
    else:
        urls = [posts_url] if urlparse(posts_url).path.lower().endswith(".md") else markdown_urls(posts_url)
    if limit is not None:
        urls = urls[:limit]

    pages: list[CrawledPage] = []
    for index, url in enumerate(urls, start=1):
        try:
            page = parse_markdown_post(url)
        except Exception as exc:
            print(f"[warn] {url}: {exc}", file=sys.stderr)
            continue

        if page:
            pages.append(page)
            print(f"[md {index}/{len(urls)}] {url}")
        time.sleep(pause)
    return pages


def crawl_local_posts(posts_dir: str, blog_post_url: str = DEFAULT_BLOG_POST_URL) -> list[CrawledPage]:
    directory = Path(posts_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Map bestaat niet: {posts_dir}")

    pages: list[CrawledPage] = []
    files = sorted(directory.rglob("*.md"))
    for index, path in enumerate(files, start=1):
        markdown = path.read_text(encoding="utf-8")
        url = public_blog_url_for_post(path, markdown, blog_post_url=blog_post_url)
        page = parse_markdown_content(url, markdown)
        if page:
            pages.append(page)
            print(f"[local md {index}/{len(files)}] {path}")
    return pages


def crawl(
    sitemap_url: str,
    posts_url: str | None = DEFAULT_POSTS_URL,
    posts_manifest: str | None = None,
    local_posts_dir: str | None = None,
    blog_post_url: str = DEFAULT_BLOG_POST_URL,
    limit: int | None = None,
    posts_limit: int | None = None,
    pause: float = 2.0,
) -> list[CrawledPage]:
    base_domain = urlparse(sitemap_url).netloc or urlparse(DEFAULT_SITEMAP_URL).netloc
    urls = []
    for raw_url in sitemap_urls(sitemap_url):
        full_url = urljoin(sitemap_url, raw_url)
        if is_allowed_page(full_url, base_domain) and full_url not in urls:
            urls.append(full_url)

    if limit is not None:
        urls = urls[:limit]

    pages: list[CrawledPage] = []
    for index, url in enumerate(urls, start=1):
        try:
            page = parse_page(url)
        except Exception as exc:
            print(f"[warn] {url}: {exc}", file=sys.stderr)
            continue

        if page:
            pages.append(page)
            print(f"[{index}/{len(urls)}] {url}")
        time.sleep(pause)

    if posts_url:
        try:
            posts = crawl_posts(posts_url, posts_manifest=posts_manifest, limit=posts_limit, pause=pause)
            pages.extend(posts)
        except Exception as exc:
            print(f"[warn] Markdown-posts niet opgehaald via {posts_url}: {exc}", file=sys.stderr)

    if local_posts_dir:
        try:
            pages.extend(crawl_local_posts(local_posts_dir, blog_post_url=blog_post_url))
        except Exception as exc:
            print(f"[warn] Lokale Markdown-posts niet opgehaald uit {local_posts_dir}: {exc}", file=sys.stderr)

    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl tonhaex.nl via sitemap.xml en Markdown-posts")
    parser.add_argument("--sitemap", default=DEFAULT_SITEMAP_URL)
    parser.add_argument("--posts-url", default=DEFAULT_POSTS_URL)
    parser.add_argument("--posts-manifest", default=None)
    parser.add_argument("--local-posts-dir", default=None)
    parser.add_argument("--blog-post-url", default=DEFAULT_BLOG_POST_URL)
    parser.add_argument("--no-posts", action="store_true")
    parser.add_argument("--out", default="data/pages.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--posts-limit", type=int, default=None)
    parser.add_argument("--pause", type=float, default=2.0)
    args = parser.parse_args()

    pages = crawl(
        args.sitemap,
        posts_url=None if args.no_posts else args.posts_url,
        posts_manifest=args.posts_manifest,
        local_posts_dir=args.local_posts_dir,
        blog_post_url=args.blog_post_url,
        limit=args.limit,
        posts_limit=args.posts_limit,
        pause=args.pause,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as file:
        for page in pages:
            file.write(json.dumps(asdict(page), ensure_ascii=False) + "\n")
    print(f"Saved {len(pages)} pages to {args.out}")


if __name__ == "__main__":
    main()
