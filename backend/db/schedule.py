"""Schedule queue, schedule settings, and calendar event queries."""

import json
from typing import Optional, List, Dict, Any
from db.connection import get_pool


async def add_to_schedule(
    printify_product_id: str,
    title: str,
    scheduled_publish_at: str,
    image_url: Optional[str] = None,
    etsy_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a product to the publish schedule."""
    pool = await get_pool()
    metadata_json = json.dumps(etsy_metadata) if etsy_metadata else "{}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO scheduled_products (printify_product_id, title, image_url, scheduled_publish_at, etsy_metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            printify_product_id, title, image_url, scheduled_publish_at, metadata_json,
        )
    return {
        "printify_product_id": printify_product_id,
        "title": title,
        "image_url": image_url,
        "status": "pending",
        "scheduled_publish_at": scheduled_publish_at,
        "etsy_metadata": etsy_metadata or {},
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
            "preferred_primary_camera": "",
            "default_shipping_profile_id": None,
            "default_shop_section_id": None,
            "updated_at": None,
        }


async def save_schedule_settings(
    publish_times: List[str],
    timezone: str = _DEFAULT_TIMEZONE,
    enabled: bool = True,
    preferred_primary_camera: str = "",
    default_shipping_profile_id: Optional[int] = None,
    default_shop_section_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Upsert schedule settings (single-row, id=1)."""
    times_json = json.dumps(publish_times)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO schedule_settings (id, publish_times_json, timezone, enabled, preferred_primary_camera,
                                           default_shipping_profile_id, default_shop_section_id, updated_at)
            VALUES (1, $1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT(id) DO UPDATE SET
                publish_times_json = EXCLUDED.publish_times_json,
                timezone = EXCLUDED.timezone,
                enabled = EXCLUDED.enabled,
                preferred_primary_camera = EXCLUDED.preferred_primary_camera,
                default_shipping_profile_id = EXCLUDED.default_shipping_profile_id,
                default_shop_section_id = EXCLUDED.default_shop_section_id,
                updated_at = NOW()
            """,
            times_json, timezone, 1 if enabled else 0, preferred_primary_camera,
            default_shipping_profile_id, default_shop_section_id,
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
