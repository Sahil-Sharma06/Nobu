"""Fetch public web pages and reduce them to readable text."""

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol

import httpx

USER_AGENT = "NobuResearchBot/0.1 (personal job-outreach tool)"


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    text: str


class Fetcher(Protocol):
    def fetch(self, url: str) -> Page | None: ...


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()
        elif not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def html_to_page(url: str, html: str, max_chars: int = 20_000) -> Page:
    p = _TextExtractor()
    p.feed(html)
    return Page(url=url, title=p.title, text=" ".join(p.parts)[:max_chars])


class HttpFetcher:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> Page | None:
        try:
            r = httpx.get(
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        if "html" not in r.headers.get("content-type", "html"):
            return None
        return html_to_page(str(r.url), r.text)


class FakeFetcher:
    """Serves pages from a dict of url -> html. Unknown urls return None."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> Page | None:
        self.requested.append(url)
        html = self.pages.get(url)
        return html_to_page(url, html) if html is not None else None
