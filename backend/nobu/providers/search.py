"""Web search. Real implementation uses the free `ddgs` (DuckDuckGo) library, no API key."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class DdgsSearch:
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from ddgs import DDGS

            rows = DDGS().text(query, max_results=max_results)
        except Exception:  # network/rate-limit errors: research degrades, never crashes
            return []
        return [
            SearchResult(r.get("title", ""), r.get("href", ""), r.get("body", ""))
            for r in rows
            if r.get("href")
        ]


class FakeSearch:
    def __init__(self, results: dict[str, list[SearchResult]] | None = None) -> None:
        self.results = results or {}
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        for key, rows in self.results.items():
            if key.lower() in query.lower():
                return rows[:max_results]
        return []
