"""
Etsy Search Volume Validator via Etsy API v3

Uses GET /v3/application/listings/active?keywords={tag}&limit=1
to get total_results count as a proxy for search demand/competition.

Scoring tiers:
  > 10,000 results → high demand (high competition too)
  > 1,000 results  → medium demand (sweet spot)
  > 100 results    → low demand (niche)
  < 100 results    → probably not a real search term → replace

Two-level cache:
  1. In-memory dict (fast, per-process lifetime)
  2. PostgreSQL autocomplete_cache table (7-day TTL, persists across restarts)

Usage:
    from deps import etsy
    validator = EtsySearchValidator(etsy)
    result = await validator.check_tag("japanese wall art")
    results = await validator.check_tags(["japanese wall art", "zen decor"])
"""

import asyncio
from typing import Optional
import database as db


# Demand tiers based on total Etsy search results
DEMAND_TIERS = {
    "high": 10_000,      # > 10k results
    "medium": 1_000,     # 1k - 10k results
    "low": 100,          # 100 - 1k results
    "dead": 0,           # < 100 results — not a real search term
}


def classify_demand(total_results: int) -> str:
    """Classify search demand based on total Etsy results."""
    if total_results >= DEMAND_TIERS["high"]:
        return "high"
    elif total_results >= DEMAND_TIERS["medium"]:
        return "medium"
    elif total_results >= DEMAND_TIERS["low"]:
        return "low"
    else:
        return "dead"


class EtsySearchValidator:
    RATE_LIMIT_DELAY = 0.5  # seconds between Etsy API calls

    def __init__(self, etsy_api):
        """Initialize with an EtsyAPI instance (from deps.py)."""
        self._etsy = etsy_api
        self._cache: dict[str, dict] = {}

    async def check_tag(self, tag: str) -> dict:
        """Check a single tag against Etsy search results count.
        Uses in-memory cache → DB cache → Etsy API (with fallback)."""
        normalized = tag.strip().lower()

        # 1. In-memory cache
        if normalized in self._cache:
            return self._cache[normalized]

        # 2. DB cache (7-day TTL)
        try:
            cached = await db.get_cached_tag(normalized, "etsy")
            if cached:
                result = {
                    "tag": tag,
                    "found": cached["found"],
                    "total_results": cached["total_results"],
                    "demand": cached["demand"],
                    "source": "etsy",
                }
                self._cache[normalized] = result
                return result
        except Exception:
            pass  # DB not ready or table doesn't exist yet

        # 3. Hit Etsy API
        total_results = 0
        try:
            data = await self._etsy.search_listings(normalized, limit=1)
            total_results = data.get("count", 0)
        except Exception as e:
            return {
                "tag": tag,
                "found": False,
                "total_results": 0,
                "demand": "error",
                "error": str(e),
                "source": "etsy",
            }

        demand = classify_demand(total_results)
        found = demand != "dead"  # < 100 results = not found

        result = {
            "tag": tag,
            "found": found,
            "total_results": total_results,
            "demand": demand,
            "source": "etsy",
        }

        # Save to both caches
        self._cache[normalized] = result
        try:
            await db.save_cached_tag(
                tag=normalized, source="etsy", found=found,
                total_results=total_results, demand=demand,
            )
        except Exception:
            pass  # Non-critical — in-memory cache still works

        return result

    async def check_tags(self, tags: list[str]) -> dict:
        """Validate all tags against Etsy search with rate limiting."""
        results = []
        for i, tag in enumerate(tags):
            if i > 0:
                # Only delay if we need to hit the API (not cached)
                normalized = tag.strip().lower()
                if normalized not in self._cache:
                    try:
                        cached = await db.get_cached_tag(normalized, "etsy")
                        if not cached:
                            await asyncio.sleep(self.RATE_LIMIT_DELAY)
                    except Exception:
                        await asyncio.sleep(self.RATE_LIMIT_DELAY)
            result = await self.check_tag(tag)
            results.append(result)

        found_count = sum(1 for r in results if r["found"])
        total = len(tags)

        return {
            "total": total,
            "found": found_count,
            "not_found": total - found_count,
            "results": results,
            "score": round(found_count / total, 2) if total > 0 else 0,
            "source": "etsy",
        }

    def clear_cache(self):
        """Clear the in-memory cache."""
        self._cache.clear()
