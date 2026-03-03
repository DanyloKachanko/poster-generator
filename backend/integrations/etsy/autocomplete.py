"""
Search Volume Validator via Google Autocomplete

Checks keywords against Google's autocomplete API as a proxy for search volume.
If a keyword appears in autocomplete, real people search for it.
Etsy's own suggest endpoint is blocked by DataDome, so we use Google as a
reliable, free alternative that still correlates with buyer search behavior.

Usage:
    checker = EtsyAutocompleteChecker()
    result = await checker.check_keyword("japanese wall art")
    results = await checker.check_tags(["japanese wall art", "zen decor", "serene nature piece"])
"""

import asyncio
from typing import Optional
import httpx


class EtsyAutocompleteChecker:
    # Google autocomplete — reliable, no anti-bot
    SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
    RATE_LIMIT_DELAY = 0.3  # seconds between requests (Google is more lenient)

    def __init__(self):
        self._cache: dict[str, list[str]] = {}

    async def _fetch_suggestions(self, query: str) -> list[str]:
        """Fetch autocomplete suggestions from Google for a query."""
        normalized = query.strip().lower()
        if normalized in self._cache:
            return self._cache[normalized]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.SUGGEST_URL,
                    params={"client": "firefox", "q": normalized},
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                # Google returns: [query, [suggestions], ...]
                suggestions = []
                if isinstance(data, list) and len(data) > 1:
                    suggestions = [
                        s.lower() for s in data[1]
                        if isinstance(s, str)
                    ]

                self._cache[normalized] = suggestions
                return suggestions
        except Exception:
            return []

    def _is_match(self, tag: str, suggestions: list[str]) -> bool:
        """Check if tag matches any suggestion (exact or close variant)."""
        tag_lower = tag.strip().lower()
        if not suggestions:
            return False
        for suggestion in suggestions:
            if tag_lower == suggestion:
                return True
            if tag_lower in suggestion:
                return True
        return False

    def _find_position(self, tag: str, suggestions: list[str]) -> Optional[int]:
        """Find position of tag in suggestions (1-indexed), or None."""
        tag_lower = tag.strip().lower()
        for i, suggestion in enumerate(suggestions):
            if tag_lower == suggestion or tag_lower in suggestion:
                return i + 1
        return None

    async def check_keyword(self, keyword: str) -> dict:
        """Check a single keyword against autocomplete."""
        suggestions = await self._fetch_suggestions(keyword)
        found = self._is_match(keyword, suggestions)
        position = self._find_position(keyword, suggestions) if found else None
        return {
            "keyword": keyword,
            "found": found,
            "position": position,
            "suggestions": suggestions[:10],
        }

    async def get_suggestions(self, query: str) -> list[str]:
        """Get raw autocomplete suggestions for a query."""
        return await self._fetch_suggestions(query)

    async def check_tags(self, tags: list[str]) -> dict:
        """Check all tags against autocomplete with rate limiting."""
        results = []
        for i, tag in enumerate(tags):
            if i > 0:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)
            result = await self.check_keyword(tag)
            results.append({
                "tag": tag,
                "found": result["found"],
                "position": result["position"],
                "suggestions": result["suggestions"],
            })

        found_count = sum(1 for r in results if r["found"])
        total = len(tags)
        return {
            "total": total,
            "found": found_count,
            "not_found": total - found_count,
            "results": results,
            "score": round(found_count / total, 2) if total > 0 else 0,
        }

    def clear_cache(self):
        """Clear the suggestions cache."""
        self._cache.clear()
