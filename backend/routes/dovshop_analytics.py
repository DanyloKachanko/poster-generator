"""DovShop analytics routes — proxy to production DovShop API with caching."""

import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

import database as db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dovshop-analytics"])

DOVSHOP_PROD_URL = os.getenv("DOVSHOP_PROD_URL", "https://dovshop.org/api")
DOVSHOP_API_KEY = os.getenv("DOVSHOP_API_KEY", "")

# In-memory cache: key -> (timestamp, data)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour


def _get_headers() -> dict[str, str]:
    return {"x-api-key": DOVSHOP_API_KEY}


def _cache_key(endpoint: str, params: dict) -> str:
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{endpoint}?{sorted_params}"


def _get_cached(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _get_stale_cached(key: str) -> Optional[dict]:
    """Return cached data regardless of TTL (for fallback on errors)."""
    entry = _cache.get(key)
    return entry[1] if entry else None


def _set_cache(key: str, data: dict) -> None:
    _cache[key] = (time.time(), data)


@router.get("/dovshop/analytics")
async def get_dovshop_analytics(days: int = 7, force: bool = False):
    """Fetch analytics summary from DovShop production API.

    Uses in-memory cache with 1-hour TTL. On failure, returns stale
    cached data if available, otherwise returns 502.
    """
    cache_key = _cache_key("analytics/summary", {"days": days})

    if not force:
        cached = _get_cached(cache_key)
        if cached is not None:
            return {**cached, "cached": True}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{DOVSHOP_PROD_URL}/analytics/summary",
                params={"days": days},
                headers=_get_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        _set_cache(cache_key, data)
        return {**data, "cached": False}

    except Exception as e:
        logger.warning("Failed to fetch DovShop analytics: %s", e)
        stale = _get_stale_cached(cache_key)
        if stale is not None:
            return {**stale, "cached": True, "stale": True}
        raise HTTPException(status_code=502, detail=f"DovShop analytics unavailable: {e}")


@router.post("/dovshop/analytics/sync")
async def sync_dovshop_analytics():
    """Manually trigger analytics sync: fetch 30-day summary and trigger aggregation."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch 30-day summary
            summary_resp = await client.get(
                f"{DOVSHOP_PROD_URL}/analytics/summary",
                params={"days": 30},
                headers=_get_headers(),
            )
            summary_resp.raise_for_status()
            summary = summary_resp.json()

            # Trigger aggregation
            agg_resp = await client.post(
                f"{DOVSHOP_PROD_URL}/analytics/aggregate",
                headers=_get_headers(),
            )
            agg_resp.raise_for_status()

        # Cache the 30-day summary
        cache_key = _cache_key("analytics/summary", {"days": 30})
        _set_cache(cache_key, summary)

        return {
            "status": "ok",
            "period": summary.get("period", "30d"),
            "pageViews": summary.get("pageViews", 0),
        }

    except Exception as e:
        logger.error("DovShop analytics sync failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Analytics sync failed: {e}")


@router.get("/dovshop/analytics/poster/{printify_product_id}")
async def get_poster_analytics(printify_product_id: str, days: int = 30):
    """Per-poster DovShop analytics.

    Looks up dovshop_product_id from local DB via printify_product_id,
    then fetches analytics from DovShop production API.
    """
    product = await db.get_product_by_printify_id(printify_product_id)
    if not product:
        return _empty_poster_stats()

    dovshop_id = product.get("dovshop_product_id")
    if not dovshop_id:
        return _empty_poster_stats()

    cache_key = _cache_key(f"analytics/poster/{dovshop_id}", {"days": days})
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{DOVSHOP_PROD_URL}/analytics/poster/{dovshop_id}",
                params={"days": days},
                headers=_get_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        _set_cache(cache_key, data)
        return {**data, "cached": False}

    except Exception as e:
        logger.warning("Failed to fetch poster analytics for %s: %s", dovshop_id, e)
        stale = _get_stale_cached(cache_key)
        if stale is not None:
            return {**stale, "cached": True, "stale": True}
        return _empty_poster_stats()


def _empty_poster_stats() -> dict:
    return {
        "pageViews": 0,
        "clicks": 0,
        "impressions": 0,
        "cached": False,
    }
