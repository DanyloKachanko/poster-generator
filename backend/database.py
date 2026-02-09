"""
PostgreSQL database module for poster generator.
Handles generation history, credit tracking, and scheduling.
"""

import json
import os
import asyncpg
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://poster:poster@localhost:5432/poster_generator",
)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    id SERIAL PRIMARY KEY,
    generation_id TEXT UNIQUE NOT NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    model_id TEXT NOT NULL,
    model_name TEXT,
    style TEXT,
    preset TEXT,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    num_images INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    api_credit_cost INTEGER DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS generated_images (
    id SERIAL PRIMARY KEY,
    generation_id TEXT NOT NULL,
    image_id TEXT,
    url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (generation_id) REFERENCES generations(generation_id)
);

CREATE TABLE IF NOT EXISTS credit_usage (
    id SERIAL PRIMARY KEY,
    generation_id TEXT NOT NULL,
    credits_used INTEGER NOT NULL,
    balance_after INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (generation_id) REFERENCES generations(generation_id)
);

CREATE TABLE IF NOT EXISTS product_analytics (
    id SERIAL PRIMARY KEY,
    printify_product_id TEXT NOT NULL,
    date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    favorites INTEGER DEFAULT 0,
    orders INTEGER DEFAULT 0,
    revenue_cents INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(printify_product_id, date)
);

CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generations_status ON generations(status);
CREATE INDEX IF NOT EXISTS idx_generations_style ON generations(style);
CREATE INDEX IF NOT EXISTS idx_generated_images_generation_id ON generated_images(generation_id);

CREATE TABLE IF NOT EXISTS etsy_tokens (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    etsy_user_id TEXT,
    shop_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_analytics_product ON product_analytics(printify_product_id);
CREATE INDEX IF NOT EXISTS idx_product_analytics_date ON product_analytics(date DESC);

CREATE TABLE IF NOT EXISTS scheduled_products (
    id SERIAL PRIMARY KEY,
    printify_product_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    image_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    scheduled_publish_at TEXT NOT NULL,
    published_at TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_scheduled_status ON scheduled_products(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_publish_at ON scheduled_products(scheduled_publish_at);

CREATE TABLE IF NOT EXISTS used_presets (
    id SERIAL PRIMARY KEY,
    preset_id TEXT NOT NULL,
    printify_product_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(preset_id, printify_product_id)
);

CREATE TABLE IF NOT EXISTS schedule_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    publish_times_json TEXT NOT NULL DEFAULT '["10:00","14:00","18:00"]',
    timezone TEXT NOT NULL DEFAULT 'US/Eastern',
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calendar_event_products (
    id SERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    printify_product_id TEXT NOT NULL,
    preset_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(event_id, printify_product_id)
);
CREATE INDEX IF NOT EXISTS idx_calendar_event ON calendar_event_products(event_id);
"""


async def init_db():
    """Initialize the database (create tables). Called on app startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)
        # Migrations
        try:
            await conn.execute(
                "ALTER TABLE scheduled_products ADD COLUMN image_url TEXT"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
    print(f"Database initialized (PostgreSQL)")


async def save_generation(
    generation_id: str,
    prompt: str,
    negative_prompt: Optional[str],
    model_id: str,
    model_name: Optional[str],
    style: Optional[str],
    preset: Optional[str],
    width: int,
    height: int,
    num_images: int,
    status: str = "PENDING",
) -> int:
    """Save a new generation record."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO generations
            (generation_id, prompt, negative_prompt, model_id, model_name,
             style, preset, width, height, num_images, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            generation_id, prompt, negative_prompt, model_id, model_name,
            style, preset, width, height, num_images, status,
        )
        return row["id"]


async def update_generation_status(
    generation_id: str,
    status: str,
    api_credit_cost: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Update generation status and credit cost."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status == "COMPLETE":
            await conn.execute(
                """
                UPDATE generations
                SET status = $1, api_credit_cost = $2, completed_at = NOW()
                WHERE generation_id = $3
                """,
                status, api_credit_cost, generation_id,
            )
        else:
            await conn.execute(
                """
                UPDATE generations
                SET status = $1, api_credit_cost = $2, error_message = $3
                WHERE generation_id = $4
                """,
                status, api_credit_cost, error_message, generation_id,
            )


async def save_generated_images(
    generation_id: str,
    images: List[Dict[str, str]],
) -> None:
    """Save generated images for a generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        for img in images:
            await conn.execute(
                """
                INSERT INTO generated_images (generation_id, image_id, url)
                VALUES ($1, $2, $3)
                """,
                generation_id, img.get("id"), img.get("url"),
            )


async def save_credit_usage(
    generation_id: str,
    credits_used: int,
    balance_after: Optional[int] = None,
) -> None:
    """Save credit usage record."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO credit_usage (generation_id, credits_used, balance_after)
            VALUES ($1, $2, $3)
            """,
            generation_id, credits_used, balance_after,
        )


async def get_generation(generation_id: str) -> Optional[Dict[str, Any]]:
    """Get a single generation by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM generations WHERE generation_id = $1",
            generation_id,
        )
        return dict(row) if row else None


async def get_generation_images(generation_id: str) -> List[Dict[str, Any]]:
    """Get all images for a generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM generated_images WHERE generation_id = $1",
            generation_id,
        )
        return [dict(row) for row in rows]


async def archive_generation(generation_id: str) -> bool:
    """Archive (soft-delete) a generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE generations SET archived = 1 WHERE generation_id = $1",
            generation_id,
        )
        return result != "UPDATE 0"


async def restore_generation(generation_id: str) -> bool:
    """Restore an archived generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE generations SET archived = 0 WHERE generation_id = $1",
            generation_id,
        )
        return result != "UPDATE 0"


async def get_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    style: Optional[str] = None,
    model_id: Optional[str] = None,
    archived: bool = False,
) -> Dict[str, Any]:
    """
    Get paginated generation history with optional filters.
    Returns dict with items, total count, and pagination info.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build WHERE clause
        conditions = ["g.archived = $1"]
        params: list = [1 if archived else 0]
        idx = 2

        if status:
            conditions.append(f"g.status = ${idx}")
            params.append(status)
            idx += 1
        if style:
            conditions.append(f"g.style = ${idx}")
            params.append(style)
            idx += 1
        if model_id:
            conditions.append(f"g.model_id = ${idx}")
            params.append(model_id)
            idx += 1

        where_clause = "WHERE " + " AND ".join(conditions)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM generations g {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Get items with images
        query = f"""
            SELECT g.*,
                   STRING_AGG(gi.url, ',') as image_urls,
                   STRING_AGG(gi.image_id, ',') as image_ids
            FROM generations g
            LEFT JOIN generated_images gi ON g.generation_id = gi.generation_id
            {where_clause}
            GROUP BY g.id
            ORDER BY g.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            item = dict(row)
            # Parse concatenated images
            if item.get("image_urls"):
                urls = item["image_urls"].split(",")
                ids = (item.get("image_ids") or "").split(",")
                item["images"] = [
                    {"url": url, "id": img_id}
                    for url, img_id in zip(urls, ids)
                ]
            else:
                item["images"] = []
            del item["image_urls"]
            if "image_ids" in item:
                del item["image_ids"]
            items.append(item)

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }


async def get_total_credits_used() -> int:
    """Get total API credits used."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(api_credit_cost), 0) FROM generations"
        )
        return val or 0


async def get_generation_stats() -> Dict[str, Any]:
    """Get generation statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_generations = await conn.fetchval(
            "SELECT COUNT(*) FROM generations"
        )

        status_rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM generations GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        total_credits = await conn.fetchval(
            "SELECT COALESCE(SUM(api_credit_cost), 0) FROM generations"
        )

        total_images = await conn.fetchval(
            "SELECT COUNT(*) FROM generated_images"
        )

        return {
            "total_generations": total_generations,
            "by_status": by_status,
            "total_credits_used": total_credits or 0,
            "total_images": total_images,
        }


# === Product Analytics ===

async def save_analytics(
    printify_product_id: str,
    date: str,
    views: int = 0,
    favorites: int = 0,
    orders: int = 0,
    revenue_cents: int = 0,
    notes: Optional[str] = None,
) -> None:
    """Upsert analytics entry for a product on a given date."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO product_analytics
            (printify_product_id, date, views, favorites, orders, revenue_cents, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT(printify_product_id, date) DO UPDATE SET
                views = EXCLUDED.views,
                favorites = EXCLUDED.favorites,
                orders = EXCLUDED.orders,
                revenue_cents = EXCLUDED.revenue_cents,
                notes = EXCLUDED.notes
            """,
            printify_product_id, date, views, favorites, orders, revenue_cents, notes,
        )


async def get_analytics_summary() -> List[Dict[str, Any]]:
    """Get aggregated analytics per product."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                printify_product_id,
                COALESCE(SUM(views), 0) as total_views,
                COALESCE(SUM(favorites), 0) as total_favorites,
                COALESCE(SUM(orders), 0) as total_orders,
                COALESCE(SUM(revenue_cents), 0) as total_revenue_cents,
                MAX(date) as latest_date
            FROM product_analytics
            GROUP BY printify_product_id
            """
        )
        return [dict(row) for row in rows]


async def get_product_analytics_history(
    printify_product_id: str,
) -> List[Dict[str, Any]]:
    """Get all analytics entries for a product, ordered by date."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM product_analytics
            WHERE printify_product_id = $1
            ORDER BY date DESC
            """,
            printify_product_id,
        )
        return [dict(row) for row in rows]


# === Etsy Tokens ===

async def save_etsy_tokens(
    access_token: str,
    refresh_token: str,
    expires_at: int,
    etsy_user_id: Optional[str] = None,
    shop_id: Optional[str] = None,
) -> None:
    """Save or update Etsy OAuth tokens (single row, id=1)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO etsy_tokens (id, access_token, refresh_token, expires_at, etsy_user_id, shop_id, updated_at)
            VALUES (1, $1, $2, $3, $4, $5, NOW())
            ON CONFLICT(id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                etsy_user_id = COALESCE(EXCLUDED.etsy_user_id, etsy_tokens.etsy_user_id),
                shop_id = COALESCE(EXCLUDED.shop_id, etsy_tokens.shop_id),
                updated_at = NOW()
            """,
            access_token, refresh_token, expires_at, etsy_user_id, shop_id,
        )


async def get_etsy_tokens() -> Optional[Dict[str, Any]]:
    """Get stored Etsy tokens."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM etsy_tokens WHERE id = 1")
        return dict(row) if row else None


async def delete_etsy_tokens() -> None:
    """Remove Etsy tokens (disconnect)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM etsy_tokens")


# === Scheduled Publishing ===

async def add_to_schedule(
    printify_product_id: str,
    title: str,
    scheduled_publish_at: str,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a product to the publish schedule."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO scheduled_products (printify_product_id, title, image_url, scheduled_publish_at)
            VALUES ($1, $2, $3, $4)
            """,
            printify_product_id, title, image_url, scheduled_publish_at,
        )
    return {
        "printify_product_id": printify_product_id,
        "title": title,
        "image_url": image_url,
        "status": "pending",
        "scheduled_publish_at": scheduled_publish_at,
    }


async def get_schedule_queue(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get scheduled products, optionally filtered by status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM scheduled_products WHERE status = $1 ORDER BY scheduled_publish_at",
                status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM scheduled_products ORDER BY scheduled_publish_at"
            )
        return [dict(row) for row in rows]


async def get_pending_due() -> List[Dict[str, Any]]:
    """Get pending products whose scheduled time has passed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM scheduled_products
            WHERE status = 'pending' AND scheduled_publish_at::timestamptz <= NOW()
            ORDER BY scheduled_publish_at
            """
        )
        return [dict(row) for row in rows]


async def update_schedule_status(
    printify_product_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Update status of a scheduled product."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status == "published":
            await conn.execute(
                """
                UPDATE scheduled_products
                SET status = $1, published_at = NOW()::text, error_message = NULL
                WHERE printify_product_id = $2
                """,
                status, printify_product_id,
            )
        else:
            await conn.execute(
                """
                UPDATE scheduled_products
                SET status = $1, error_message = $2
                WHERE printify_product_id = $3
                """,
                status, error_message, printify_product_id,
            )


async def remove_from_schedule(printify_product_id: str) -> bool:
    """Remove a product from the schedule."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM scheduled_products WHERE printify_product_id = $1",
            printify_product_id,
        )
        return result != "DELETE 0"


async def get_last_scheduled_time() -> Optional[str]:
    """Get the latest scheduled_publish_at in the queue."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT MAX(scheduled_publish_at) FROM scheduled_products"
        )
        return val


async def get_schedule_stats() -> Dict[str, Any]:
    """Get scheduling statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM scheduled_products WHERE status = 'pending'"
        )

        row = await conn.fetchrow(
            """
            SELECT scheduled_publish_at FROM scheduled_products
            WHERE status = 'pending'
            ORDER BY scheduled_publish_at
            LIMIT 1
            """
        )
        next_publish = row["scheduled_publish_at"] if row else None

        published_7d = await conn.fetchval(
            """
            SELECT COUNT(*) FROM scheduled_products
            WHERE status = 'published'
            AND published_at::timestamp >= NOW() - INTERVAL '7 days'
            """
        )

        failed = await conn.fetchval(
            "SELECT COUNT(*) FROM scheduled_products WHERE status = 'failed'"
        )

        return {
            "pending": pending,
            "next_publish_at": next_publish,
            "published_last_7_days": published_7d,
            "failed": failed,
        }


# === Used Presets ===

async def mark_preset_used(
    preset_id: str,
    printify_product_id: str,
    title: Optional[str] = None,
) -> None:
    """Record that a preset was used to create a product."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO used_presets (preset_id, printify_product_id, title)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            preset_id, printify_product_id, title,
        )


async def get_used_preset_ids() -> List[str]:
    """Get distinct preset IDs that have been used."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT preset_id FROM used_presets"
        )
        return [row["preset_id"] for row in rows]


async def get_preset_products(preset_id: str) -> List[Dict[str, Any]]:
    """Get all products created from a specific preset."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT printify_product_id, title, created_at
            FROM used_presets WHERE preset_id = $1
            ORDER BY created_at DESC
            """,
            preset_id,
        )
        return [dict(row) for row in rows]


# === Schedule Settings ===

_DEFAULT_PUBLISH_TIMES = ["10:00", "14:00", "18:00"]
_DEFAULT_TIMEZONE = "US/Eastern"


async def get_schedule_settings() -> Dict[str, Any]:
    """Get schedule configuration. Returns defaults if no row exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM schedule_settings WHERE id = 1")
        if row:
            d = dict(row)
            d["publish_times"] = json.loads(d["publish_times_json"])
            return d
        return {
            "id": 1,
            "publish_times_json": json.dumps(_DEFAULT_PUBLISH_TIMES),
            "publish_times": list(_DEFAULT_PUBLISH_TIMES),
            "timezone": _DEFAULT_TIMEZONE,
            "enabled": 1,
            "updated_at": None,
        }


async def save_schedule_settings(
    publish_times: List[str],
    timezone: str = _DEFAULT_TIMEZONE,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Upsert schedule settings (single-row, id=1)."""
    times_json = json.dumps(publish_times)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO schedule_settings (id, publish_times_json, timezone, enabled, updated_at)
            VALUES (1, $1, $2, $3, NOW())
            ON CONFLICT(id) DO UPDATE SET
                publish_times_json = EXCLUDED.publish_times_json,
                timezone = EXCLUDED.timezone,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            """,
            times_json, timezone, 1 if enabled else 0,
        )
    return await get_schedule_settings()


async def get_daily_summary_stats() -> Dict[str, Any]:
    """Get stats for the daily Telegram digest."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        published_yesterday = await conn.fetchval(
            """SELECT COUNT(*) FROM scheduled_products
               WHERE status = 'published'
               AND published_at::date = CURRENT_DATE - INTERVAL '1 day'"""
        )

        upcoming_today = await conn.fetchval(
            """SELECT COUNT(*) FROM scheduled_products
               WHERE status = 'pending'
               AND scheduled_publish_at::timestamptz::date = CURRENT_DATE"""
        )

    stats = await get_schedule_stats()
    stats["published_yesterday"] = published_yesterday
    stats["upcoming_today"] = upcoming_today
    return stats


# === Calendar Event Products ===

async def track_calendar_product(
    event_id: str,
    printify_product_id: str,
    preset_id: Optional[str] = None,
) -> None:
    """Link a product to a calendar event."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO calendar_event_products (event_id, printify_product_id, preset_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            event_id, printify_product_id, preset_id,
        )


async def get_calendar_event_products(event_id: str) -> List[Dict[str, Any]]:
    """Get products linked to a specific event."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_id, printify_product_id, preset_id, created_at
            FROM calendar_event_products WHERE event_id = $1
            ORDER BY created_at DESC
            """,
            event_id,
        )
        return [dict(row) for row in rows]


async def get_calendar_product_counts() -> Dict[str, int]:
    """Get product count per event_id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT event_id, COUNT(*) as count FROM calendar_event_products GROUP BY event_id"
        )
        return {row["event_id"]: row["count"] for row in rows}
