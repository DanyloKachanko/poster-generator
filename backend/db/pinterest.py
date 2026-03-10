"""Pinterest tokens, boards, pins, and analytics queries."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from db.connection import get_pool

logger = logging.getLogger(__name__)


# === Tokens ===

async def save_pinterest_tokens(
    access_token: str,
    refresh_token: str,
    expires_at: int,
    username: Optional[str] = None,
) -> None:
    """Save or update Pinterest OAuth tokens (single row, id=1)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pinterest_tokens (id, access_token, refresh_token, expires_at, username, updated_at)
            VALUES (1, $1, $2, $3, $4, NOW())
            ON CONFLICT(id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                username = COALESCE(EXCLUDED.username, pinterest_tokens.username),
                updated_at = NOW()
            """,
            access_token, refresh_token, expires_at, username,
        )


async def get_pinterest_tokens() -> Optional[Dict[str, Any]]:
    """Get stored Pinterest tokens."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pinterest_tokens WHERE id = 1")
        return dict(row) if row else None


async def delete_pinterest_tokens() -> None:
    """Remove Pinterest tokens (disconnect)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pinterest_tokens")


# === Boards ===

async def save_pinterest_boards(boards: list) -> int:
    """Upsert boards from Pinterest API response. Returns count saved."""
    pool = await get_pool()
    count = 0
    async with pool.acquire() as conn:
        for b in boards:
            await conn.execute(
                """
                INSERT INTO pinterest_boards (board_id, name, description, pin_count, privacy, synced_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT(board_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    pin_count = EXCLUDED.pin_count,
                    privacy = EXCLUDED.privacy,
                    synced_at = NOW()
                """,
                b.get("id", ""),
                b.get("name", ""),
                b.get("description", ""),
                b.get("pin_count", 0) or 0,
                b.get("privacy", "PUBLIC"),
            )
            count += 1
    return count


async def get_pinterest_boards() -> List[Dict[str, Any]]:
    """Get all cached boards."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM pinterest_boards ORDER BY name")
        return [dict(r) for r in rows]


# === Pins ===

async def queue_pin(
    product_id: int,
    board_id: str,
    title: str,
    description: str,
    image_url: str,
    link: str,
    alt_text: str = "",
    scheduled_at: Optional[datetime] = None,
) -> int:
    """Queue a pin for publishing. Returns the DB id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO pinterest_pins
                (product_id, board_id, title, description, image_url, link, alt_text, status, scheduled_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued', $8)
            RETURNING id
            """,
            product_id, board_id, title, description, image_url, link, alt_text, scheduled_at,
        )
        return row["id"]


async def get_queued_pins(limit: int = 20) -> List[Dict[str, Any]]:
    """Get pins ready for publishing (queued, ordered by scheduled_at)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM pinterest_pins
            WHERE status = 'queued'
            ORDER BY scheduled_at ASC NULLS FIRST, created_at ASC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def mark_pin_published(pin_db_id: int, pinterest_pin_id: str) -> None:
    """Mark a pin as successfully published."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE pinterest_pins
            SET status = 'published', pin_id = $2, published_at = NOW()
            WHERE id = $1
            """,
            pin_db_id, pinterest_pin_id,
        )


async def mark_pin_failed(pin_db_id: int, error_message: str) -> None:
    """Mark a pin as failed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE pinterest_pins SET status = 'failed', error_message = $2 WHERE id = $1",
            pin_db_id, error_message,
        )


async def get_published_pins(limit: int = 50) -> List[Dict[str, Any]]:
    """Get published pins with analytics data."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT pp.*, p.title AS product_title, p.image_url AS product_image_url
            FROM pinterest_pins pp
            LEFT JOIN products p ON p.id = pp.product_id
            WHERE pp.status = 'published'
            ORDER BY pp.published_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def update_pin_analytics(
    pin_db_id: int,
    impressions: int,
    saves: int,
    clicks: int,
    outbound_clicks: int,
) -> None:
    """Update analytics counters for a pin."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE pinterest_pins
            SET impressions = $2, saves = $3, clicks = $4, outbound_clicks = $5,
                last_analytics_sync = NOW()
            WHERE id = $1
            """,
            pin_db_id, impressions, saves, clicks, outbound_clicks,
        )


async def get_pin_stats_summary() -> Dict[str, Any]:
    """Get aggregate Pinterest stats."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'published') AS total_published,
                COUNT(*) FILTER (WHERE status = 'queued') AS total_queued,
                COALESCE(SUM(impressions), 0) AS total_impressions,
                COALESCE(SUM(saves), 0) AS total_saves,
                COALESCE(SUM(clicks), 0) AS total_clicks,
                COALESCE(SUM(outbound_clicks), 0) AS total_outbound_clicks
            FROM pinterest_pins
            """
        )
        return dict(row)


async def get_pins_for_product(product_id: int) -> List[Dict[str, Any]]:
    """Get all pins for a specific product."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM pinterest_pins WHERE product_id = $1 ORDER BY created_at DESC",
            product_id,
        )
        return [dict(r) for r in rows]


async def delete_pin_record(pin_db_id: int) -> None:
    """Delete a pin record from DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pinterest_pins WHERE id = $1", pin_db_id)


# === Products for pin creation ===

async def get_pinterest_products() -> List[Dict[str, Any]]:
    """Get all published products with mockup count and pin statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.id,
                p.title,
                p.image_url,
                p.printify_product_id,
                p.etsy_listing_id,
                p.source_image_id,
                COALESCE(m.mockup_count, 0) AS mockup_count,
                COALESCE(pq.queued_pins, 0) AS queued_pins,
                COALESCE(pp.published_pins, 0) AS published_pins
            FROM products p
            LEFT JOIN (
                SELECT image_id, COUNT(*) AS mockup_count
                FROM image_mockups
                WHERE dovshop_included = true AND etsy_cdn_url IS NOT NULL
                GROUP BY image_id
            ) m ON m.image_id = p.source_image_id
            LEFT JOIN (
                SELECT product_id, COUNT(*) AS queued_pins
                FROM pinterest_pins WHERE status = 'queued'
                GROUP BY product_id
            ) pq ON pq.product_id = p.id
            LEFT JOIN (
                SELECT product_id, COUNT(*) AS published_pins
                FROM pinterest_pins WHERE status = 'published'
                GROUP BY product_id
            ) pp ON pp.product_id = p.id
            WHERE p.etsy_listing_id IS NOT NULL
              AND p.archived = 0
              AND p.status = 'published'
            ORDER BY p.created_at DESC
        """)
        return [dict(r) for r in rows]


async def get_next_mockup_url(product_id: int, source_image_id: int) -> Optional[str]:
    """Pick the next mockup URL via round-robin for a product.

    Selects the least-used mockup (by count of existing pins using that URL),
    breaking ties by rank order. Returns the etsy_cdn_url.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT im.etsy_cdn_url
            FROM image_mockups im
            LEFT JOIN (
                SELECT image_url, COUNT(*) AS use_count
                FROM pinterest_pins
                WHERE product_id = $1
                GROUP BY image_url
            ) used ON used.image_url = im.etsy_cdn_url
            WHERE im.image_id = $2
              AND im.dovshop_included = true
              AND im.etsy_cdn_url IS NOT NULL
            ORDER BY COALESCE(used.use_count, 0) ASC, im.rank ASC
            LIMIT 1
        """, product_id, source_image_id)
        return row["etsy_cdn_url"] if row else None
