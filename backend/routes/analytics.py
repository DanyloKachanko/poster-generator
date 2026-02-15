import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deps import printify, etsy
import database as db

router = APIRouter(tags=["analytics"])


async def _get_active_etsy_listing_ids() -> set:
    """Fetch active Etsy listing IDs for cross-referencing with Printify data."""
    try:
        tokens = await db.get_etsy_tokens()
        if not tokens or not tokens.get("shop_id"):
            return set()
        access_token = tokens["access_token"]
        if tokens["expires_at"] < int(time.time()):
            new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
            await db.save_etsy_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
            )
            access_token = new_tokens.access_token
        listings = await etsy.get_all_listings(access_token, tokens["shop_id"])
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

        # Count products on Printify, cross-referenced with active Etsy listings
        products_count = 0
        published_count = 0
        if printify.is_configured:
            try:
                result = await printify.list_products(page=1, limit=50)
                products = result.get("data", [])
                products_count = len(products)
                active_etsy_ids = await _get_active_etsy_listing_ids()
                published_count = sum(
                    1 for p in products
                    if p.get("external") and str(p["external"].get("id", "")) in active_etsy_ids
                ) if active_etsy_ids else sum(
                    1 for p in products
                    if p.get("external") and p["external"].get("id")
                )
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


@router.get("/analytics")
async def get_analytics():
    """
    Get all products with aggregated analytics.
    Merges Printify product data with local SQLite analytics.
    """
    try:
        # Get analytics summary from SQLite
        analytics = await db.get_analytics_summary()
        analytics_map = {a["printify_product_id"]: a for a in analytics}

        # Get products from Printify
        products = []
        if printify.is_configured:
            try:
                result = await printify.list_products(page=1, limit=50)
                products = result.get("data", [])
            except Exception:
                pass

        # Fetch active Etsy listing IDs for accurate status
        active_etsy_ids = await _get_active_etsy_listing_ids()

        # Merge: build list with product info + analytics
        merged = []
        for product in products:
            pid = product["id"]
            a = analytics_map.pop(pid, {})

            # Get thumbnail from images
            thumbnail = None
            for img in product.get("images", []):
                if img.get("is_default"):
                    thumbnail = img.get("src")
                    break
            if not thumbnail and product.get("images"):
                thumbnail = product["images"][0].get("src")

            # Get price range from enabled variants
            enabled_variants = [v for v in product.get("variants", []) if v.get("is_enabled")]
            prices = [v.get("price", 0) for v in enabled_variants]
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0

            # Etsy status — cross-reference with active listings
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
                    status = "deleted"  # was published but deleted on Etsy
                else:
                    status = "draft"
            else:
                status = "on_etsy" if etsy_listing_id else "draft"

            merged.append({
                "printify_product_id": pid,
                "title": product.get("title", "Untitled"),
                "thumbnail": thumbnail,
                "status": status,
                "min_price": min_price,
                "max_price": max_price,
                "etsy_url": etsy_url,
                "total_views": a.get("total_views", 0),
                "total_favorites": a.get("total_favorites", 0),
                "total_orders": a.get("total_orders", 0),
                "total_revenue_cents": a.get("total_revenue_cents", 0),
                "latest_date": a.get("latest_date"),
            })

        # Include any analytics entries for products no longer on Printify
        for pid, a in analytics_map.items():
            # Try to look up product info from local DB or scheduled_products
            local = await db.get_product_by_printify_id(pid)
            title = None
            thumbnail = None
            if local:
                title = local.get("title")
                thumbnail = local.get("image_url")
            if not title:
                # Try scheduled_products as fallback
                pool = await db.get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT title, image_url FROM scheduled_products WHERE printify_product_id = $1",
                        pid,
                    )
                    if row:
                        title = row["title"]
                        thumbnail = thumbnail or row["image_url"]
            merged.append({
                "printify_product_id": pid,
                "title": title or f"Deleted ({pid[-8:]})",
                "thumbnail": thumbnail,
                "status": "deleted",
                "min_price": 0,
                "max_price": 0,
                "etsy_url": None,
                "total_views": a.get("total_views", 0),
                "total_favorites": a.get("total_favorites", 0),
                "total_orders": a.get("total_orders", 0),
                "total_revenue_cents": a.get("total_revenue_cents", 0),
                "latest_date": a.get("latest_date"),
            })

        # Summary totals
        total_views = sum(p["total_views"] for p in merged)
        total_favorites = sum(p["total_favorites"] for p in merged)
        total_orders = sum(p["total_orders"] for p in merged)
        total_revenue = sum(p["total_revenue_cents"] for p in merged)

        live_products = [p for p in merged if p["status"] == "on_etsy"]
        deleted_products = [p for p in merged if p["status"] == "deleted"]
        draft_products_list = [p for p in merged if p["status"] == "draft"]
        live_with_views = [p for p in live_products if p["total_views"] > 0]
        live_no_views = [p for p in live_products if p["total_views"] == 0]

        # Best performer by views
        best = max(merged, key=lambda p: p["total_views"]) if merged else None

        totals = {
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

        return {
            "products": merged,
            "totals": totals,
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
