"""Competitor intelligence queries — shops, listings, snapshots, stats."""

from typing import Optional, List, Dict, Any
from db.connection import get_pool


async def save_competitor(
    etsy_shop_id: str,
    shop_name: str,
    shop_url: str = "",
    icon_url: str = "",
    total_listings: int = 0,
    rating: float = 0,
    total_reviews: int = 0,
    country: str = "",
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO competitors
               (etsy_shop_id, shop_name, shop_url, icon_url, total_listings, rating, total_reviews, country)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING *""",
            etsy_shop_id, shop_name, shop_url, icon_url, total_listings, rating, total_reviews, country,
        )
        return dict(row)


async def get_competitors(is_active: int = 1) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM competitors WHERE is_active = $1 ORDER BY created_at DESC",
            is_active,
        )
        return [dict(row) for row in rows]


async def get_competitor(competitor_id: int) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM competitors WHERE id = $1", competitor_id)
        return dict(row) if row else None


async def get_competitor_by_shop_id(etsy_shop_id: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM competitors WHERE etsy_shop_id = $1", etsy_shop_id
        )
        return dict(row) if row else None


async def archive_competitor(competitor_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE competitors SET is_active = 0, updated_at = NOW() WHERE id = $1",
            competitor_id,
        )


async def reactivate_competitor(competitor_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE competitors SET is_active = 1, updated_at = NOW() WHERE id = $1",
            competitor_id,
        )


async def update_competitor(competitor_id: int, **fields) -> None:
    pool = await get_pool()
    allowed = {"total_listings", "rating", "total_reviews", "icon_url", "shop_name"}
    parts = []
    values = []
    idx = 2  # $1 is competitor_id
    for key, val in fields.items():
        if key in allowed:
            parts.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1
    if not parts:
        return
    parts.append("updated_at = NOW()")
    sql = f"UPDATE competitors SET {', '.join(parts)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(sql, competitor_id, *values)


async def upsert_competitor_listing(
    competitor_id: int,
    etsy_listing_id: str,
    title: str = "",
    description: str = "",
    tags: str = "[]",
    price_cents: int = 0,
    currency: str = "USD",
    views: int = 0,
    favorites: int = 0,
    image_url: str = "",
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO competitor_listings
               (competitor_id, etsy_listing_id, title, description, tags, price_cents, currency, views, favorites, image_url)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
               ON CONFLICT(etsy_listing_id) DO UPDATE SET
                 title = EXCLUDED.title,
                 description = EXCLUDED.description,
                 tags = EXCLUDED.tags,
                 price_cents = EXCLUDED.price_cents,
                 currency = EXCLUDED.currency,
                 views = EXCLUDED.views,
                 favorites = EXCLUDED.favorites,
                 image_url = EXCLUDED.image_url,
                 synced_at = NOW()
               RETURNING *""",
            competitor_id, etsy_listing_id, title, description, tags,
            price_cents, currency, views, favorites, image_url,
        )
        return dict(row)


async def get_competitor_listings(
    competitor_id: int,
    sort_by: str = "favorites",
    sort_dir: str = "DESC",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    allowed_sort = {"views", "favorites", "price_cents", "title", "synced_at"}
    if sort_by not in allowed_sort:
        sort_by = "favorites"
    sort_dir = "ASC" if sort_dir.upper() == "ASC" else "DESC"
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM competitor_listings WHERE competitor_id = $1 ORDER BY {sort_by} {sort_dir} LIMIT $2 OFFSET $3",
            competitor_id, limit, offset,
        )
        return [dict(row) for row in rows]


async def get_competitor_listings_count(competitor_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM competitor_listings WHERE competitor_id = $1",
            competitor_id,
        )


async def save_competitor_listing_stats(
    listing_id: int, date: str, views: int, favorites: int, price_cents: int
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO competitor_listing_stats (listing_id, date, views, favorites, price_cents)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT(listing_id, date) DO UPDATE SET
                 views = EXCLUDED.views,
                 favorites = EXCLUDED.favorites,
                 price_cents = EXCLUDED.price_cents""",
            listing_id, date, views, favorites, price_cents,
        )


async def save_competitor_snapshot(
    competitor_id: int, snapshot_date: str, total_listings: int, avg_price_cents: int, top_tags: str = "[]"
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO competitor_snapshots (competitor_id, snapshot_date, total_listings, avg_price_cents, top_tags)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT(competitor_id, snapshot_date) DO UPDATE SET
                 total_listings = EXCLUDED.total_listings,
                 avg_price_cents = EXCLUDED.avg_price_cents,
                 top_tags = EXCLUDED.top_tags""",
            competitor_id, snapshot_date, total_listings, avg_price_cents, top_tags,
        )


async def get_competitor_stats(competitor_id: int) -> Dict[str, Any]:
    """Get aggregated stats for a competitor: listings count, top tags."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        listings_count = await conn.fetchval(
            "SELECT COUNT(*) FROM competitor_listings WHERE competitor_id = $1",
            competitor_id,
        )
        # Get latest snapshot for top_tags
        snapshot = await conn.fetchrow(
            "SELECT * FROM competitor_snapshots WHERE competitor_id = $1 ORDER BY snapshot_date DESC LIMIT 1",
            competitor_id,
        )
        return {
            "listings_count": listings_count or 0,
            "top_tags": snapshot["top_tags"] if snapshot else "[]",
            "last_snapshot_date": snapshot["snapshot_date"] if snapshot else None,
        }
