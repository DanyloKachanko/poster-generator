from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deps import printify, etsy
from routes.etsy_auth import ensure_etsy_token
import database as db

router = APIRouter(tags=["analytics"])


async def _get_active_etsy_listing_ids() -> set:
    """Fetch active Etsy listing IDs for cross-referencing with Printify data."""
    try:
        access_token, shop_id = await ensure_etsy_token()
        listings = await etsy.get_all_listings(access_token, shop_id)
        return {str(l["listing_id"]) for l in listings}
    except Exception:
        return set()


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get business-focused dashboard statistics."""
    try:
        gen_stats = await db.get_generation_stats()
        analytics = await db.get_analytics_summary()

        total_views = sum(a.get("total_views", 0) for a in analytics)
        total_favorites = sum(a.get("total_favorites", 0) for a in analytics)
        total_orders = sum(a.get("total_orders", 0) for a in analytics)
        total_revenue = sum(a.get("total_revenue_cents", 0) for a in analytics)

        # Count products from local DB (no external API dependency)
        products_count = 0
        published_count = 0
        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE etsy_listing_id IS NOT NULL) AS published
                    FROM products
                """)
                products_count = row["total"]
                published_count = row["published"]
        except Exception:
            pass

        # Time-windowed totals for trend calculation
        current_7d = await db.get_analytics_totals_for_period(7)
        previous_7d = await db.get_analytics_totals_for_period(14)

        # Chart data + top performers
        daily_views = await db.get_daily_views_chart(30)
        top_products = await db.get_top_products(5)

        # Conversion rate
        conversion_rate = (total_orders / total_views * 100) if total_views > 0 else 0

        # 7-day trends (percentage change)
        def calc_trend(metric: str):
            current = current_7d.get(metric, 0)
            prev_total = previous_7d.get(metric, 0)
            prev_only = prev_total - current
            if prev_only == 0:
                return current * 100 if current > 0 else 0
            return round((current - prev_only) / prev_only * 100, 1)

        return {
            "total_generated": gen_stats.get("total_generations", 0),
            "total_images": gen_stats.get("total_images", 0),
            "total_credits_used": gen_stats.get("total_credits_used", 0),
            "total_products": products_count,
            "total_published": published_count,
            "total_views": total_views,
            "total_favorites": total_favorites,
            "total_orders": total_orders,
            "total_revenue_cents": total_revenue,
            "by_status": gen_stats.get("by_status", {}),
            "conversion_rate": round(conversion_rate, 2),
            "trends_7d": {
                "views": calc_trend("total_views"),
                "orders": calc_trend("total_orders"),
                "revenue": calc_trend("total_revenue_cents"),
            },
            "daily_views": daily_views,
            "top_products": top_products,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AnalyticsEntryRequest(BaseModel):
    printify_product_id: str
    date: str
    views: int = 0
    favorites: int = 0
    orders: int = 0
    revenue_cents: int = 0
    notes: Optional[str] = None


def _get_product_thumbnail(product: dict) -> Optional[str]:
    """Extract the thumbnail URL from a Printify product's images."""
    for img in product.get("images", []):
        if img.get("is_default"):
            return img.get("src")
    if product.get("images"):
        return product["images"][0].get("src")
    return None


def _get_price_range(product: dict) -> tuple[int, int]:
    """Return (min_price, max_price) from a product's enabled variants."""
    enabled_variants = [v for v in product.get("variants", []) if v.get("is_enabled")]
    prices = [v.get("price", 0) for v in enabled_variants]
    return (min(prices) if prices else 0, max(prices) if prices else 0)


def _get_etsy_info(product: dict, active_etsy_ids: set) -> tuple[str, Optional[str]]:
    """Determine Etsy status and URL for a product.

    Returns (status, etsy_url).
    """
    external = product.get("external")
    etsy_url = None
    etsy_listing_id = str(external["id"]) if external and external.get("id") else None
    if external and external.get("handle"):
        handle = external["handle"]
        etsy_url = handle if handle.startswith("http") else f"https://{handle}"

    if active_etsy_ids:
        if etsy_listing_id and etsy_listing_id in active_etsy_ids:
            status = "on_etsy"
        elif etsy_listing_id:
            status = "deleted"
        else:
            status = "draft"
    else:
        status = "on_etsy" if etsy_listing_id else "draft"

    return status, etsy_url


def _merge_product_with_analytics(product: dict, analytics_entry: dict, active_etsy_ids: set) -> dict:
    """Merge a Printify product with its analytics data into a single record."""
    pid = product["id"]
    thumbnail = _get_product_thumbnail(product)
    min_price, max_price = _get_price_range(product)
    status, etsy_url = _get_etsy_info(product, active_etsy_ids)

    return {
        "printify_product_id": pid,
        "title": product.get("title", "Untitled"),
        "thumbnail": thumbnail,
        "status": status,
        "min_price": min_price,
        "max_price": max_price,
        "etsy_url": etsy_url,
        "total_views": analytics_entry.get("total_views", 0),
        "total_favorites": analytics_entry.get("total_favorites", 0),
        "total_orders": analytics_entry.get("total_orders", 0),
        "total_revenue_cents": analytics_entry.get("total_revenue_cents", 0),
        "latest_date": analytics_entry.get("latest_date"),
    }


async def _build_orphaned_entry(pid: str, analytics_entry: dict) -> dict:
    """Build a merged record for a product that no longer exists on Printify."""
    local = await db.get_product_by_printify_id(pid)
    title = None
    thumbnail = None
    if local:
        title = local.get("title")
        thumbnail = local.get("image_url")
    if not title:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT title, image_url FROM scheduled_products WHERE printify_product_id = $1",
                pid,
            )
            if row:
                title = row["title"]
                thumbnail = thumbnail or row["image_url"]
    return {
        "printify_product_id": pid,
        "title": title or f"Deleted ({pid[-8:]})",
        "thumbnail": thumbnail,
        "status": "deleted",
        "min_price": 0,
        "max_price": 0,
        "etsy_url": None,
        "total_views": analytics_entry.get("total_views", 0),
        "total_favorites": analytics_entry.get("total_favorites", 0),
        "total_orders": analytics_entry.get("total_orders", 0),
        "total_revenue_cents": analytics_entry.get("total_revenue_cents", 0),
        "latest_date": analytics_entry.get("latest_date"),
    }


def _compute_totals(merged: list[dict]) -> dict:
    """Compute summary totals from the merged product list."""
    total_views = sum(p["total_views"] for p in merged)
    total_favorites = sum(p["total_favorites"] for p in merged)
    total_orders = sum(p["total_orders"] for p in merged)
    total_revenue = sum(p["total_revenue_cents"] for p in merged)

    live_products = [p for p in merged if p["status"] == "on_etsy"]
    deleted_products = [p for p in merged if p["status"] == "deleted"]
    draft_products_list = [p for p in merged if p["status"] == "draft"]
    live_with_views = [p for p in live_products if p["total_views"] > 0]
    live_no_views = [p for p in live_products if p["total_views"] == 0]

    best = max(merged, key=lambda p: p["total_views"]) if merged else None

    return {
        "total_views": total_views,
        "total_favorites": total_favorites,
        "total_orders": total_orders,
        "total_revenue_cents": total_revenue,
        "total_products": len(merged),
        "live_products": len(live_products),
        "draft_products": len(draft_products_list),
        "deleted_products": len(deleted_products),
        "products_with_views": len(live_with_views),
        "products_no_views": len(live_no_views),
        "avg_views": round(total_views / len(live_products), 1) if live_products else 0,
        "avg_favorites": round(total_favorites / len(live_products), 1) if live_products else 0,
        "fav_rate": round((total_favorites / total_views * 100), 1) if total_views > 0 else 0,
        "best_performer": best["title"] if best and best["total_views"] > 0 else None,
        "best_performer_views": best["total_views"] if best and best["total_views"] > 0 else 0,
    }


async def _fetch_printify_products() -> list[dict]:
    """Fetch products from Printify, returning an empty list on failure."""
    if not printify.is_configured:
        return []
    try:
        result = await printify.list_products(page=1, limit=50)
        return result.get("data", [])
    except Exception:
        return []


@router.get("/analytics")
async def get_analytics():
    """
    Get all products with aggregated analytics.
    Merges Printify product data with local SQLite analytics.
    """
    try:
        analytics = await db.get_analytics_summary()
        analytics_map = {a["printify_product_id"]: a for a in analytics}

        products = await _fetch_printify_products()
        active_etsy_ids = await _get_active_etsy_listing_ids()

        # Merge Printify products with their analytics
        merged = []
        for product in products:
            a = analytics_map.pop(product["id"], {})
            merged.append(_merge_product_with_analytics(product, a, active_etsy_ids))

        # Include orphaned analytics entries (products no longer on Printify)
        for pid, a in analytics_map.items():
            merged.append(await _build_orphaned_entry(pid, a))

        return {
            "products": merged,
            "totals": _compute_totals(merged),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics")
async def save_analytics_entry(request: AnalyticsEntryRequest):
    """Upsert analytics entry for a product on a given date."""
    try:
        await db.save_analytics(
            printify_product_id=request.printify_product_id,
            date=request.date,
            views=request.views,
            favorites=request.favorites,
            orders=request.orders,
            revenue_cents=request.revenue_cents,
            notes=request.notes,
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/{product_id}/history")
async def get_product_analytics(product_id: str):
    """Get historical analytics entries for a single product."""
    try:
        entries = await db.get_product_analytics_history(product_id)
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
