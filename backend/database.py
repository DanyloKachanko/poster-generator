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

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    printify_product_id TEXT UNIQUE NOT NULL,
    etsy_listing_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    tags TEXT[],
    image_url TEXT,
    pricing_strategy TEXT DEFAULT 'standard',
    enabled_sizes TEXT[],
    status TEXT DEFAULT 'draft',
    etsy_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_etsy ON products(etsy_listing_id);

CREATE TABLE IF NOT EXISTS seo_refresh_log (
    id SERIAL PRIMARY KEY,
    printify_product_id TEXT NOT NULL,
    etsy_listing_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    old_title TEXT,
    new_title TEXT,
    old_tags TEXT[],
    new_tags TEXT[],
    status TEXT DEFAULT 'updated',
    created_at TIMESTAMP DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS competitors (
    id SERIAL PRIMARY KEY,
    etsy_shop_id TEXT UNIQUE NOT NULL,
    shop_name TEXT NOT NULL,
    shop_url TEXT,
    icon_url TEXT,
    total_listings INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    total_reviews INTEGER DEFAULT 0,
    country TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_competitors_active ON competitors(is_active);

CREATE TABLE IF NOT EXISTS competitor_listings (
    id SERIAL PRIMARY KEY,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    etsy_listing_id TEXT UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    tags TEXT,
    price_cents INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    views INTEGER DEFAULT 0,
    favorites INTEGER DEFAULT 0,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    synced_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_competitor_listings_competitor ON competitor_listings(competitor_id);

CREATE TABLE IF NOT EXISTS competitor_listing_stats (
    id SERIAL PRIMARY KEY,
    listing_id INTEGER NOT NULL REFERENCES competitor_listings(id),
    date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    favorites INTEGER DEFAULT 0,
    price_cents INTEGER DEFAULT 0,
    UNIQUE(listing_id, date)
);
CREATE INDEX IF NOT EXISTS idx_competitor_listing_stats_date ON competitor_listing_stats(date DESC);

CREATE TABLE IF NOT EXISTS competitor_snapshots (
    id SERIAL PRIMARY KEY,
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    snapshot_date TEXT NOT NULL,
    total_listings INTEGER DEFAULT 0,
    avg_price_cents INTEGER DEFAULT 0,
    top_tags TEXT,
    UNIQUE(competitor_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS mockup_templates (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    scene_url TEXT NOT NULL,
    scene_width INTEGER NOT NULL DEFAULT 1024,
    scene_height INTEGER NOT NULL DEFAULT 1280,
    corners TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_plans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_items (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES strategy_plans(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    description TEXT,
    style TEXT,
    preset TEXT,
    model_id TEXT NOT NULL DEFAULT 'phoenix',
    size_id TEXT NOT NULL DEFAULT 'poster_4_5',
    title_hint TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    generation_id TEXT,
    printify_product_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_strategy_items_plan ON strategy_items(plan_id);
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
        try:
            await conn.execute(
                "ALTER TABLE schedule_settings ADD COLUMN preferred_primary_camera TEXT NOT NULL DEFAULT ''"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE scheduled_products ADD COLUMN etsy_metadata JSONB DEFAULT '{}'::jsonb"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE schedule_settings ADD COLUMN default_shipping_profile_id BIGINT"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE schedule_settings ADD COLUMN default_shop_section_id BIGINT"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE products ADD COLUMN preferred_mockup_url TEXT"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE products ADD COLUMN dovshop_product_id TEXT"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass

        # Mockup workflow columns
        try:
            await conn.execute(
                "ALTER TABLE generated_images ADD COLUMN mockup_url TEXT"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE generated_images ADD COLUMN mockup_status TEXT DEFAULT 'pending'"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass

        # Product ↔ Generated Image linking
        try:
            await conn.execute(
                "ALTER TABLE products ADD COLUMN source_image_id INTEGER REFERENCES generated_images(id)"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        try:
            await conn.execute(
                "ALTER TABLE generated_images ADD COLUMN product_id INTEGER REFERENCES products(id)"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass

        # Backfill: link existing products ↔ images by URL
        await conn.execute("""
            UPDATE products p
            SET source_image_id = gi.id
            FROM generated_images gi
            WHERE p.image_url = gi.url AND p.source_image_id IS NULL
        """)
        await conn.execute("""
            UPDATE generated_images gi
            SET product_id = p.id
            FROM products p
            WHERE p.image_url = gi.url AND gi.product_id IS NULL
        """)

        # App settings table for default mockup template
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    id SERIAL PRIMARY KEY,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
        except asyncpg.exceptions.DuplicateTableError:
            pass

        # Multi-mockup: is_active flag on templates
        try:
            await conn.execute(
                "ALTER TABLE mockup_templates ADD COLUMN is_active BOOLEAN DEFAULT false"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass

        # Per-template blend mode (normal / multiply)
        try:
            await conn.execute(
                "ALTER TABLE mockup_templates ADD COLUMN blend_mode TEXT DEFAULT 'normal'"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass

        # Backfill: activate the current default template
        default_id = await conn.fetchval(
            "SELECT value FROM app_settings WHERE key = 'default_mockup_template_id'"
        )
        if default_id:
            await conn.execute(
                "UPDATE mockup_templates SET is_active = true WHERE id = $1 AND is_active = false",
                int(default_id),
            )

        # Multi-mockup: junction table for composed mockups per image
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS image_mockups (
                id SERIAL PRIMARY KEY,
                image_id INTEGER NOT NULL REFERENCES generated_images(id) ON DELETE CASCADE,
                template_id INTEGER NOT NULL REFERENCES mockup_templates(id),
                mockup_data TEXT NOT NULL,
                etsy_image_id TEXT,
                etsy_cdn_url TEXT,
                rank INTEGER NOT NULL DEFAULT 1,
                is_included BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(image_id, template_id)
            )
        """)
        try:
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_image_mockups_image ON image_mockups(image_id)"
            )
        except Exception:
            pass

        # Mockup packs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mockup_packs (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mockup_pack_templates (
                id SERIAL PRIMARY KEY,
                pack_id INTEGER NOT NULL REFERENCES mockup_packs(id) ON DELETE CASCADE,
                template_id INTEGER NOT NULL REFERENCES mockup_templates(id) ON DELETE CASCADE,
                rank INTEGER NOT NULL DEFAULT 1,
                UNIQUE(pack_id, template_id)
            )
        """)
        try:
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mockup_pack_templates_pack ON mockup_pack_templates(pack_id)"
            )
        except Exception:
            pass

        # pack_id on image_mockups
        try:
            await conn.execute(
                "ALTER TABLE image_mockups ADD COLUMN pack_id INTEGER REFERENCES mockup_packs(id) ON DELETE SET NULL"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass

        # color_grade on mockup_packs
        try:
            await conn.execute(
                "ALTER TABLE mockup_packs ADD COLUMN color_grade TEXT DEFAULT 'none'"
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
    exclude_style: Optional[str] = None,
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
        if exclude_style:
            conditions.append(f"(g.style IS NULL OR g.style != ${idx})")
            params.append(exclude_style)
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
                COALESCE(MAX(views), 0) as total_views,
                COALESCE(MAX(favorites), 0) as total_favorites,
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


async def get_analytics_totals_for_period(days: int = 7) -> Dict[str, Any]:
    """Get aggregated totals for the last N days."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(max_views), 0) as total_views,
                COALESCE(SUM(max_favs), 0) as total_favorites,
                COALESCE(SUM(sum_orders), 0) as total_orders,
                COALESCE(SUM(sum_revenue), 0) as total_revenue_cents
            FROM (
                SELECT printify_product_id,
                       MAX(views) as max_views,
                       MAX(favorites) as max_favs,
                       SUM(orders) as sum_orders,
                       SUM(revenue_cents) as sum_revenue
                FROM product_analytics
                WHERE date >= (CURRENT_DATE - $1 * INTERVAL '1 day')::date::text
                GROUP BY printify_product_id
            ) sub
            """,
            days,
        )
        return dict(row) if row else {
            "total_views": 0, "total_favorites": 0,
            "total_orders": 0, "total_revenue_cents": 0,
        }


async def get_daily_views_chart(days: int = 30) -> List[Dict[str, Any]]:
    """Get daily total views for the last N days for chart rendering."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT date, COALESCE(SUM(views), 0) as views
            FROM (
                SELECT date, printify_product_id, MAX(views) as views
                FROM product_analytics
                WHERE date >= (CURRENT_DATE - $1 * INTERVAL '1 day')::date::text
                GROUP BY date, printify_product_id
            ) sub
            GROUP BY date
            ORDER BY date ASC
            """,
            days,
        )
        return [dict(row) for row in rows]


async def get_top_products(limit: int = 5) -> List[Dict[str, Any]]:
    """Get top products by total views."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT printify_product_id,
                   COALESCE(MAX(views), 0) as total_views,
                   COALESCE(MAX(favorites), 0) as total_favorites,
                   COALESCE(SUM(orders), 0) as total_orders,
                   COALESCE(SUM(revenue_cents), 0) as total_revenue_cents
            FROM product_analytics
            GROUP BY printify_product_id
            ORDER BY total_views DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(row) for row in rows]


async def get_product_analytics_for_date(
    printify_product_id: str, date: str,
) -> Optional[Dict[str, Any]]:
    """Get analytics for a specific product on a specific date."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM product_analytics
            WHERE printify_product_id = $1 AND date = $2
            """,
            printify_product_id, date,
        )
        return dict(row) if row else None


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


# === Competitor Intelligence ===


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


# === Mockup Templates ===

async def save_mockup_template(name: str, scene_url: str, scene_width: int, scene_height: int, corners: str, blend_mode: str = "normal") -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO mockup_templates (name, scene_url, scene_width, scene_height, corners, blend_mode)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            name, scene_url, scene_width, scene_height, corners, blend_mode,
        )
        return dict(row)


async def get_mockup_templates() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mockup_templates ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]


async def get_mockup_template(template_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mockup_templates WHERE id = $1", template_id
        )
        return dict(row) if row else None


async def delete_mockup_template(template_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM mockup_templates WHERE id = $1", template_id
        )


async def update_mockup_template(
    template_id: int,
    name: str,
    scene_url: str,
    scene_width: int,
    scene_height: int,
    corners: str,
    blend_mode: str = "normal"
) -> Optional[dict]:
    """Update an existing mockup template."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE mockup_templates
               SET name = $1, scene_url = $2, scene_width = $3, scene_height = $4, corners = $5, blend_mode = $6
               WHERE id = $7
               RETURNING *""",
            name, scene_url, scene_width, scene_height, corners, blend_mode, template_id
        )
        return dict(row) if row else None


# === Products ===

async def save_product(
    printify_product_id: str,
    title: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    image_url: Optional[str] = None,
    pricing_strategy: str = "standard",
    enabled_sizes: Optional[List[str]] = None,
    status: str = "draft",
    etsy_metadata: Optional[Dict[str, Any]] = None,
    source_image_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Save a new product record."""
    pool = await get_pool()
    metadata_json = json.dumps(etsy_metadata) if etsy_metadata else "{}"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO products (printify_product_id, title, description, tags, image_url,
                                  pricing_strategy, enabled_sizes, status, etsy_metadata,
                                  source_image_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
            ON CONFLICT (printify_product_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                tags = EXCLUDED.tags,
                image_url = EXCLUDED.image_url,
                pricing_strategy = EXCLUDED.pricing_strategy,
                enabled_sizes = EXCLUDED.enabled_sizes,
                status = EXCLUDED.status,
                etsy_metadata = EXCLUDED.etsy_metadata,
                source_image_id = COALESCE(EXCLUDED.source_image_id, products.source_image_id),
                updated_at = NOW()
            RETURNING *
            """,
            printify_product_id, title, description,
            tags or [], image_url, pricing_strategy,
            enabled_sizes or [], status, metadata_json,
            source_image_id,
        )
        return dict(row)


async def link_image_to_product(image_id: int, product_id: int) -> None:
    """Set both FK directions: generated_images.product_id and products.source_image_id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE generated_images SET product_id = $1 WHERE id = $2",
            product_id, image_id,
        )
        await conn.execute(
            "UPDATE products SET source_image_id = $1, updated_at = NOW() WHERE id = $2",
            image_id, product_id,
        )


async def get_image_by_url(url: str) -> Optional[Dict[str, Any]]:
    """Find a generated_image row by its URL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM generated_images WHERE url = $1 LIMIT 1", url
        )
        return dict(row) if row else None


async def update_product_status(
    printify_product_id: str,
    status: str,
    etsy_listing_id: Optional[str] = None,
) -> bool:
    """Update product status and optionally set Etsy listing ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if etsy_listing_id:
            result = await conn.execute(
                """
                UPDATE products SET status = $1, etsy_listing_id = $2, updated_at = NOW()
                WHERE printify_product_id = $3
                """,
                status, etsy_listing_id, printify_product_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE products SET status = $1, updated_at = NOW()
                WHERE printify_product_id = $2
                """,
                status, printify_product_id,
            )
        return result != "UPDATE 0"


async def set_product_preferred_mockup(printify_product_id: str, mockup_url: Optional[str]) -> bool:
    """Set or clear the preferred mockup URL for a product."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE products SET preferred_mockup_url = $1, updated_at = NOW() WHERE printify_product_id = $2",
            mockup_url, printify_product_id,
        )
        return result != "UPDATE 0"


async def set_product_dovshop_id(printify_product_id: str, dovshop_product_id: Optional[str]) -> bool:
    """Set or clear the DovShop product ID for a product."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE products SET dovshop_product_id = $1, updated_at = NOW() WHERE printify_product_id = $2",
            dovshop_product_id, printify_product_id,
        )
        return result != "UPDATE 0"


async def get_product_by_printify_id(printify_product_id: str) -> Optional[Dict[str, Any]]:
    """Get a single product by Printify ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM products WHERE printify_product_id = $1",
            printify_product_id,
        )
        return dict(row) if row else None


async def get_all_products(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get paginated product list, optionally filtered by status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT * FROM products WHERE status = $1
                ORDER BY created_at DESC LIMIT $2 OFFSET $3
                """,
                status, limit, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM products WHERE status = $1", status
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM products ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM products")

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


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

# === App Settings ===

async def get_setting(key: str) -> Optional[str]:
    """Get a setting value by key."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM app_settings WHERE key = $1", key
        )
        return row["value"] if row else None


async def set_setting(key: str, value: str) -> None:
    """Set a setting value (upsert)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = $2, updated_at = NOW()
            """,
            key, value,
        )


async def get_default_mockup_template_id() -> Optional[int]:
    """Get the default mockup template ID."""
    val = await get_setting("default_mockup_template_id")
    return int(val) if val else None


async def set_default_mockup_template_id(template_id: int) -> None:
    """Set the default mockup template ID."""
    await set_setting("default_mockup_template_id", str(template_id))


# === Mockup Workflow ===

async def update_image_mockup_status(
    image_id: int,
    mockup_url: Optional[str] = None,
    mockup_status: str = "pending",
) -> bool:
    """Update mockup URL and status for a generated image."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if mockup_url:
            result = await conn.execute(
                """
                UPDATE generated_images
                SET mockup_url = $1, mockup_status = $2
                WHERE id = $3
                """,
                mockup_url, mockup_status, image_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE generated_images
                SET mockup_status = $1
                WHERE id = $2
                """,
                mockup_status, image_id,
            )
        return result != "UPDATE 0"


async def get_workflow_posters(
    status: str = "pending",
    limit: int = 50,
    linked_only: bool = True,
) -> List[Dict[str, Any]]:
    """Get posters for workflow approval (pending/needs_attention).

    linked_only=True filters to only images linked to a product (product_id IS NOT NULL).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        linked_filter = "AND gi.product_id IS NOT NULL" if linked_only else ""
        rows = await conn.fetch(
            f"""
            SELECT gi.*, g.prompt, g.style, g.width, g.height
            FROM generated_images gi
            JOIN generations g ON gi.generation_id = g.generation_id
            WHERE gi.mockup_status = $1
              AND g.archived = 0
              AND (g.style IS NULL OR g.style != 'mockup')
              {linked_filter}
            ORDER BY gi.created_at DESC
            LIMIT $2
            """,
            status, limit,
        )
        return [dict(r) for r in rows]


# === Active Mockup Templates ===

async def get_active_mockup_templates() -> List[Dict[str, Any]]:
    """Get all templates marked as active, ordered by id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mockup_templates WHERE is_active = true ORDER BY id"
        )
        return [dict(r) for r in rows]


async def set_template_active(template_id: int, is_active: bool) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE mockup_templates SET is_active = $1 WHERE id = $2",
            is_active, template_id,
        )
        return result != "UPDATE 0"


async def set_active_templates(template_ids: List[int]) -> None:
    """Set exactly these templates as active, deactivating all others."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE mockup_templates SET is_active = false")
        if template_ids:
            await conn.execute(
                "UPDATE mockup_templates SET is_active = true WHERE id = ANY($1)",
                template_ids,
            )


# === Image Mockups (multi-mockup junction) ===

async def save_image_mockup(
    image_id: int,
    template_id: int,
    mockup_data: str,
    rank: int = 1,
    is_included: bool = True,
    pack_id: Optional[int] = None,
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO image_mockups (image_id, template_id, mockup_data, rank, is_included, pack_id)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (image_id, template_id) DO UPDATE SET
                 mockup_data = EXCLUDED.mockup_data,
                 rank = EXCLUDED.rank,
                 is_included = EXCLUDED.is_included,
                 pack_id = EXCLUDED.pack_id
               RETURNING *""",
            image_id, template_id, mockup_data, rank, is_included, pack_id,
        )
        return dict(row)


async def get_image_mockups(image_id: int) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM image_mockups WHERE image_id = $1 ORDER BY rank",
            image_id,
        )
        return [dict(r) for r in rows]


async def delete_image_mockups(image_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM image_mockups WHERE image_id = $1", image_id
        )


async def update_image_mockup_inclusion(mockup_id: int, is_included: bool) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE image_mockups SET is_included = $1 WHERE id = $2",
            is_included, mockup_id,
        )
        return result != "UPDATE 0"


async def update_image_mockup_etsy_info(
    mockup_id: int, etsy_image_id: str, etsy_cdn_url: str
) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE image_mockups SET etsy_image_id = $1, etsy_cdn_url = $2 WHERE id = $3",
            etsy_image_id, etsy_cdn_url, mockup_id,
        )
        return result != "UPDATE 0"


# === Mockup Packs ===

async def create_mockup_pack(name: str, color_grade: str = "none") -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO mockup_packs (name, color_grade) VALUES ($1, $2) RETURNING *",
            name, color_grade,
        )
        return dict(row)


async def get_mockup_packs() -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT mp.*, COUNT(mpt.id) as template_count
            FROM mockup_packs mp
            LEFT JOIN mockup_pack_templates mpt ON mpt.pack_id = mp.id
            GROUP BY mp.id
            ORDER BY mp.created_at DESC
        """)
        return [dict(r) for r in rows]


async def get_mockup_pack(pack_id: int) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mockup_packs WHERE id = $1", pack_id
        )
        return dict(row) if row else None


async def update_mockup_pack(pack_id: int, name: str, color_grade: str = "none") -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE mockup_packs SET name = $1, color_grade = $2 WHERE id = $3 RETURNING *",
            name, color_grade, pack_id,
        )
        return dict(row) if row else None


async def delete_mockup_pack(pack_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM mockup_packs WHERE id = $1", pack_id)


async def set_pack_templates(pack_id: int, template_ids: List[int]) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM mockup_pack_templates WHERE pack_id = $1", pack_id
        )
        for rank, tid in enumerate(template_ids, start=1):
            await conn.execute(
                "INSERT INTO mockup_pack_templates (pack_id, template_id, rank) VALUES ($1, $2, $3)",
                pack_id, tid, rank,
            )


async def get_pack_templates(pack_id: int) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT mt.*, mpt.rank as pack_rank
            FROM mockup_pack_templates mpt
            JOIN mockup_templates mt ON mt.id = mpt.template_id
            WHERE mpt.pack_id = $1
            ORDER BY mpt.rank
        """, pack_id)
        return [dict(r) for r in rows]


async def get_image_mockup_pack_id(image_id: int) -> Optional[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT pack_id FROM image_mockups WHERE image_id = $1 LIMIT 1",
            image_id,
        )
