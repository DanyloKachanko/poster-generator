"""Product analytics queries — views, favorites, orders, revenue."""

from typing import Optional, List, Dict, Any
from db.connection import get_pool


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


async def get_analytics_summary(limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
    """Get aggregated analytics per product (paginated)."""
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
            ORDER BY total_views DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        return [dict(row) for row in rows]


async def get_product_analytics_history(
    printify_product_id: str,
    limit: int = 365,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get analytics entries for a product, ordered by date (paginated)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM product_analytics
            WHERE printify_product_id = $1
            ORDER BY date DESC
            LIMIT $2 OFFSET $3
            """,
            printify_product_id, limit, offset,
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
    """Get daily NEW views (delta) for the last N days for chart rendering.

    Views in product_analytics are cumulative (Etsy total), so we compute
    the delta between consecutive snapshots per product and sum those deltas.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH snapshots AS (
                SELECT date, printify_product_id, MAX(views) as views
                FROM product_analytics
                WHERE date >= (CURRENT_DATE - ($1 + 1) * INTERVAL '1 day')::date::text
                GROUP BY date, printify_product_id
            ),
            deltas AS (
                SELECT date, printify_product_id,
                       views - COALESCE(LAG(views) OVER (
                           PARTITION BY printify_product_id ORDER BY date
                       ), 0) AS new_views
                FROM snapshots
            )
            SELECT date, GREATEST(SUM(new_views), 0) as views
            FROM deltas
            WHERE date >= (CURRENT_DATE - $1 * INTERVAL '1 day')::date::text
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
