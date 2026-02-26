import asyncio
import logging
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import httpx
from printify import PrintifyAPI
from deps import printify, etsy as etsy_service, listing_gen, publish_scheduler
from routes.etsy_auth import ensure_etsy_token
import database as db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["products"])


async def _import_printify_product(p: dict) -> dict:
    """Import a single Printify product into local DB. Returns saved product dict."""
    pid = p["id"]
    image_url = None
    for img in p.get("images", []):
        if img.get("is_default"):
            image_url = img.get("src")
            break
    if not image_url and p.get("images"):
        image_url = p["images"][0].get("src")

    external = p.get("external") or {}
    etsy_listing_id = str(external["id"]) if external.get("id") else None

    product = await db.save_product(
        printify_product_id=pid,
        title=p.get("title", "Untitled"),
        description=p.get("description", ""),
        tags=p.get("tags", []),
        image_url=image_url,
        status="published" if etsy_listing_id else "draft",
    )
    if etsy_listing_id:
        await db.update_product_status(pid, product["status"], etsy_listing_id)
        product["etsy_listing_id"] = etsy_listing_id
    return product


@router.post("/products/sync")
async def sync_products_from_printify():
    """Import all Printify products into local DB. Skips existing ones."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    # Fetch all from Printify
    all_products = []
    page = 1
    while True:
        result = await printify.list_products(page=page, limit=50)
        data = result.get("data", [])
        all_products.extend(data)
        if page * 50 >= result.get("total", 0) or not data:
            break
        page += 1

    # Check which exist locally
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        existing = {
            r["printify_product_id"]
            for r in await conn.fetch("SELECT printify_product_id FROM products")
        }

    imported = 0
    skipped = 0
    for p in all_products:
        if p["id"] in existing:
            skipped += 1
            continue
        try:
            await _import_printify_product(p)
            imported += 1
        except Exception as e:
            logger.warning(f"Failed to import {p['id']}: {e}")

    return {"total": len(all_products), "imported": imported, "skipped": skipped}


@router.get("/products")
async def list_products(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List all tracked products. Optional ?status=draft|scheduled|published|failed."""
    return await db.get_all_products(status=status, limit=limit, offset=offset)


@router.get("/products/{printify_product_id}")
async def get_product(printify_product_id: str):
    """Get a single product by Printify ID, including source image info."""
    product = await db.get_product_by_printify_id(printify_product_id)
    if not product:
        # Fallback: import from Printify if it exists there
        if printify.is_configured:
            try:
                p = await printify.get_product(printify_product_id)
                product = await _import_printify_product(p)
            except Exception:
                raise HTTPException(status_code=404, detail="Product not found")
        else:
            raise HTTPException(status_code=404, detail="Product not found")

    # Enrich with source image details if linked
    if product.get("source_image_id"):
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            source = await conn.fetchrow(
                "SELECT id, generation_id, url, mockup_url, mockup_status FROM generated_images WHERE id = $1",
                product["source_image_id"],
            )
            if source:
                product["source_image"] = dict(source)

    return product


# ------------------------------------------------------------------
# Source image linking
# ------------------------------------------------------------------

class LinkImageRequest(BaseModel):
    image_id: int


@router.post("/products/{printify_product_id}/link-image")
async def link_source_image(printify_product_id: str, request: LinkImageRequest):
    """Manually link a generated image to a product (both directions)."""
    product = await db.get_product_by_printify_id(printify_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        image = await conn.fetchrow(
            "SELECT id, url FROM generated_images WHERE id = $1", request.image_id
        )
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    await db.link_image_to_product(request.image_id, product["id"])
    return {"success": True, "product_id": product["id"], "image_id": request.image_id}


@router.get("/generated-images/unlinked")
async def list_unlinked_images(limit: int = 50, offset: int = 0):
    """List generated images that are not linked to any product."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT gi.id, gi.generation_id, gi.url, gi.created_at,
                   g.prompt, g.style
            FROM generated_images gi
            JOIN generations g ON g.generation_id = gi.generation_id
            WHERE gi.product_id IS NULL
            ORDER BY gi.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM generated_images WHERE product_id IS NULL"
        )
    return {
        "items": [dict(r) for r in rows],
        "total": total,
    }


# ------------------------------------------------------------------
# Mockup endpoints
# ------------------------------------------------------------------

@router.get("/products/{printify_product_id}/mockups")
async def get_product_mockups(printify_product_id: str):
    """List all mockup images for a product — from local DB (Etsy CDN) first, Printify as fallback."""
    # Try local DB first (our composed mockups with Etsy CDN URLs)
    local = await db.get_product_by_printify_id(printify_product_id)
    if local and local.get("source_image_id"):
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT im.*, mt.name AS camera_label
                FROM image_mockups im
                JOIN mockup_templates mt ON mt.id = im.template_id
                WHERE im.image_id = $1 AND im.is_included = true
                ORDER BY im.rank ASC
            """, local["source_image_id"])

        if rows:
            preferred = local.get("preferred_mockup_url") or ""
            mockups = []
            for row in rows:
                src = row["etsy_cdn_url"] or row["mockup_data"]
                is_primary = (src == preferred) if preferred else (row["rank"] == 1)
                mockups.append({
                    "src": src,
                    "is_default": is_primary,
                    "position": "front",
                    "variant_ids": [],
                    "camera_label": row["camera_label"] or "",
                    "size": "",
                })
            return {
                "printify_product_id": printify_product_id,
                "title": local.get("title", ""),
                "mockups": mockups,
            }

    # Fallback: Printify API
    if not printify.is_configured:
        return {"printify_product_id": printify_product_id, "title": "", "mockups": []}

    try:
        product = await printify.get_product(printify_product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    vid_to_size = {vid: sz for sz, vid in PrintifyAPI.SIZE_VARIANT_IDS.items()}

    images = product.get("images", [])
    mockups = []
    for img in images:
        src = img.get("src", "")
        m = re.search(r'camera_label=([^&]+)', src)
        camera_label = m.group(1) if m else ""
        m2 = re.search(r'/mockup/[^/]+/(\d+)/', src)
        size = vid_to_size.get(int(m2.group(1)), "") if m2 else ""

        mockups.append({
            "src": src,
            "is_default": img.get("is_default", False),
            "position": img.get("position", "front"),
            "variant_ids": img.get("variant_ids", []),
            "camera_label": camera_label,
            "size": size,
        })

    return {
        "printify_product_id": printify_product_id,
        "title": product.get("title", ""),
        "mockups": mockups,
    }


class SetPrimaryMockupRequest(BaseModel):
    mockup_url: str


@router.post("/products/{printify_product_id}/set-primary-mockup")
async def set_primary_mockup(printify_product_id: str, request: SetPrimaryMockupRequest):
    """Download a Printify mockup and upload it as the primary (rank=1) image on Etsy."""
    # Get Etsy listing ID from local DB or Printify
    local = await db.get_product_by_printify_id(printify_product_id)
    etsy_listing_id = local.get("etsy_listing_id") if local else None

    if not etsy_listing_id:
        # Try fetching from Printify
        if not printify.is_configured:
            raise HTTPException(status_code=400, detail="Printify not configured")
        try:
            product = await printify.get_product(printify_product_id)
            external = product.get("external") or {}
            etsy_listing_id = str(external["id"]) if external.get("id") else None
        except Exception:
            pass

    if not etsy_listing_id:
        raise HTTPException(status_code=400, detail="No Etsy listing found for this product")

    access_token, shop_id = await ensure_etsy_token()

    # Download the mockup image
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(request.mockup_url, timeout=30.0)
            resp.raise_for_status()
            image_bytes = resp.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download mockup: {e}")

    # Upload to Etsy as primary image (rank=1)
    if not etsy_service:
        raise HTTPException(status_code=500, detail="Etsy service not configured")

    try:
        result = await etsy_service.upload_listing_image(
            access_token, shop_id, etsy_listing_id,
            image_bytes, "primary_mockup.jpg", rank=1,
        )
        return {
            "ok": True,
            "etsy_listing_id": etsy_listing_id,
            "image_id": result.get("listing_image_id"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload to Etsy: {e}")


@router.post("/products/{printify_product_id}/upload-mockup")
async def upload_custom_mockup(
    printify_product_id: str,
    image: UploadFile = File(...),
    rank: Optional[int] = None,
):
    """Upload a custom mockup image to the Etsy listing for this product."""
    # Get Etsy listing ID
    local = await db.get_product_by_printify_id(printify_product_id)
    etsy_listing_id = local.get("etsy_listing_id") if local else None

    if not etsy_listing_id:
        if not printify.is_configured:
            raise HTTPException(status_code=400, detail="Printify not configured")
        try:
            product = await printify.get_product(printify_product_id)
            external = product.get("external") or {}
            etsy_listing_id = str(external["id"]) if external.get("id") else None
        except Exception:
            pass

    if not etsy_listing_id:
        raise HTTPException(status_code=400, detail="No Etsy listing found for this product")

    access_token, shop_id = await ensure_etsy_token()

    if not etsy_service:
        raise HTTPException(status_code=500, detail="Etsy service not configured")

    image_bytes = await image.read()
    filename = image.filename or "custom_mockup.jpg"

    try:
        result = await etsy_service.upload_listing_image(
            access_token, shop_id, etsy_listing_id,
            image_bytes, filename, rank=rank,
        )
        return {
            "ok": True,
            "etsy_listing_id": etsy_listing_id,
            "image_id": result.get("listing_image_id"),
            "rank": rank,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload to Etsy: {e}")


class SetPreferredMockupRequest(BaseModel):
    mockup_url: Optional[str] = None  # null to clear


@router.put("/products/{printify_product_id}/preferred-mockup")
async def set_preferred_mockup(printify_product_id: str, request: SetPreferredMockupRequest):
    """Set or clear the preferred mockup URL for a product.

    When set, the scheduler will use this specific mockup as the primary Etsy image
    after publish, overriding the global preferred_primary_camera setting.
    """
    updated = await db.set_product_preferred_mockup(printify_product_id, request.mockup_url)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "printify_product_id": printify_product_id,
        "preferred_mockup_url": request.mockup_url,
    }


@router.post("/products/fix-descriptions")
async def fix_descriptions():
    """Compare local DB descriptions with live Etsy descriptions and fix mismatches.

    Useful for correcting descriptions that Printify has overwritten.
    """
    if not etsy_service:
        raise HTTPException(status_code=400, detail="Etsy service not configured")

    access_token, shop_id = await ensure_etsy_token()

    products = await db.get_all_products(status="published", limit=200)
    items = products.get("items", [])

    results = []
    for product in items:
        etsy_listing_id = product.get("etsy_listing_id")
        local_desc = product.get("description")
        if not etsy_listing_id or not local_desc:
            continue

        try:
            listing = await etsy_service.get_listing(access_token, etsy_listing_id)
            etsy_desc = listing.get("description", "")

            if etsy_desc.strip() != local_desc.strip():
                await etsy_service.update_listing(
                    access_token, shop_id, etsy_listing_id,
                    {"description": local_desc},
                )
                results.append({
                    "printify_product_id": product["printify_product_id"],
                    "etsy_listing_id": etsy_listing_id,
                    "status": "fixed",
                    "title": product.get("title", "")[:60],
                })
                logger.info("Fixed description for %s (etsy=%s)",
                            product["printify_product_id"], etsy_listing_id)
            else:
                results.append({
                    "printify_product_id": product["printify_product_id"],
                    "etsy_listing_id": etsy_listing_id,
                    "status": "ok",
                })

            await asyncio.sleep(0.5)
        except Exception as e:
            results.append({
                "printify_product_id": product["printify_product_id"],
                "etsy_listing_id": etsy_listing_id,
                "status": "error",
                "error": str(e),
            })

    return {
        "total_checked": sum(1 for r in results if r["status"] != "error"),
        "fixed": sum(1 for r in results if r["status"] == "fixed"),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }


class SeoRefreshRequest(BaseModel):
    max_items: int = 10
    min_days_since_publish: int = 14
    max_views: int = 5


@router.post("/products/auto-seo-refresh")
async def auto_seo_refresh(request: SeoRefreshRequest = SeoRefreshRequest()):
    """Manually trigger SEO refresh for underperforming listings.

    Finds listings with low views, regenerates title/tags/description via Claude,
    updates on Etsy, and logs changes.
    """
    if not etsy_service:
        raise HTTPException(status_code=400, detail="Etsy service not configured")
    if not listing_gen or not listing_gen.api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")

    access_token, shop_id = await ensure_etsy_token()

    candidates = await db.get_seo_refresh_candidates(
        min_days_since_publish=request.min_days_since_publish,
        max_views=request.max_views,
        limit=request.max_items,
    )

    results = []
    for product in candidates:
        pid = product["printify_product_id"]
        etsy_listing_id = product["etsy_listing_id"]

        try:
            listing = await etsy_service.get_listing(access_token, etsy_listing_id)
            old_title = listing.get("title", "")
            old_tags = listing.get("tags", [])
            old_desc = listing.get("description", "")

            new_listing = await listing_gen.regenerate_seo_from_existing(
                current_title=old_title,
                current_tags=old_tags,
                current_description=old_desc,
            )

            await etsy_service.update_listing(access_token, shop_id, etsy_listing_id, {
                "title": new_listing.title,
                "tags": new_listing.tags,
                "description": new_listing.description,
            })

            # Update local DB
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE products SET description = $1, title = $2, tags = $3, updated_at = NOW() WHERE printify_product_id = $4",
                    new_listing.description, new_listing.title, new_listing.tags, pid,
                )

            await db.save_seo_refresh_log(
                printify_product_id=pid,
                etsy_listing_id=etsy_listing_id,
                reason="low_views",
                old_title=old_title,
                new_title=new_listing.title,
                old_tags=old_tags,
                new_tags=new_listing.tags,
            )

            results.append({
                "printify_product_id": pid,
                "etsy_listing_id": etsy_listing_id,
                "status": "refreshed",
                "old_title": old_title[:80],
                "new_title": new_listing.title[:80],
                "views": product.get("total_views", 0),
            })

            await asyncio.sleep(2)
        except Exception as e:
            results.append({
                "printify_product_id": pid,
                "etsy_listing_id": etsy_listing_id,
                "status": "error",
                "error": str(e),
            })

    return {
        "candidates_found": len(candidates),
        "refreshed": sum(1 for r in results if r["status"] == "refreshed"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
