"""SEO refresh log and autocomplete cache queries."""

from typing import Optional, List, Dict, Any
from db.connection import get_pool


async def save_seo_refresh_log(
    printify_product_id: str,
    etsy_listing_id: str,
    reason: str,
    old_title: str,
    new_title: str,
    old_tags: Optional[List[str]] = None,
    new_tags: Optional[List[str]] = None,
    status: str = "updated",
) -> int:
    """Log an SEO refresh action."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO seo_refresh_log
                (printify_product_id, etsy_listing_id, reason, old_title, new_title, old_tags, new_tags, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            printify_product_id, etsy_listing_id, reason, old_title, new_title,
            old_tags, new_tags, status,
        )
        return row["id"]


async def get_seo_refresh_candidates(
    min_days_since_publish: int = 14,
    max_views: int = 5,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Find published products with low views that haven't been refreshed recently.

    Candidates: published, have etsy_listing_id, low analytics views,
    not refreshed in last 7 days.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.printify_product_id, p.etsy_listing_id, p.title, p.description,
                   p.enabled_sizes, p.created_at,
                   COALESCE(a.total_views, 0) as total_views,
                   COALESCE(a.total_favorites, 0) as total_favorites
            FROM products p
            LEFT JOIN (
                SELECT printify_product_id,
                       SUM(views) as total_views,
                       SUM(favorites) as total_favorites
                FROM analytics
                GROUP BY printify_product_id
            ) a ON a.printify_product_id = p.printify_product_id
            WHERE p.status = 'published'
              AND p.etsy_listing_id IS NOT NULL
              AND p.created_at < NOW() - INTERVAL '1 day' * $1
              AND p.printify_product_id NOT IN (
                  SELECT printify_product_id FROM seo_refresh_log
                  WHERE created_at > NOW() - INTERVAL '7 days'
              )
              AND COALESCE(a.total_views, 0) <= $2
            ORDER BY COALESCE(a.total_views, 0) ASC, p.created_at ASC
            LIMIT $3
            """,
            min_days_since_publish, max_views, limit,
        )
        return [dict(r) for r in rows]


# === Autocomplete Cache ===

async def get_cached_tag(tag: str, source: str = "etsy") -> Optional[Dict[str, Any]]:
    """Get a cached autocomplete result if it exists and hasn't expired."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM autocomplete_cache
               WHERE tag = $1 AND source = $2 AND expires_at > NOW()""",
            tag.lower().strip(), source
        )
        return dict(row) if row else None


async def save_cached_tag(tag: str, source: str, found: bool, total_results: int = 0,
                          demand: str = "dead", position: Optional[int] = None,
                          suggestions_json: Optional[str] = None):
    """Upsert a tag validation result into the cache with 7-day TTL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO autocomplete_cache (tag, source, found, total_results, demand, position, suggestions_json, checked_at, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW() + INTERVAL '7 days')
               ON CONFLICT (tag, source) DO UPDATE SET
                   found = EXCLUDED.found,
                   total_results = EXCLUDED.total_results,
                   demand = EXCLUDED.demand,
                   position = EXCLUDED.position,
                   suggestions_json = EXCLUDED.suggestions_json,
                   checked_at = NOW(),
                   expires_at = NOW() + INTERVAL '7 days'""",
            tag.lower().strip(), source, found, total_results, demand, position, suggestions_json
        )


async def get_cache_stats() -> Dict[str, Any]:
    """Get autocomplete cache statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE expires_at > NOW()) AS valid,
                COUNT(*) FILTER (WHERE expires_at <= NOW()) AS expired,
                COUNT(*) FILTER (WHERE source = 'etsy') AS etsy_count,
                COUNT(*) FILTER (WHERE source = 'google') AS google_count
               FROM autocomplete_cache"""
        )
        return dict(row) if row else {"total": 0, "valid": 0, "expired": 0}


async def clear_expired_cache():
    """Delete expired cache entries."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM autocomplete_cache WHERE expires_at <= NOW()"
        )
        return result
