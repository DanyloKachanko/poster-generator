"""Database connection pool and schema initialization."""

import json
import logging
import os
import asyncpg
from typing import Optional

logger = logging.getLogger(__name__)

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

CREATE TABLE IF NOT EXISTS autocomplete_cache (
    id SERIAL PRIMARY KEY,
    tag TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'etsy',
    found BOOLEAN NOT NULL DEFAULT false,
    total_results INTEGER DEFAULT 0,
    demand TEXT DEFAULT 'dead',
    position INTEGER,
    suggestions_json TEXT,
    checked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '7 days')
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_tag_source ON autocomplete_cache(tag, source);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON autocomplete_cache(expires_at);

-- Performance indexes (added 2026-02-26)
CREATE INDEX IF NOT EXISTS idx_credit_usage_generation_id ON credit_usage(generation_id);
CREATE INDEX IF NOT EXISTS idx_seo_refresh_log_product ON seo_refresh_log(printify_product_id);
CREATE INDEX IF NOT EXISTS idx_seo_refresh_log_created ON seo_refresh_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_used_presets_product ON used_presets(printify_product_id);
CREATE INDEX IF NOT EXISTS idx_competitor_snapshots_competitor ON competitor_snapshots(competitor_id);
CREATE INDEX IF NOT EXISTS idx_mockup_templates_active ON mockup_templates(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_strategy_items_plan_status ON strategy_items(plan_id, status);

CREATE TABLE IF NOT EXISTS background_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    total INTEGER DEFAULT 0,
    done INTEGER DEFAULT 0,
    progress_json TEXT DEFAULT '{}',
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_background_tasks_type ON background_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_background_tasks_status ON background_tasks(status);
"""


async def init_db():
    """Initialize the database (create tables). Called on app startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(SCHEMA)

            # Migrations — all use IF NOT EXISTS for idempotency
            await conn.execute(
                "ALTER TABLE scheduled_products ADD COLUMN IF NOT EXISTS image_url TEXT"
            )
            await conn.execute(
                "ALTER TABLE schedule_settings ADD COLUMN IF NOT EXISTS preferred_primary_camera TEXT NOT NULL DEFAULT ''"
            )
            await conn.execute(
                "ALTER TABLE scheduled_products ADD COLUMN IF NOT EXISTS etsy_metadata JSONB DEFAULT '{}'::jsonb"
            )
            await conn.execute(
                "ALTER TABLE schedule_settings ADD COLUMN IF NOT EXISTS default_shipping_profile_id BIGINT"
            )
            await conn.execute(
                "ALTER TABLE schedule_settings ADD COLUMN IF NOT EXISTS default_shop_section_id BIGINT"
            )
            await conn.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS preferred_mockup_url TEXT"
            )
            await conn.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS dovshop_product_id TEXT"
            )

            # Mockup workflow columns
            await conn.execute(
                "ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS mockup_url TEXT"
            )
            await conn.execute(
                "ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS mockup_status TEXT DEFAULT 'pending'"
            )

            # Product ↔ Generated Image linking
            await conn.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS source_image_id INTEGER REFERENCES generated_images(id)"
            )
            await conn.execute(
                "ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES products(id)"
            )

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
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    id SERIAL PRIMARY KEY,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Multi-mockup: is_active flag on templates
            await conn.execute(
                "ALTER TABLE mockup_templates ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT false"
            )

            # Per-template blend mode (normal / multiply)
            await conn.execute(
                "ALTER TABLE mockup_templates ADD COLUMN IF NOT EXISTS blend_mode TEXT DEFAULT 'normal'"
            )

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
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_image_mockups_image ON image_mockups(image_id)"
            )

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
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mockup_pack_templates_pack ON mockup_pack_templates(pack_id)"
            )

            # pack_id on image_mockups
            await conn.execute(
                "ALTER TABLE image_mockups ADD COLUMN IF NOT EXISTS pack_id INTEGER REFERENCES mockup_packs(id) ON DELETE SET NULL"
            )

            # color_grade on mockup_packs
            await conn.execute(
                "ALTER TABLE mockup_packs ADD COLUMN IF NOT EXISTS color_grade TEXT DEFAULT 'none'"
            )

            # dovshop_included on image_mockups (separate from Etsy's is_included)
            await conn.execute(
                "ALTER TABLE image_mockups ADD COLUMN IF NOT EXISTS dovshop_included BOOLEAN DEFAULT true"
            )

            # dovshop_primary on image_mockups (hero image for DovShop)
            await conn.execute(
                "ALTER TABLE image_mockups ADD COLUMN IF NOT EXISTS dovshop_primary BOOLEAN DEFAULT false"
            )

            # AI strategy history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_strategy_history (
                    id SERIAL PRIMARY KEY,
                    result JSONB NOT NULL,
                    product_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

    logger.info("Database initialized (PostgreSQL)")
