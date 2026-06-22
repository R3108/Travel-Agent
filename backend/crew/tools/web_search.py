"""Web search tool.

Keyless by default: DuckDuckGo Instant Answers + Wikipedia (no signup needed).
If TAVILY_API_KEY / SERPER_API_KEY are set, those higher-quality providers are
used first. Final fallback is the model's own knowledge.
"""

from __future__ import annotations

import html as _html
import re
from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...config import get_settings

# Wikimedia's UA policy wants a descriptive agent + contact; a generic one 403s.
_WIKI_UA = {
    "User-Agent": "TripTrailers/1.0 (https://github.com/trip-trailers; trip-planner demo)",
    "Accept": "application/json",
}
# A browser-like UA reduces blocking on the keyless DuckDuckGo HTML endpoint.
_BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
_TAG_RE = re.compile(r"<[^>]+>")
_DDG_LINK_RE = re.compile(r'class="result__a"[^>]*>(.*?)</a>', re.S)
_DDG_SNIP_RE = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.S)


def _clean(fragment: str) -> str:
    return _html.unescape(_TAG_RE.sub("", fragment)).strip()


class WebSearchInput(BaseModel):
    query: str = Field(..., description="The search query.")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current travel information: attractions, events, "
        "opening hours, prices, advisories, neighbourhood guides, etc. "
        "Works with no API key (DuckDuckGo + Wikipedia). Input is a "
        "natural-language query; returns result snippets."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str) -> str:
        settings = get_settings()
        # Premium providers first if configured.
        try:
            if settings.tavily_api_key:
                return self._tavily(query, settings.tavily_api_key)
            if settings.serper_api_key:
                return self._serper(query, settings.serper_api_key)
        except Exception as exc:
            pass  # fall through to keyless

        # Keyless cascade: real web results (DDG HTML) -> DDG facts -> Wikipedia.
        parts: list[str] = []
        for provider in (self._duckduckgo_html, self._duckduckgo_ia, self._wikipedia):
            try:
                out = provider(query)
                if out:
                    parts.append(out)
            except Exception:
                continue
            if len(parts) >= 2:  # enough signal; stop early
                break

        if parts:
            return "\n\n".join(parts)
        return self._knowledge_fallback(query)

    # --- Premium providers ---
    def _tavily(self, query: str, key: str) -> str:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": 5, "include_answer": True},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = []
        if data.get("answer"):
            lines.append(f"Summary: {data['answer']}")
        for r in data.get("results", [])[:5]:
            lines.append(f"- {r.get('title', '')}: {r.get('content', '')[:300]} ({r.get('url', '')})")
        return "\n".join(lines) or self._knowledge_fallback(query)

    def _serper(self, query: str, key: str) -> str:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = [
            f"- {r.get('title', '')}: {r.get('snippet', '')} ({r.get('link', '')})"
            for r in data.get("organic", [])[:5]
        ]
        return "\n".join(lines) or self._knowledge_fallback(query)

    # --- Keyless providers ---
    def _duckduckgo_html(self, query: str) -> str:
        """Real organic web results from DuckDuckGo's no-JS HTML endpoint."""
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=_BROWSER_UA,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        body = resp.text
        titles = [_clean(t) for t in _DDG_LINK_RE.findall(body)]
        snippets = [_clean(s) for s in _DDG_SNIP_RE.findall(body)]
        lines = []
        for i, title in enumerate(titles[:6]):
            if not title:
                continue
            snip = snippets[i] if i < len(snippets) else ""
            lines.append(f"- {title}: {snip}".rstrip(": "))
        if not lines:
            return ""
        return "DuckDuckGo results:\n" + "\n".join(lines)

    def _duckduckgo_ia(self, query: str) -> str:
        """DuckDuckGo Instant Answers — good for entity facts."""
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            headers=_BROWSER_UA,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("AbstractText"):
            src = data.get("AbstractURL", "")
            return f"Summary: {data['AbstractText']} ({src})".strip()
        return ""

    def _wikipedia(self, query: str) -> str:
        # Full-text search for the most relevant pages.
        search = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": query,
                "format": "json", "srlimit": 3,
            },
            headers=_WIKI_UA,
            timeout=20,
        )
        search.raise_for_status()
        results = search.json().get("query", {}).get("search", [])
        if not results:
            return ""
        lines = []
        for r in results:
            title = r.get("title", "")
            snippet = _clean(r.get("snippet", ""))
            url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
            lines.append(f"- {title}: {snippet} ({url})")
        return "Wikipedia:\n" + "\n".join(lines)

    # --- Last resort ---
    def _knowledge_fallback(self, query: str) -> str:
        return (
            f"[Live search returned nothing for \"{query}\".] Answer from your own "
            "training knowledge, and tell the traveler to reconfirm time-sensitive "
            "details (prices, opening hours, event dates) closer to the trip."
        )
