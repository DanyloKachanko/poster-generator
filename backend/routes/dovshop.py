"""DovShop API routes for product publishing and management"""

import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deps import dovshop_client
from categorizer import categorize_product
import database as db

router = APIRouter(tags=["dovshop"])


class PushProductRequest(BaseModel):
    """Request model for pushing product to DovShop"""
    printify_product_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    tags: Optional[List[str]] = None
    featured: bool = False


class CreateCollectionRequest(BaseModel):
    """Request model for creating DovShop collection"""
    name: str
    description: str = ""
    cover_url: Optional[str] = None


@router.get("/dovshop/status")
async def get_dovshop_status():
    """Check DovShop API connection and configuration"""
    if not dovshop_client.is_configured:
        return {
            "configured": False,
            "connected": False,
            "message": "DovShop API key or URL not configured"
        }

    try:
        health = await dovshop_client.health_check()
        return {
            "configured": True,
            "connected": health.get("status") != "error",
            "info": health
        }
    except Exception as e:
        return {
            "configured": True,
            "connected": False,
            "error": str(e)
        }


@router.get("/dovshop/products")
async def list_dovshop_products():
    """Get all products from DovShop"""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        products = await dovshop_client.get_products()
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch DovShop products: {str(e)}")


@router.post("/dovshop/push")
async def push_product_to_dovshop(request: PushProductRequest):
    """Push a product from the panel to DovShop.

    Workflow:
    1. Fetch product from panel database
    2. Build Etsy URL from etsy_listing_id
    3. Create poster on DovShop with image URL
    4. Save DovShop ID back to our DB
    """
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        # Step 1: Get product from local database
        product = await db.get_product_by_printify_id(request.printify_product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found in database")

        image_url = product.get("image_url") or ""
        if not image_url:
            raise HTTPException(status_code=404, detail="Product has no image")

        # Step 2: Build Etsy URL if available
        etsy_listing_id = product.get("etsy_listing_id")
        etsy_url = f"https://www.etsy.com/listing/{etsy_listing_id}" if etsy_listing_id else ""

        # Step 3: Create poster on DovShop
        name = request.title or product["title"]
        dovshop_product = await dovshop_client.push_product(
            name=name,
            images=[image_url],
            etsy_url=etsy_url,
            featured=request.featured,
            description=request.description or product.get("description", ""),
            tags=request.tags or product.get("tags", []),
            price=request.price or 0,
            external_id=request.printify_product_id,
            preferred_mockup_url=product.get("preferred_mockup_url") or "",
        )

        # Step 4: Save DovShop product ID to our DB
        dovshop_id = dovshop_product.get("id") or dovshop_product.get("_id", "")
        if dovshop_id:
            await db.set_product_dovshop_id(request.printify_product_id, str(dovshop_id))

        return {
            "success": True,
            "dovshop_product_id": dovshop_id,
            "dovshop_product": dovshop_product,
            "message": "Product successfully pushed to DovShop",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to push product: {str(e)}")


@router.delete("/dovshop/products/{product_id}")
async def delete_dovshop_product(product_id: str):
    """Delete a product from DovShop"""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        success = await dovshop_client.delete_product(product_id)
        return {
            "success": success,
            "message": "Product deleted from DovShop"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete product: {str(e)}")


@router.get("/dovshop/collections")
async def list_dovshop_collections():
    """Get all collections from DovShop"""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        collections = await dovshop_client.get_collections()
        return {"collections": collections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch collections: {str(e)}")


@router.post("/dovshop/collections")
async def create_dovshop_collection(request: CreateCollectionRequest):
    """Create a new collection on DovShop"""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        collection = await dovshop_client.create_collection(
            name=request.name,
            description=request.description,
            cover_url=request.cover_url or ""
        )
        return {
            "success": True,
            "collection": collection,
            "message": "Collection created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")


@router.delete("/dovshop/collections/{collection_id}")
async def delete_dovshop_collection(collection_id: str):
    """Delete a collection from DovShop"""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        success = await dovshop_client.delete_collection(collection_id)
        return {
            "success": success,
            "message": "Collection deleted from DovShop"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")


@router.post("/dovshop/sync")
async def sync_all_to_dovshop():
    """Bulk sync all published products to DovShop with auto-categorization.

    Gathers all products with etsy_listing_id (published on Etsy),
    auto-categorizes them from tags/style, and sends them to DovShop
    in a single bulk request.
    """
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT p.*, g.style as gen_style
                FROM products p
                LEFT JOIN generated_images gi ON gi.id = p.source_image_id
                LEFT JOIN generations g ON g.generation_id = gi.generation_id
                WHERE p.etsy_listing_id IS NOT NULL
                ORDER BY p.created_at DESC
            """)

        if not rows:
            return {"total": 0, "created": 0, "updated": 0, "errors": [], "message": "No published products found"}

        # Build bulk payload
        posters = []
        for row in rows:
            product = dict(row)
            tags = product.get("tags") or []
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []

            style = product.get("gen_style") or None
            categories = categorize_product(tags, style)

            # Get mockup images from image_mockups table
            images = []
            mockup_url = product.get("preferred_mockup_url")
            if mockup_url:
                images.append(mockup_url)

            # Also get etsy CDN mockup URLs
            async with pool.acquire() as conn:
                mockup_rows = await conn.fetch("""
                    SELECT etsy_cdn_url FROM image_mockups
                    WHERE image_id = $1 AND etsy_cdn_url IS NOT NULL AND is_included = true
                    ORDER BY rank ASC
                """, product.get("source_image_id") or 0)
            for mr in mockup_rows:
                url = mr["etsy_cdn_url"]
                if url and url not in images:
                    images.append(url)

            # Fallback to original image
            if not images and product.get("image_url"):
                images.append(product["image_url"])

            etsy_listing_id = product.get("etsy_listing_id")
            etsy_url = f"https://www.etsy.com/listing/{etsy_listing_id}" if etsy_listing_id else None

            enabled_sizes = product.get("enabled_sizes") or []
            if isinstance(enabled_sizes, str):
                try:
                    enabled_sizes = json.loads(enabled_sizes)
                except Exception:
                    enabled_sizes = []

            posters.append({
                "name": product.get("title", ""),
                "images": images,
                "description": product.get("description", ""),
                "tags": tags,
                "etsy_url": etsy_url,
                "etsy_listing_id": etsy_listing_id,
                "printify_id": product.get("printify_product_id"),
                "mockup_url": mockup_url,
                "sizes": enabled_sizes,
                "style": style,
                "categories": categories,
            })

        # Send to DovShop
        result = await dovshop_client.bulk_sync(posters)

        # Update dovshop_product_id in local DB for synced products
        synced = result.get("results", [])
        for item in synced:
            pid = item.get("printify_id")
            did = item.get("dovshop_id")
            if pid and did:
                await db.set_product_dovshop_id(pid, str(did))

        return {
            "total": result.get("total", len(posters)),
            "created": result.get("created", 0),
            "updated": result.get("updated", 0),
            "errors": result.get("errors", []),
            "message": f"Synced {len(posters)} products to DovShop",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
