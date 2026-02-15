"""
UI endpoints for manual Etsy product linking.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deps import etsy
import database as db

router = APIRouter(tags=["sync"])


class LinkProductRequest(BaseModel):
    printify_product_id: str
    etsy_listing_id: str


@router.get("/sync/etsy-unmatched")
async def get_unmatched_products():
    """
    Get products without etsy_listing_id and unmatched Etsy listings.
    Returns data for manual matching UI.
    """
    # Get tokens from database
    tokens = await db.get_etsy_tokens()
    if not tokens or not tokens.get("access_token") or not tokens.get("shop_id"):
        raise HTTPException(
            status_code=400,
            detail="Etsy not connected. Please connect via /etsy/auth-url first."
        )

    access_token = tokens["access_token"]
    shop_id = str(tokens["shop_id"])

    try:
        # Fetch all active listings from Etsy
        etsy_listings = await etsy.get_all_listings(
            access_token=access_token,
            shop_id=shop_id,
            state="active"
        )

        # Get all products from database
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            all_products = await conn.fetch("SELECT * FROM products ORDER BY created_at DESC")

        # Separate products with and without etsy_listing_id
        products_without_listing = []
        products_with_listing = []
        linked_listing_ids = set()

        for product in all_products:
            product_dict = {
                "printify_product_id": product["printify_product_id"],
                "title": product["title"],
                "status": product["status"],
                "etsy_listing_id": product["etsy_listing_id"],
                "image_url": product.get("image_url"),
                "created_at": product["created_at"].isoformat() if product["created_at"] else None
            }

            if product["etsy_listing_id"]:
                products_with_listing.append(product_dict)
                linked_listing_ids.add(str(product["etsy_listing_id"]))
            else:
                products_without_listing.append(product_dict)

        # Filter out already linked Etsy listings
        unmatched_etsy_listings = []
        for listing in etsy_listings:
            listing_id = str(listing["listing_id"])
            if listing_id not in linked_listing_ids:
                # Get first image URL if available
                images = listing.get("images", [])
                image_url = images[0].get("url_570xN") if images else None

                unmatched_etsy_listings.append({
                    "listing_id": listing_id,
                    "title": listing.get("title", ""),
                    "state": listing.get("state", ""),
                    "url": listing.get("url", ""),
                    "image_url": image_url
                })

        return {
            "success": True,
            "products_without_listing": products_without_listing,
            "products_with_listing": products_with_listing,
            "unmatched_etsy_listings": unmatched_etsy_listings,
            "total_unmatched_products": len(products_without_listing),
            "total_unmatched_listings": len(unmatched_etsy_listings)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch unmatched: {str(e)}")


@router.post("/sync/etsy-link")
async def link_product_to_etsy(request: LinkProductRequest):
    """
    Manually link a product to an Etsy listing ID.
    """
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Check if product exists
            product = await conn.fetchrow(
                "SELECT * FROM products WHERE printify_product_id = $1",
                request.printify_product_id
            )
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            # Update product with etsy_listing_id
            await conn.execute(
                "UPDATE products SET etsy_listing_id = $1, updated_at = NOW() WHERE printify_product_id = $2",
                request.etsy_listing_id,
                request.printify_product_id
            )

        return {
            "success": True,
            "message": f"Product {request.printify_product_id} linked to Etsy listing {request.etsy_listing_id}",
            "product_id": request.printify_product_id,
            "listing_id": request.etsy_listing_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link: {str(e)}")


@router.delete("/sync/etsy-unlink/{printify_product_id}")
async def unlink_product_from_etsy(printify_product_id: str):
    """
    Remove Etsy listing ID from a product.
    """
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Update product to remove etsy_listing_id
            result = await conn.execute(
                "UPDATE products SET etsy_listing_id = NULL, updated_at = NOW() WHERE printify_product_id = $1",
                printify_product_id
            )

        return {
            "success": True,
            "message": f"Product {printify_product_id} unlinked from Etsy",
            "product_id": printify_product_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlink: {str(e)}")


@router.post("/sync/etsy-import/{listing_id}")
async def import_etsy_listing(listing_id: str):
    """
    Import an Etsy listing as a new product in the database.
    Creates a draft product with etsy_listing_id set.
    """
    try:
        # Get tokens from database
        tokens = await db.get_etsy_tokens()
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=400, detail="Etsy not connected")

        access_token = tokens["access_token"]

        # Fetch listing details from Etsy
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://openapi.etsy.com/v3/application/listings/{listing_id}",
                headers={
                    "x-api-key": etsy._x_api_key,
                    "Authorization": f"Bearer {access_token}"
                },
                params={"includes": "images"},
                timeout=15.0
            )
            response.raise_for_status()
            listing = response.json()

        # Extract listing data
        title = listing.get("title", "")
        description = listing.get("description", "")

        # Get first image URL
        images = listing.get("images", [])
        image_url = images[0].get("url_570xN") if images else None

        # Create product in database
        # Generate a temporary printify_product_id (will be replaced when published to Printify)
        import uuid
        temp_product_id = f"etsy-import-{uuid.uuid4().hex[:12]}"

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO products (
                    printify_product_id, title, description, etsy_listing_id,
                    image_url, status, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, 'draft', NOW(), NOW())
                """,
                temp_product_id, title, description, listing_id, image_url
            )

        return {
            "success": True,
            "message": f"Imported Etsy listing {listing_id}",
            "product_id": temp_product_id,
            "listing_id": listing_id,
            "title": title
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import: {str(e)}")
