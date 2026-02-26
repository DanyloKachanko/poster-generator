"""Product CRUD and linking queries."""

import json
from typing import Optional, List, Dict, Any
from db.connection import get_pool


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
