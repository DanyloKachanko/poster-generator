"""
SQLite database module for poster generator.
Handles generation history and credit tracking.
"""

import json
import os
import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# Database file path — override via DATABASE_PATH env var for production
_default_path = str(Path(__file__).parent / "poster_generator.db")
DB_PATH = Path(os.environ.get("DATABASE_PATH", _default_path))
# Ensure parent directory exists (e.g. /app/data/)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS generated_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    image_id TEXT,
    url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(generation_id)
);

CREATE TABLE IF NOT EXISTS credit_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id TEXT NOT NULL,
    credits_used INTEGER NOT NULL,
    balance_after INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id) REFERENCES generations(generation_id)
);

CREATE TABLE IF NOT EXISTS product_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    printify_product_id TEXT NOT NULL,
    date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    favorites INTEGER DEFAULT 0,
    orders INTEGER DEFAULT 0,
    revenue_cents INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_product_analytics_product ON product_analytics(printify_product_id);
CREATE INDEX IF NOT EXISTS idx_product_analytics_date ON product_analytics(date DESC);

CREATE TABLE IF NOT EXISTS scheduled_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    printify_product_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    scheduled_publish_at TEXT NOT NULL,
    published_at TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_scheduled_status ON scheduled_products(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_publish_at ON scheduled_products(scheduled_publish_at);

CREATE TABLE IF NOT EXISTS used_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preset_id TEXT NOT NULL,
    printify_product_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(preset_id, printify_product_id)
);

CREATE TABLE IF NOT EXISTS schedule_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    publish_times_json TEXT NOT NULL DEFAULT '["10:00","14:00","18:00"]',
    timezone TEXT NOT NULL DEFAULT 'US/Eastern',
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


MIGRATIONS = [
    # Add archived column if it doesn't exist
    """
    ALTER TABLE generations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;
    """,
]


def init_db():
    """Initialize the database synchronously (for startup)."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    # Run migrations (ignore errors for already-applied ones)
    for migration in MIGRATIONS:
        try:
            conn.execute(migration)
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


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
    status: str = "PENDING"
) -> int:
    """Save a new generation record."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO generations
            (generation_id, prompt, negative_prompt, model_id, model_name,
             style, preset, width, height, num_images, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (generation_id, prompt, negative_prompt, model_id, model_name,
             style, preset, width, height, num_images, status)
        )
        await db.commit()
        return cursor.lastrowid


async def update_generation_status(
    generation_id: str,
    status: str,
    api_credit_cost: int = 0,
    error_message: Optional[str] = None
) -> None:
    """Update generation status and credit cost."""
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "COMPLETE":
            await db.execute(
                """
                UPDATE generations
                SET status = ?, api_credit_cost = ?, completed_at = CURRENT_TIMESTAMP
                WHERE generation_id = ?
                """,
                (status, api_credit_cost, generation_id)
            )
        else:
            await db.execute(
                """
                UPDATE generations
                SET status = ?, api_credit_cost = ?, error_message = ?
                WHERE generation_id = ?
                """,
                (status, api_credit_cost, error_message, generation_id)
            )
        await db.commit()


async def save_generated_images(
    generation_id: str,
    images: List[Dict[str, str]]
) -> None:
    """Save generated images for a generation."""
    async with aiosqlite.connect(DB_PATH) as db:
        for img in images:
            await db.execute(
                """
                INSERT INTO generated_images (generation_id, image_id, url)
                VALUES (?, ?, ?)
                """,
                (generation_id, img.get("id"), img.get("url"))
            )
        await db.commit()


async def save_credit_usage(
    generation_id: str,
    credits_used: int,
    balance_after: Optional[int] = None
) -> None:
    """Save credit usage record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO credit_usage (generation_id, credits_used, balance_after)
            VALUES (?, ?, ?)
            """,
            (generation_id, credits_used, balance_after)
        )
        await db.commit()


async def get_generation(generation_id: str) -> Optional[Dict[str, Any]]:
    """Get a single generation by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM generations WHERE generation_id = ?",
            (generation_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_generation_images(generation_id: str) -> List[Dict[str, Any]]:
    """Get all images for a generation."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM generated_images WHERE generation_id = ?",
            (generation_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def archive_generation(generation_id: str) -> bool:
    """Archive (soft-delete) a generation."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE generations SET archived = 1 WHERE generation_id = ?",
            (generation_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def restore_generation(generation_id: str) -> bool:
    """Restore an archived generation."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE generations SET archived = 0 WHERE generation_id = ?",
            (generation_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    style: Optional[str] = None,
    model_id: Optional[str] = None,
    archived: bool = False
) -> Dict[str, Any]:
    """
    Get paginated generation history with optional filters.
    Returns dict with items, total count, and pagination info.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Build WHERE clause
        conditions = ["g.archived = ?"]
        params: list = [1 if archived else 0]

        if status:
            conditions.append("g.status = ?")
            params.append(status)
        if style:
            conditions.append("g.style = ?")
            params.append(style)
        if model_id:
            conditions.append("g.model_id = ?")
            params.append(model_id)

        where_clause = "WHERE " + " AND ".join(conditions)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM generations g {where_clause}"
        cursor = await db.execute(count_query, params)
        total_row = await cursor.fetchone()
        total = total_row["total"] if total_row else 0

        # Get items with images
        query = f"""
            SELECT g.*,
                   GROUP_CONCAT(gi.url) as image_urls,
                   GROUP_CONCAT(gi.image_id) as image_ids
            FROM generations g
            LEFT JOIN generated_images gi ON g.generation_id = gi.generation_id
            {where_clause}
            GROUP BY g.id
            ORDER BY g.created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

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
            "has_more": offset + limit < total
        }


async def get_total_credits_used() -> int:
    """Get total API credits used."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(api_credit_cost), 0) as total FROM generations"
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_generation_stats() -> Dict[str, Any]:
    """Get generation statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Total generations
        cursor = await db.execute("SELECT COUNT(*) as total FROM generations")
        total_row = await cursor.fetchone()
        total_generations = total_row["total"] if total_row else 0

        # By status
        cursor = await db.execute(
            "SELECT status, COUNT(*) as count FROM generations GROUP BY status"
        )
        status_rows = await cursor.fetchall()
        by_status = {row["status"]: row["count"] for row in status_rows}

        # Total credits
        cursor = await db.execute(
            "SELECT COALESCE(SUM(api_credit_cost), 0) as total FROM generations"
        )
        credits_row = await cursor.fetchone()
        total_credits = credits_row["total"] if credits_row else 0

        # Total images
        cursor = await db.execute("SELECT COUNT(*) as total FROM generated_images")
        images_row = await cursor.fetchone()
        total_images = images_row["total"] if images_row else 0

        return {
            "total_generations": total_generations,
            "by_status": by_status,
            "total_credits_used": total_credits,
            "total_images": total_images
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO product_analytics
            (printify_product_id, date, views, favorites, orders, revenue_cents, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(printify_product_id, date) DO UPDATE SET
                views = excluded.views,
                favorites = excluded.favorites,
                orders = excluded.orders,
                revenue_cents = excluded.revenue_cents,
                notes = excluded.notes
            """,
            (printify_product_id, date, views, favorites, orders, revenue_cents, notes),
        )
        await db.commit()


async def get_analytics_summary() -> List[Dict[str, Any]]:
    """Get aggregated analytics per product."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
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
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_product_analytics_history(
    printify_product_id: str,
) -> List[Dict[str, Any]]:
    """Get all analytics entries for a product, ordered by date."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM product_analytics
            WHERE printify_product_id = ?
            ORDER BY date DESC
            """,
            (printify_product_id,),
        )
        rows = await cursor.fetchall()
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO etsy_tokens (id, access_token, refresh_token, expires_at, etsy_user_id, shop_id, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                etsy_user_id = COALESCE(excluded.etsy_user_id, etsy_tokens.etsy_user_id),
                shop_id = COALESCE(excluded.shop_id, etsy_tokens.shop_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (access_token, refresh_token, expires_at, etsy_user_id, shop_id),
        )
        await db.commit()


async def get_etsy_tokens() -> Optional[Dict[str, Any]]:
    """Get stored Etsy tokens."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM etsy_tokens WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def delete_etsy_tokens() -> None:
    """Remove Etsy tokens (disconnect)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM etsy_tokens")
        await db.commit()


# === Scheduled Publishing ===

async def add_to_schedule(
    printify_product_id: str,
    title: str,
    scheduled_publish_at: str,
) -> Dict[str, Any]:
    """Add a product to the publish schedule."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO scheduled_products (printify_product_id, title, scheduled_publish_at)
            VALUES (?, ?, ?)
            """,
            (printify_product_id, title, scheduled_publish_at),
        )
        await conn.commit()
    return {
        "printify_product_id": printify_product_id,
        "title": title,
        "status": "pending",
        "scheduled_publish_at": scheduled_publish_at,
    }


async def get_schedule_queue(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get scheduled products, optionally filtered by status."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if status:
            cursor = await conn.execute(
                "SELECT * FROM scheduled_products WHERE status = ? ORDER BY scheduled_publish_at",
                (status,),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM scheduled_products ORDER BY scheduled_publish_at"
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_pending_due() -> List[Dict[str, Any]]:
    """Get pending products whose scheduled time has passed."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT * FROM scheduled_products
            WHERE status = 'pending' AND scheduled_publish_at <= datetime('now')
            ORDER BY scheduled_publish_at
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_schedule_status(
    printify_product_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Update status of a scheduled product."""
    async with aiosqlite.connect(DB_PATH) as conn:
        if status == "published":
            await conn.execute(
                """
                UPDATE scheduled_products
                SET status = ?, published_at = datetime('now'), error_message = NULL
                WHERE printify_product_id = ?
                """,
                (status, printify_product_id),
            )
        else:
            await conn.execute(
                """
                UPDATE scheduled_products
                SET status = ?, error_message = ?
                WHERE printify_product_id = ?
                """,
                (status, error_message, printify_product_id),
            )
        await conn.commit()


async def remove_from_schedule(printify_product_id: str) -> bool:
    """Remove a product from the schedule."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "DELETE FROM scheduled_products WHERE printify_product_id = ?",
            (printify_product_id,),
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_last_scheduled_time() -> Optional[str]:
    """Get the latest scheduled_publish_at in the queue."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT MAX(scheduled_publish_at) as last_time FROM scheduled_products"
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None


async def get_schedule_stats() -> Dict[str, Any]:
    """Get scheduling statistics."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Pending count
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM scheduled_products WHERE status = 'pending'"
        )
        pending = (await cursor.fetchone())["cnt"]

        # Next publish time
        cursor = await conn.execute(
            """
            SELECT scheduled_publish_at FROM scheduled_products
            WHERE status = 'pending'
            ORDER BY scheduled_publish_at
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
        next_publish = row["scheduled_publish_at"] if row else None

        # Published in last 7 days
        cursor = await conn.execute(
            """
            SELECT COUNT(*) as cnt FROM scheduled_products
            WHERE status = 'published'
            AND published_at >= datetime('now', '-7 days')
            """
        )
        published_7d = (await cursor.fetchone())["cnt"]

        # Failed count
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM scheduled_products WHERE status = 'failed'"
        )
        failed = (await cursor.fetchone())["cnt"]

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
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT OR IGNORE INTO used_presets (preset_id, printify_product_id, title)
            VALUES (?, ?, ?)
            """,
            (preset_id, printify_product_id, title),
        )
        await conn.commit()


async def get_used_preset_ids() -> List[str]:
    """Get distinct preset IDs that have been used."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT DISTINCT preset_id FROM used_presets"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_preset_products(preset_id: str) -> List[Dict[str, Any]]:
    """Get all products created from a specific preset."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT printify_product_id, title, created_at
            FROM used_presets WHERE preset_id = ?
            ORDER BY created_at DESC
            """,
            (preset_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# === Schedule Settings ===

_DEFAULT_PUBLISH_TIMES = ["10:00", "14:00", "18:00"]
_DEFAULT_TIMEZONE = "US/Eastern"


async def get_schedule_settings() -> Dict[str, Any]:
    """Get schedule configuration. Returns defaults if no row exists."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM schedule_settings WHERE id = 1")
        row = await cursor.fetchone()
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
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO schedule_settings (id, publish_times_json, timezone, enabled, updated_at)
            VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                publish_times_json = excluded.publish_times_json,
                timezone = excluded.timezone,
                enabled = excluded.enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (times_json, timezone, 1 if enabled else 0),
        )
        await conn.commit()
    return await get_schedule_settings()


async def get_daily_summary_stats() -> Dict[str, Any]:
    """Get stats for the daily Telegram digest."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Published yesterday
        cursor = await conn.execute(
            """SELECT COUNT(*) FROM scheduled_products
               WHERE status = 'published'
               AND date(published_at) = date('now', '-1 day')"""
        )
        published_yesterday = (await cursor.fetchone())[0]

        # Upcoming today (pending, scheduled for today)
        cursor = await conn.execute(
            """SELECT COUNT(*) FROM scheduled_products
               WHERE status = 'pending'
               AND date(scheduled_publish_at) = date('now')"""
        )
        upcoming_today = (await cursor.fetchone())[0]

    stats = await get_schedule_stats()
    stats["published_yesterday"] = published_yesterday
    stats["upcoming_today"] = upcoming_today
    return stats
