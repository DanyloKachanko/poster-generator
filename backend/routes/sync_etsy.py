"""
Sync Etsy listings with local database.
Fetches all Etsy listings and updates products with etsy_listing_id.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from deps import etsy
from routes.etsy_auth import ensure_etsy_token
import database as db

router = APIRouter(tags=["sync"])


@router.post("/sync/etsy-listings")
async def sync_etsy_listings():
    """
    Fetch all Etsy listings and sync with local database.
    Matches listings to products and updates etsy_listing_id field.
    """
    access_token, shop_id = await ensure_etsy_token()

    try:
        # Fetch all active listings from Etsy (auto-pagination)
        etsy_listings = await etsy.get_all_listings(
            access_token=access_token,
            shop_id=shop_id,
            state="active"
        )

        if not etsy_listings:
            return {
                "success": True,
                "message": "No active Etsy listings found",
                "synced": 0,
                "total_etsy_listings": 0
            }

        # Get all products from database
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            products = await conn.fetch("SELECT * FROM products")

            # Track sync results
            synced_count = 0
            matches = []
            unmatched_listings = []

            # Try to match Etsy listings with database products
            for listing in etsy_listings:
                listing_id = str(listing["listing_id"])
                listing_title = listing.get("title", "")

                # Try to find matching product by title
                matched = False
                for product in products:
                    # Simple title matching (could be improved)
                    if product["title"] and product["title"].strip() == listing_title.strip():
                        # Update product with etsy_listing_id
                        await conn.execute(
                            "UPDATE products SET etsy_listing_id = $1, updated_at = NOW() WHERE printify_product_id = $2",
                            listing_id,
                            product["printify_product_id"]
                        )
                        synced_count += 1
                        matched = True
                        matches.append({
                            "listing_id": listing_id,
                            "title": listing_title,
                            "product_id": product["printify_product_id"]
                        })
                        break

                if not matched:
                    unmatched_listings.append({
                        "listing_id": listing_id,
                        "title": listing_title
                    })

        return {
            "success": True,
            "synced": synced_count,
            "total_etsy_listings": len(etsy_listings),
            "total_db_products": len(products),
            "matches": matches,
            "unmatched_listings": unmatched_listings,
            "message": f"Synced {synced_count} out of {len(etsy_listings)} Etsy listings"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
