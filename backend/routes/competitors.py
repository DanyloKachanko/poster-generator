import json
import asyncio
from collections import Counter
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx
from deps import etsy
import database as db

router = APIRouter(tags=["competitors"])


class AddCompetitorRequest(BaseModel):
    etsy_shop_id: str


@router.get("/competitors/search")
async def search_competitors(keywords: str = Query(..., min_length=2)):
    """Search Etsy for competitor shops by keyword."""
    if not etsy.is_configured:
        raise HTTPException(status_code=400, detail="Etsy API key not configured")

    try:
        data = await etsy.search_listings(keywords, limit=25)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Etsy search failed: {e}")

    results = data.get("results", [])

    # Extract unique shop_ids
    seen_shop_ids = {}
    for listing in results:
        shop_id = str(listing.get("shop_id", ""))
        if shop_id and shop_id not in seen_shop_ids:
            seen_shop_ids[shop_id] = True

    # Fetch shop details for each unique shop
    existing = await db.get_competitors()
    tracked_shop_ids = {c["etsy_shop_id"] for c in existing}

    shops = []
    for shop_id in list(seen_shop_ids.keys())[:15]:  # Cap at 15 shops
        try:
            shop = await etsy.get_shop_public(shop_id)
            shops.append({
                "shop_id": str(shop.get("shop_id", "")),
                "shop_name": shop.get("shop_name", ""),
                "icon_url": shop.get("icon_url_fullxfull", ""),
                "rating": shop.get("review_average", 0) or 0,
                "total_reviews": shop.get("review_count", 0) or 0,
                "listing_count": shop.get("listing_active_count", 0) or 0,
                "already_tracked": str(shop.get("shop_id", "")) in tracked_shop_ids,
            })
            await asyncio.sleep(0.1)
        except Exception:
            continue  # Skip shops that fail to load

    return {"shops": shops, "keyword": keywords}


@router.post("/competitors")
async def add_competitor(request: AddCompetitorRequest):
    """Add a competitor shop to track."""
    if not etsy.is_configured:
        raise HTTPException(status_code=400, detail="Etsy API key not configured")

    # Check if already exists
    existing = await db.get_competitor_by_shop_id(request.etsy_shop_id)
    if existing:
        if existing["is_active"] == 1:
            raise HTTPException(status_code=409, detail="Competitor already tracked")
        # Reactivate archived competitor
        await db.reactivate_competitor(existing["id"])
        return await db.get_competitor(existing["id"])

    # Fetch shop info from Etsy
    try:
        shop = await etsy.get_shop_public(request.etsy_shop_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch shop: {e}")

    shop_name = shop.get("shop_name", "")
    competitor = await db.save_competitor(
        etsy_shop_id=request.etsy_shop_id,
        shop_name=shop_name,
        shop_url=f"https://www.etsy.com/shop/{shop_name}",
        icon_url=shop.get("icon_url_fullxfull", ""),
        total_listings=shop.get("listing_active_count", 0) or 0,
        rating=shop.get("review_average", 0) or 0,
        total_reviews=shop.get("review_count", 0) or 0,
        country=shop.get("country_id", ""),
    )
    return competitor


@router.get("/competitors")
async def list_competitors():
    """List all active competitors."""
    competitors = await db.get_competitors(is_active=1)
    return {"competitors": competitors, "count": len(competitors)}


@router.get("/competitors/{competitor_id}")
async def get_competitor_detail(competitor_id: int):
    """Get competitor details with stats."""
    competitor = await db.get_competitor(competitor_id)
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    stats = await db.get_competitor_stats(competitor_id)
    return {
        **competitor,
        "listings_count": stats["listings_count"],
        "top_tags": json.loads(stats["top_tags"]) if stats["top_tags"] else [],
        "last_snapshot_date": stats["last_snapshot_date"],
    }


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(competitor_id: int):
    """Soft-delete a competitor."""
    competitor = await db.get_competitor(competitor_id)
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    await db.archive_competitor(competitor_id)
    return {"ok": True}


@router.post("/competitors/{competitor_id}/sync")
async def sync_competitor(competitor_id: int):
    """Sync a competitor's listings from Etsy."""
    competitor = await db.get_competitor(competitor_id)
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not etsy.is_configured:
        raise HTTPException(status_code=400, detail="Etsy API key not configured")

    try:
        listings = await etsy.get_shop_listings_public(competitor["etsy_shop_id"])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch listings: {e}")

    today = date.today().isoformat()
    synced = 0
    all_tags = []

    for listing in listings:
        tags = listing.get("tags", [])
        all_tags.extend(tags)

        # Extract price
        price_obj = listing.get("price", {})
        amount = price_obj.get("amount", 0) or 0
        divisor = price_obj.get("divisor", 100) or 100
        price_cents = int(amount / divisor * 100)

        # Extract first image URL
        images = listing.get("images", [])
        image_url = images[0].get("url_570xN", "") if images else ""

        row = await db.upsert_competitor_listing(
            competitor_id=competitor_id,
            etsy_listing_id=str(listing.get("listing_id", "")),
            title=listing.get("title", ""),
            description=listing.get("description", ""),
            tags=json.dumps(tags),
            price_cents=price_cents,
            currency=price_obj.get("currency_code", "USD"),
            views=listing.get("views", 0) or 0,
            favorites=listing.get("num_favorers", 0) or 0,
            image_url=image_url,
        )

        # Save daily stats
        await db.save_competitor_listing_stats(
            listing_id=row["id"],
            date=today,
            views=listing.get("views", 0) or 0,
            favorites=listing.get("num_favorers", 0) or 0,
            price_cents=price_cents,
        )
        synced += 1

    # Build snapshot: top 10 tags by frequency
    tag_counts = Counter(t.lower() for t in all_tags)
    top_tags = [t for t, _ in tag_counts.most_common(10)]
    avg_price = 0
    if listings:
        prices = []
        for l in listings:
            p = l.get("price", {})
            a = p.get("amount", 0) or 0
            d = p.get("divisor", 100) or 100
            prices.append(int(a / d * 100))
        avg_price = sum(prices) // len(prices) if prices else 0

    await db.save_competitor_snapshot(
        competitor_id=competitor_id,
        snapshot_date=today,
        total_listings=len(listings),
        avg_price_cents=avg_price,
        top_tags=json.dumps(top_tags),
    )

    # Update competitor record
    await db.update_competitor(
        competitor_id,
        total_listings=len(listings),
    )

    return {"synced": synced, "total_listings": len(listings), "date": today}


@router.get("/competitors/{competitor_id}/listings")
async def get_competitor_listings(
    competitor_id: int,
    sort_by: str = Query("favorites"),
    sort_dir: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get paginated competitor listings."""
    competitor = await db.get_competitor(competitor_id)
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    listings = await db.get_competitor_listings(
        competitor_id, sort_by=sort_by, sort_dir=sort_dir, limit=limit, offset=offset
    )
    total = await db.get_competitor_listings_count(competitor_id)

    # Parse tags JSON for each listing
    for l in listings:
        try:
            l["tags"] = json.loads(l.get("tags", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            l["tags"] = []

    return {"listings": listings, "total": total}
