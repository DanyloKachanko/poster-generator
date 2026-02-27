"""DovShop API routes for product publishing and management"""

import json
import logging
import os

logger = logging.getLogger(__name__)
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from deps import dovshop_client, etsy, printify
from categorizer import categorize_product, get_collection_slug
from dovshop_ai import enrich_product, analyze_catalog_strategy
import database as db
import re as _re

# Public backend URL for DovShop image URLs (so dovshop.org can reach them)
_PUBLIC_BACKEND_URL = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")


def _get_base_url(request: Request) -> str:
    """Build public base URL. Uses PUBLIC_BACKEND_URL env if set, else proxy headers."""
    if _PUBLIC_BACKEND_URL:
        return _PUBLIC_BACKEND_URL
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{scheme}://{host}"


async def _get_mockup_images(pool, source_image_id: int | None, base_url: str) -> list[str]:
    """Get image URLs for DovShop, preferring Etsy CDN, falling back to mockup serve.

    Primary mockup first, then by rank. Uses etsy_cdn_url when available
    (public, fast CDN) and falls back to /mockups/serve/{id} otherwise.
    """
    if not source_image_id:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, etsy_cdn_url FROM image_mockups
            WHERE image_id = $1 AND dovshop_included = true
            ORDER BY dovshop_primary DESC, rank ASC
        """, source_image_id)
    return [
        r["etsy_cdn_url"] if r["etsy_cdn_url"] else f"{base_url}/mockups/serve/{r['id']}"
        for r in rows
    ]


async def _get_variant_prices(printify_product_id: str) -> dict[str, float]:
    """Fetch enabled variant prices from Printify and return {size: price} dict.

    Printify variant title format: '8" x 10" / Matte' -> key '8x10'
    Price is in cents -> divide by 100.
    """
    try:
        product = await printify.get_product(printify_product_id)
        prices = {}
        for v in product.get("variants", []):
            if not v.get("is_enabled"):
                continue
            title = v.get("title", "")
            # Parse '8" x 10" / Matte' or '8\u2033 x 10\u2033 / Matte' -> '8x10'
            match = _re.match(r'(\d+)["\u2033\u2032\u201d\u2036]\s*x\s*(\d+)["\u2033\u2032\u201d\u2036]', title)
            if match:
                size_key = f"{match.group(1)}x{match.group(2)}"
                prices[size_key] = v.get("price", 0) / 100
        return prices
    except Exception as e:
        logger.warning("Failed to fetch variant prices for %s: %s", printify_product_id, e)
        return {}


def _transform_product(p: dict) -> dict:
    """Map DovShop camelCase poster fields to frontend snake_case."""
    images = p.get("images") or []
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []
    return {
        "id": str(p.get("id", "")),
        "title": p.get("name", ""),
        "description": p.get("description") or "",
        "price": _parse_price(p.get("priceRange") or ""),
        "image_url": p.get("mockupUrl") or (images[0] if images else ""),
        "images": images,
        "tags": p.get("tags") or [],
        "created_at": p.get("createdAt") or "",
        "slug": p.get("slug") or "",
        "etsy_url": p.get("etsyUrl") or "",
        "printify_id": p.get("printifyId") or "",
        "style": p.get("style") or "",
        "featured": p.get("featured", False),
        "collection": p.get("collection"),
        "categories": [c.get("slug") or c.get("name", "") for c in (p.get("categories") or [])],
    }


def _parse_price(price_range: str) -> float:
    """Extract first number from price range string like '$15 - $45'."""
    if not price_range:
        return 0.0
    match = _re.search(r"[\d.]+", price_range)
    return float(match.group()) if match else 0.0


def _transform_collection(c: dict) -> dict:
    """Map DovShop camelCase collection fields to frontend snake_case."""
    count = c.get("_count") or {}
    return {
        "id": str(c.get("id", "")),
        "name": c.get("name", ""),
        "description": c.get("description") or "",
        "cover_url": c.get("coverImage") or "",
        "product_count": count.get("posters") or 0,
        "created_at": c.get("createdAt") or "",
        "slug": c.get("slug") or "",
    }


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
        return {"products": [_transform_product(p) for p in products]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch DovShop products: {str(e)}")


@router.post("/dovshop/push")
async def push_product_to_dovshop(request: PushProductRequest, req: Request):
    """Push a product from the panel to DovShop.

    Workflow:
    1. Fetch product from panel database
    2. Build Etsy URL from etsy_listing_id
    3. Create poster on DovShop with mockup serve URLs
    4. Save DovShop ID back to our DB
    """
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        # Step 1: Get product from local database
        product = await db.get_product_by_printify_id(request.printify_product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found in database")

        # Step 2: Build images from our mockup serve endpoint
        base_url = _get_base_url(req)
        pool = await db.get_pool()
        images = await _get_mockup_images(pool, product.get("source_image_id"), base_url)
        if not images:
            # Fallback to original image
            image_url = product.get("image_url") or ""
            if not image_url:
                raise HTTPException(status_code=404, detail="Product has no image")
            images = [image_url]

        # Step 3: Build Etsy URL if available
        etsy_listing_id = product.get("etsy_listing_id")
        etsy_url = f"https://www.etsy.com/listing/{etsy_listing_id}" if etsy_listing_id else ""

        # Step 4: Create poster on DovShop
        name = request.title or product["title"]
        dovshop_product = await dovshop_client.push_product(
            name=name,
            images=images,
            etsy_url=etsy_url,
            featured=request.featured,
            description=request.description or product.get("description", ""),
            tags=request.tags or product.get("tags", []),
            price=request.price or 0,
            external_id=request.printify_product_id,
            preferred_mockup_url=images[0] if images else "",
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
        return {"collections": [_transform_collection(c) for c in collections]}
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
async def sync_all_to_dovshop(req: Request):
    """Bulk sync all published products to DovShop with auto-categorization.

    Gathers all products with etsy_listing_id (published on Etsy),
    auto-categorizes them from tags/style, and sends them to DovShop
    in a single bulk request.
    """
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    try:
        # Get active Etsy listing IDs to filter out deactivated/expired
        active_etsy_ids: set = set()
        try:
            tokens = await db.get_etsy_tokens()
            if tokens and tokens.get("shop_id"):
                import time as _time
                access_token = tokens["access_token"]
                if tokens["expires_at"] < int(_time.time()):
                    new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
                    await db.save_etsy_tokens(
                        access_token=new_tokens.access_token,
                        refresh_token=new_tokens.refresh_token,
                        expires_at=new_tokens.expires_at,
                        shop_id=tokens["shop_id"],
                    )
                    access_token = new_tokens.access_token
                listings = await etsy.get_all_listings(access_token, tokens["shop_id"])
                active_etsy_ids = {str(l["listing_id"]) for l in listings}
                logger.info("DovShop sync: %d active Etsy listings found", len(active_etsy_ids))
        except Exception as e:
            logger.warning("Could not fetch active Etsy listings: %s — syncing all", e)

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

        # Filter to only active Etsy listings (if we got the list)
        if active_etsy_ids:
            rows = [r for r in rows if r["etsy_listing_id"] in active_etsy_ids]

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

            # Get mockup images from our serve endpoint
            base_url = _get_base_url(req)
            images = await _get_mockup_images(pool, product.get("source_image_id"), base_url)

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

            size_prices = await _get_variant_prices(product.get("printify_product_id", ""))

            title = product.get("title", "")
            collection_slug = get_collection_slug(title, tags)

            posters.append({
                "name": title,
                "images": images,
                "description": product.get("description", ""),
                "tags": tags,
                "etsy_url": etsy_url,
                "etsy_listing_id": etsy_listing_id,
                "printify_id": product.get("printify_product_id"),
                "mockup_url": images[0] if images else None,
                "sizes": enabled_sizes,
                "style": style,
                "categories": categories,
                "collection_slug": collection_slug,
                "size_prices": size_prices,
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

        # Remove DovShop products not in current Etsy-published set
        synced_printify_ids = {p["printify_id"] for p in posters if p.get("printify_id")}
        removed = 0
        try:
            dovshop_products = await dovshop_client.get_products()
            for dp in dovshop_products:
                dp_pid = dp.get("printifyId") or dp.get("printify_id") or ""
                dp_id = dp.get("id")
                if dp_pid and dp_pid not in synced_printify_ids and dp_id:
                    try:
                        await dovshop_client.delete_product(str(dp_id))
                        removed += 1
                    except Exception as e:
                        logger.warning("Failed to remove DovShop product %s: %s", dp_id, e)
        except Exception as e:
            logger.warning("Failed to clean up DovShop products: %s", e)

        return {
            "total": result.get("total", len(posters)),
            "created": result.get("created", 0),
            "updated": result.get("updated", 0),
            "removed": removed,
            "errors": result.get("errors", []),
            "message": f"Synced {len(posters)} products to DovShop, removed {removed} stale",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# === Product Mockup Management ===


@router.get("/dovshop/product-mockups/{printify_product_id}")
async def get_product_mockups_for_dovshop(printify_product_id: str, req: Request):
    """Get all mockups for a product with both is_included and dovshop_included flags."""
    product = await db.get_product_by_printify_id(printify_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    source_image_id = product.get("source_image_id")
    if not source_image_id:
        return {"mockups": [], "printify_product_id": printify_product_id}

    mockups = await db.get_image_mockups_for_dovshop(source_image_id)
    base_url = _get_base_url(req)
    for m in mockups:
        m["thumbnail_url"] = f"{base_url}/mockups/serve/{m['id']}"
    return {"mockups": mockups, "printify_product_id": printify_product_id}


@router.post("/dovshop/update-product-images/{printify_product_id}")
async def update_dovshop_product_images(printify_product_id: str, req: Request):
    """Re-sync mockup images to DovShop based on dovshop_included flags."""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    product = await db.get_product_by_printify_id(printify_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    dovshop_product_id = product.get("dovshop_product_id")
    if not dovshop_product_id:
        raise HTTPException(status_code=400, detail="Product not on DovShop")

    base_url = _get_base_url(req)
    pool = await db.get_pool()
    images = await _get_mockup_images(pool, product.get("source_image_id"), base_url)
    if not images:
        raise HTTPException(status_code=400, detail="No mockups selected for DovShop")

    await dovshop_client.update_product(dovshop_product_id, {
        "images": images,
        "mockupUrl": images[0],
    })

    return {"success": True, "image_count": len(images), "printify_product_id": printify_product_id}


# === Pack Pattern Assignment ===


class AssignPackPatternRequest(BaseModel):
    start_offset: int = 0


@router.post("/dovshop/assign-pack-pattern")
async def assign_pack_pattern(request: AssignPackPatternRequest, req: Request):
    """Rotate the primary (hero) mockup across DovShop products for visual diversity.

    For all products on DovShop, cycles through their included mockups and sets
    a different one as dovshop_primary for each product. This makes every product
    look different on the storefront (product 1 → mockup 2, product 2 → mockup 3, etc.).

    start_offset shifts which mockup index the first product starts at.
    """
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    pool = await db.get_pool()

    # Get all products on DovShop, ordered by created_at
    async with pool.acquire() as conn:
        products = await conn.fetch("""
            SELECT p.printify_product_id, p.dovshop_product_id, p.source_image_id
            FROM products p
            WHERE p.dovshop_product_id IS NOT NULL
            ORDER BY p.created_at ASC
        """)

    total = len(products)
    updated = 0
    base_url = _get_base_url(req)

    for idx, product in enumerate(products):
        source_image_id = product["source_image_id"]
        if not source_image_id:
            continue

        # Get included mockups for this product
        async with pool.acquire() as conn:
            mockups = await conn.fetch(
                "SELECT id FROM image_mockups WHERE image_id = $1 AND dovshop_included = true ORDER BY rank",
                source_image_id,
            )

        if not mockups:
            continue

        # Pick primary by cycling: product index + offset mod number of mockups
        primary_idx = (idx + request.start_offset) % len(mockups)
        primary_id = mockups[primary_idx]["id"]

        # Set primary (unsets others for this image)
        await db.set_image_mockup_dovshop_primary(primary_id, source_image_id)

        # Re-sync to DovShop (primary first in image list)
        dovshop_product_id = product["dovshop_product_id"]
        images = await _get_mockup_images(pool, source_image_id, base_url)
        if images and dovshop_product_id:
            try:
                await dovshop_client.update_product(dovshop_product_id, {
                    "images": images,
                    "mockupUrl": images[0],
                })
                updated += 1
            except Exception as e:
                logger.warning("Failed to update DovShop product %s: %s", dovshop_product_id, e)

    return {"total": total, "updated": updated}


# === AI Endpoints ===


class EnrichRequest(BaseModel):
    printify_product_id: str


@router.post("/dovshop/ai-enrich")
async def ai_enrich_product(request: EnrichRequest):
    """Use AI to determine categories, collection, and SEO description for a product."""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    product = await db.get_product_by_printify_id(request.printify_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    tags = product.get("tags") or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []

    collections = await dovshop_client.get_collections()
    try:
        categories = await dovshop_client.get_categories()
    except Exception:
        categories = []

    result = await enrich_product(
        title=product.get("title", ""),
        tags=tags,
        style=None,
        description=product.get("description", ""),
        image_url=product.get("image_url", ""),
        existing_collections=collections,
        existing_categories=categories,
    )
    return result


@router.post("/dovshop/ai-strategy")
async def ai_strategy():
    """Analyze full DovShop catalog and return AI recommendations."""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    products = await dovshop_client.get_products()
    collections = await dovshop_client.get_collections()
    try:
        categories = await dovshop_client.get_categories()
    except Exception:
        categories = []

    result = await analyze_catalog_strategy(products, collections, categories)
    if "error" in result and len(result) == 1:
        raise HTTPException(status_code=500, detail=result["error"])

    # Save to history
    await db.save_ai_strategy(result, product_count=len(products))
    return result


@router.get("/dovshop/ai-strategy/history")
async def ai_strategy_history(limit: int = 20):
    """Get history of AI strategy analyses."""
    items = await db.get_ai_strategy_history(limit=limit)
    return {"items": items}


@router.get("/dovshop/ai-strategy/latest")
async def ai_strategy_latest():
    """Get the most recent AI strategy analysis."""
    item = await db.get_ai_strategy_latest()
    if not item:
        return {"item": None}
    return {"item": item}


class ApplyCollectionRequest(BaseModel):
    name: str
    description: str = ""
    poster_ids: List[int] = []


@router.post("/dovshop/apply-collection")
async def apply_collection(request: ApplyCollectionRequest):
    """Create a collection and optionally assign posters to it."""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    collection = await dovshop_client.create_collection(
        name=request.name,
        description=request.description,
    )
    coll_id = collection.get("id")

    assigned = 0
    if coll_id and request.poster_ids:
        for pid in request.poster_ids:
            try:
                await dovshop_client.update_product(str(pid), {"collectionId": coll_id})
                assigned += 1
            except Exception:
                pass

    return {"success": True, "collection_id": coll_id, "assigned": assigned}


class ApplyFeatureRequest(BaseModel):
    poster_id: int
    featured: bool = True


@router.post("/dovshop/apply-feature")
async def apply_feature(request: ApplyFeatureRequest):
    """Set or unset featured status for a poster on DovShop."""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    await dovshop_client.update_product(str(request.poster_id), {"featured": request.featured})
    return {"success": True}


class ApplySeoRequest(BaseModel):
    poster_id: int
    description: str


@router.post("/dovshop/apply-seo")
async def apply_seo(request: ApplySeoRequest):
    """Update a poster's description on DovShop."""
    if not dovshop_client.is_configured:
        raise HTTPException(status_code=400, detail="DovShop not configured")

    await dovshop_client.update_product(str(request.poster_id), {"description": request.description})
    return {"success": True}
