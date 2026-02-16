import re
import io
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
import httpx
from PIL import Image
from printify import PrintifyAPI
from pricing import get_minimum_price
from sizes import PRINTIFY_SCALE, PRINTIFY_SCALE_DEFAULT
from dpi import analyze_sizes, get_size_groups
from upscaler import fit_image_to_ratio
from printify import DesignGroup
from deps import printify, upscale_service
import database as db

router = APIRouter(tags=["printify"])


@router.get("/printify/status")
async def get_printify_status():
    """Check if Printify is configured and accessible."""
    if not printify.is_configured:
        return {"configured": False, "connected": False}

    try:
        shops = await printify.get_shops()
        return {
            "configured": True,
            "connected": True,
            "shops": [{"id": s["id"], "title": s["title"]} for s in shops],
        }
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}


@router.get("/printify/products")
async def list_printify_products(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List products in the Printify shop."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.list_products(page=page, limit=limit)

        # Inject local mockup thumbnails where available
        products = result.get("data", [])
        if products:
            pids = [p["id"] for p in products]
            base_url = str(request.base_url).rstrip("/")
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT p.printify_product_id,
                           p.preferred_mockup_url,
                           (SELECT im.etsy_cdn_url
                            FROM image_mockups im
                            WHERE im.image_id = p.source_image_id
                              AND im.etsy_cdn_url IS NOT NULL
                            ORDER BY im.rank LIMIT 1) AS cdn_url,
                           (SELECT im.id
                            FROM image_mockups im
                            WHERE im.image_id = p.source_image_id
                            ORDER BY im.rank LIMIT 1) AS mockup_id
                    FROM products p
                    WHERE p.printify_product_id = ANY($1::text[])
                """, pids)
            mockup_map = {}
            for r in rows:
                url = r["preferred_mockup_url"] or r["cdn_url"]
                if not url and r["mockup_id"]:
                    url = f"{base_url}/mockups/serve/{r['mockup_id']}"
                if url:
                    mockup_map[r["printify_product_id"]] = url
            for p in products:
                url = mockup_map.get(p["id"])
                if url and p.get("images"):
                    # Prepend mockup as first image
                    p["images"].insert(0, {"src": url, "is_default": True, "is_mockup": True})

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/printify/products/{product_id}")
async def get_printify_product(product_id: str):
    """Get a single Printify product."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        product = await printify.get_product(product_id)
        return product
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/printify/mockups")
async def get_printify_mockups():
    """Get all Printify products with their mockup images and Etsy linkage."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        all_products = []
        page = 1
        while True:
            result = await printify.list_products(page=page, limit=50)
            data = result.get("data", [])
            all_products.extend(data)
            total = result.get("total", 0)
            if page * 50 >= total or not data:
                break
            page += 1

        # Reverse map: variant_id -> size label
        vid_to_size = {vid: sz for sz, vid in PrintifyAPI.SIZE_VARIANT_IDS.items()}

        def extract_size_from_url(src: str) -> str:
            """Extract the rendered size from mockup URL path: /mockup/{pid}/{variant_id}/..."""
            m = re.search(r'/mockup/[^/]+/(\d+)/', src)
            if m:
                return vid_to_size.get(int(m.group(1)), "")
            return ""

        def extract_camera_label(src: str) -> str:
            m = re.search(r'camera_label=([^&]+)', src)
            return m.group(1) if m else ""

        mockups = []
        for p in all_products:
            images = p.get("images", [])
            if not images:
                continue
            external = p.get("external", {}) or {}
            mockups.append({
                "printify_id": p["id"],
                "title": p.get("title", ""),
                "etsy_listing_id": external.get("id"),
                "etsy_url": external.get("handle"),
                "images": [
                    {
                        "src": img.get("src", ""),
                        "is_default": img.get("is_default", False),
                        "position": img.get("position", "front"),
                        "variant_ids": img.get("variant_ids", []),
                        "size": extract_size_from_url(img.get("src", "")),
                        "camera_label": extract_camera_label(img.get("src", "")),
                    }
                    for img in images
                ],
            })
        return mockups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/printify/products/{product_id}/publish")
async def publish_printify_product(product_id: str):
    """Publish a product to the connected store (Etsy)."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        # Skip Printify images if custom mockups are ready
        sync_images = True
        try:
            product = await db.get_product_by_printify_id(product_id)
            if product and product.get("source_image_id"):
                source_image_id = product["source_image_id"]
                pool = await db.get_pool()
                async with pool.acquire() as conn:
                    img_row = await conn.fetchrow(
                        "SELECT mockup_status FROM generated_images WHERE id = $1",
                        source_image_id,
                    )
                if img_row and img_row["mockup_status"] == "approved":
                    mockups = await db.get_image_mockups(source_image_id)
                    included = [m for m in mockups if m.get("is_included", True)]
                    if included:
                        sync_images = False
        except Exception:
            pass  # Fallback to sync_images=True

        result = await printify.publish_product(product_id, sync_images=sync_images)
        return {"ok": True, "result": result, "sync_images": sync_images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/printify/products/{product_id}/unpublish")
async def unpublish_printify_product(product_id: str):
    """Unpublish a product from the connected store."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.unpublish_product(product_id)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/printify/products/{product_id}")
async def delete_printify_product(product_id: str):
    """Delete a product from Printify."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        await printify.delete_product(product_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateProductRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    variants: Optional[List[dict]] = None


@router.put("/printify/products/{product_id}")
async def update_printify_product(product_id: str, request: UpdateProductRequest):
    """Update product details on Printify."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.update_product(
            product_id=product_id,
            title=request.title,
            description=request.description,
            tags=request.tags,
            variants=request.variants,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/printify/products/{product_id}/republish")
async def republish_printify_product(product_id: str):
    """Re-publish product to push updates to Etsy."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.publish_product(product_id)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === FIX EXISTING PRODUCTS ===

@router.post("/printify/fix-existing-products")
async def fix_existing_products(
    dry_run: bool = Query(default=True, description="Preview changes without applying"),
):
    """Disable blurry large-size variants on existing products.

    Disables 24x36 variants (removed size) and optionally 16x20, 18x24
    that were created before DPI-aware sizing was implemented.
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    large_variant_ids = [
        43150,  # 24x36 (removed from SIZE_VARIANT_IDS but still on old products)
    ]

    try:
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])

        fixed = []
        skipped = []

        for product in products:
            pid = product["id"]
            title = product.get("title", "Untitled")
            variants = product.get("variants", [])

            # Check if any large variants are currently enabled
            enabled_large = [
                v for v in variants
                if v["id"] in large_variant_ids and v.get("is_enabled", False)
            ]

            if not enabled_large:
                skipped.append({"id": pid, "title": title, "reason": "no large variants enabled"})
                continue

            if dry_run:
                fixed.append({
                    "id": pid,
                    "title": title,
                    "variants_to_disable": [v["id"] for v in enabled_large],
                    "action": "would_disable",
                })
            else:
                await printify.disable_variants(pid, large_variant_ids)

                # Re-publish to sync changes to Etsy
                external = product.get("external")
                if external and external.get("id"):
                    try:
                        await printify.publish_product(pid)
                    except Exception:
                        pass  # Non-fatal if republish fails

                fixed.append({
                    "id": pid,
                    "title": title,
                    "variants_disabled": [v["id"] for v in enabled_large],
                    "action": "disabled",
                })

        return {
            "dry_run": dry_run,
            "fixed": fixed,
            "skipped": skipped,
            "total_fixed": len(fixed),
            "total_skipped": len(skipped),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/disable-size/{size_key}")
async def disable_size_on_all_products(
    size_key: str,
    dry_run: bool = Query(default=True),
):
    """Disable a specific size variant on ALL existing Printify products."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    # Include removed sizes so we can still disable them on old products
    ALL_VARIANT_IDS = {**PrintifyAPI.SIZE_VARIANT_IDS, "24x36": 43150}
    variant_id = ALL_VARIANT_IDS.get(size_key)
    if not variant_id:
        raise HTTPException(status_code=400, detail=f"Unknown size: {size_key}")

    results = []
    page = 1
    while True:
        batch = await printify.list_products(page=page, limit=50)
        products = batch.get("data", [])
        if not products:
            break

        for product in products:
            pid = product["id"]
            title = product.get("title", "Untitled")
            variants = product.get("variants", [])

            enabled_match = [
                v for v in variants
                if v["id"] == variant_id and v.get("is_enabled", False)
            ]

            if not enabled_match:
                results.append({"id": pid, "title": title, "action": "already_disabled"})
                continue

            if dry_run:
                results.append({"id": pid, "title": title, "action": "would_disable"})
            else:
                await printify.disable_variants(pid, [variant_id])
                external = product.get("external")
                if external and external.get("id"):
                    try:
                        await printify.publish_product(pid)
                    except Exception:
                        pass
                results.append({"id": pid, "title": title, "action": "disabled"})

        page += 1

    return {
        "size": size_key,
        "variant_id": variant_id,
        "dry_run": dry_run,
        "results": results,
        "total_disabled": sum(1 for r in results if r["action"] in ("disabled", "would_disable")),
    }


@router.post("/products/fix-pricing")
async def fix_product_pricing(
    dry_run: bool = Query(default=True, description="Preview changes without applying"),
):
    """Sanitize pricing on ALL existing Printify products.

    - Disables unknown variants (squares, non-standard sizes)
    - Enforces minimum prices on known variants so no sale is at a loss
    - Optionally re-publishes to sync changes to Etsy
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    results = []
    page = 1
    known_vids = set(PrintifyAPI.SIZE_VARIANT_IDS.values())
    vid_to_size = {vid: sk for sk, vid in PrintifyAPI.SIZE_VARIANT_IDS.items()}

    try:
        while True:
            batch = await printify.list_products(page=page, limit=50)
            products = batch.get("data", [])
            if not products:
                break

            for product in products:
                pid = product["id"]
                title = product.get("title", "Untitled")
                variants = product.get("variants", [])

                issues = []
                for v in variants:
                    vid = v["id"]
                    price_cents = v.get("price", 0)
                    is_enabled = v.get("is_enabled", False)

                    if vid not in known_vids and is_enabled:
                        issues.append({
                            "variant_id": vid,
                            "issue": "unknown_variant_enabled",
                            "price": price_cents / 100,
                        })
                    elif vid in known_vids:
                        size_key = vid_to_size[vid]
                        min_cents = int(get_minimum_price(size_key) * 100)
                        if price_cents < min_cents and is_enabled:
                            issues.append({
                                "variant_id": vid,
                                "size": size_key,
                                "issue": "price_below_minimum",
                                "current_price": price_cents / 100,
                                "minimum_price": min_cents / 100,
                            })

                if not issues:
                    results.append({
                        "id": pid,
                        "title": title,
                        "action": "ok",
                    })
                    continue

                if dry_run:
                    results.append({
                        "id": pid,
                        "title": title,
                        "action": "would_fix",
                        "issues": issues,
                    })
                else:
                    try:
                        fix_result = await printify.sanitize_product_variants(pid, product)
                        # Re-publish to Etsy if already published
                        republished = False
                        external = product.get("external")
                        if external and external.get("id"):
                            try:
                                await printify.publish_product(pid)
                                republished = True
                            except Exception:
                                pass
                        results.append({
                            "id": pid,
                            "title": title,
                            "action": "fixed",
                            "issues": issues,
                            "fix_result": fix_result,
                            "republished": republished,
                        })
                    except Exception as exc:
                        results.append({
                            "id": pid,
                            "title": title,
                            "action": "error",
                            "issues": issues,
                            "error": str(exc),
                        })

            page += 1

        total_issues = sum(1 for r in results if r["action"] in ("would_fix", "fixed"))
        return {
            "dry_run": dry_run,
            "results": results,
            "total_products": len(results),
            "total_with_issues": total_issues,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/printify/upgrade-product/{product_id}")
async def upgrade_product_with_upscale(product_id: str):
    """Upgrade an existing product with per-size cropped + upscaled images.

    Each poster size gets its own image cropped to the exact aspect ratio
    and resized to exact Printify target pixels. Eliminates white padding.
    Unknown variants (squares etc.) get the original unfitted image.
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        # Get current product
        product = await printify.get_product(product_id)
        title = product.get("title", "Untitled")

        # Find the original design image from print_areas (not mockups)
        source_url = None
        for pa in product.get("print_areas", []):
            for ph in pa.get("placeholders", []):
                for img in ph.get("images", []):
                    if img.get("src"):
                        source_url = img["src"]
                        break
                if source_url:
                    break
            if source_url:
                break

        if not source_url:
            raise HTTPException(status_code=400, detail="No design image found in print_areas")

        # Download source image
        async with httpx.AsyncClient() as client:
            resp = await client.get(source_url, timeout=60.0)
            resp.raise_for_status()
            source_bytes = resp.content

        # Get dimensions and analyze DPI
        img = Image.open(io.BytesIO(source_bytes))
        src_w, src_h = img.size
        analysis = analyze_sizes(src_w, src_h)
        _original_ok, _needs_upscale, skip = get_size_groups(analysis)

        sellable = [k for k, sa in analysis.items() if sa.is_sellable]
        if not sellable:
            raise HTTPException(
                status_code=400,
                detail=f"No sellable sizes for {src_w}x{src_h} image",
            )

        filename_prefix = f"upgrade_{product_id}_{int(time.time())}"

        # Collect ALL variant IDs from the product (Printify requires all in print_areas)
        all_product_variant_ids = [v["id"] for v in product.get("variants", [])]
        assigned_variant_ids = set()

        design_groups = []
        enabled_sizes = set()

        # Per-size: crop to exact ratio, resize to exact target pixels
        for size_key in sellable:
            sa = analysis[size_key]
            target_ratio = sa.target_width / sa.target_height

            try:
                cropped = fit_image_to_ratio(source_bytes, target_ratio)
                resized = upscale_service.upscale_to_target(
                    cropped, sa.target_width, sa.target_height,
                )
                upload = await printify.upload_image_base64(
                    image_bytes=resized,
                    filename=f"{filename_prefix}_{size_key}.jpg",
                )
                design_groups.append(
                    DesignGroup(image_id=upload["id"], variant_ids=[sa.variant_id])
                )
                enabled_sizes.add(size_key)
                assigned_variant_ids.add(sa.variant_id)
            except Exception:
                pass  # Skip this size on failure

        # All remaining variant IDs (skipped sizes + unknown squares etc.)
        # go with original unfitted image
        remaining_vids = [
            vid for vid in all_product_variant_ids
            if vid not in assigned_variant_ids
        ]
        if remaining_vids:
            original_upload = await printify.upload_image(
                image_url=source_url,
                filename=f"{filename_prefix}_original.png",
            )
            design_groups.append(
                DesignGroup(image_id=original_upload["id"], variant_ids=remaining_vids)
            )

        # Build print_areas payload with per-size scale overrides
        vid_to_size = {vid: sk for sk, vid in PrintifyAPI.SIZE_VARIANT_IDS.items()}
        print_areas = []
        for group in design_groups:
            size_key = vid_to_size.get(group.variant_ids[0]) if len(group.variant_ids) == 1 else None
            scale = PRINTIFY_SCALE.get(size_key, PRINTIFY_SCALE_DEFAULT) if size_key else PRINTIFY_SCALE_DEFAULT
            print_areas.append({
                "variant_ids": group.variant_ids,
                "placeholders": [{
                    "position": "front",
                    "images": [{
                        "id": group.image_id,
                        "x": 0.5,
                        "y": 0.5,
                        "scale": scale,
                        "angle": 0,
                    }],
                }],
            })

        # Build updated variants with correct enabled state
        updated_variants = []
        for v in product.get("variants", []):
            vid = v["id"]
            size_key = None
            for sk, sv_id in PrintifyAPI.SIZE_VARIANT_IDS.items():
                if sv_id == vid:
                    size_key = sk
                    break
            if size_key:
                is_enabled = size_key in enabled_sizes
            else:
                is_enabled = v.get("is_enabled", False)
            updated_variants.append({
                "id": vid,
                "price": v["price"],
                "is_enabled": is_enabled,
            })

        # Update product with new print_areas and variants
        await printify.update_product(
            product_id=product_id,
            variants=updated_variants,
            print_areas=print_areas,
        )

        # Re-publish to Etsy if already published
        was_published = False
        external = product.get("external")
        if external and external.get("id"):
            try:
                await printify.publish_product(product_id)
                was_published = True
            except Exception:
                pass

        dpi_dict = {k: v.to_dict() for k, v in analysis.items()}
        return {
            "product_id": product_id,
            "title": title,
            "source_resolution": f"{src_w}x{src_h}",
            "enabled_sizes": sorted(enabled_sizes),
            "skipped_sizes": skip,
            "design_groups": len(design_groups),
            "upscale_backend": upscale_service.backend_name,
            "republished": was_published,
            "dpi_analysis": dpi_dict,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/printify/upgrade-all-products")
async def upgrade_all_products(
    dry_run: bool = Query(default=True, description="Preview changes without applying"),
):
    """Upgrade ALL existing products with DPI-aware upscaled images.

    For each product: downloads source image, upscales, updates print_areas,
    enables all sellable sizes, re-publishes.
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])

        results = []
        for product in products:
            pid = product["id"]
            title = product.get("title", "Untitled")

            if dry_run:
                # Just analyze what would happen — get design from print_areas
                source_url = None
                for pa in product.get("print_areas", []):
                    for ph in pa.get("placeholders", []):
                        for img_pa in ph.get("images", []):
                            if img_pa.get("src"):
                                source_url = img_pa["src"]
                                break
                        if source_url:
                            break
                    if source_url:
                        break

                if not source_url:
                    results.append({"id": pid, "title": title, "action": "skip", "reason": "no image"})
                    continue

                # Download to check dimensions
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(source_url, timeout=30.0)
                        resp.raise_for_status()
                        img_obj = Image.open(io.BytesIO(resp.content))
                        src_w, src_h = img_obj.size

                    analysis = analyze_sizes(src_w, src_h)
                    ok, up, sk = get_size_groups(analysis)

                    # Check currently enabled variants
                    current_enabled = [
                        v["id"] for v in product.get("variants", [])
                        if v.get("is_enabled", False)
                    ]

                    results.append({
                        "id": pid,
                        "title": title,
                        "action": "would_upgrade",
                        "source_resolution": f"{src_w}x{src_h}",
                        "would_enable": sorted(ok + up),
                        "would_skip": sk,
                        "currently_enabled_count": len(current_enabled),
                    })
                except Exception as exc:
                    results.append({"id": pid, "title": title, "action": "skip", "reason": str(exc)})
            else:
                # Actually upgrade
                try:
                    upgrade_result = await upgrade_product_with_upscale(pid)
                    results.append({
                        "id": pid,
                        "title": title,
                        "action": "upgraded",
                        "enabled_sizes": upgrade_result.get("enabled_sizes", []),
                        "upscale_backend": upgrade_result.get("upscale_backend", ""),
                    })
                except Exception as exc:
                    results.append({"id": pid, "title": title, "action": "failed", "error": str(exc)})

        return {
            "dry_run": dry_run,
            "products": results,
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/fix-scales")
async def fix_product_scales(
    dry_run: bool = Query(default=True),
):
    """Fix print_area scale values on ALL existing products.

    Reads the current PRINTIFY_SCALE config and updates every product's
    print_areas so that each variant uses the correct scale.  This fixes
    the white-stripe issue on 24x36 (and any future scale tweaks).
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    vid_to_size = {vid: sk for sk, vid in PrintifyAPI.SIZE_VARIANT_IDS.items()}
    results = []

    try:
        page = 1
        while True:
            batch = await printify.list_products(page=page, limit=50)
            products = batch.get("data", [])
            if not products:
                break

            for product in products:
                pid = product["id"]
                title = product.get("title", "Untitled")
                old_print_areas = product.get("print_areas", [])

                needs_update = False
                new_print_areas = []

                for pa in old_print_areas:
                    pa_vids = pa.get("variant_ids", [])
                    new_pa = {**pa}
                    new_placeholders = []

                    for ph in pa.get("placeholders", []):
                        new_ph = {**ph}
                        new_images = []

                        for img in ph.get("images", []):
                            new_img = {**img}
                            old_scale = img.get("scale", 1.0)

                            # Determine correct scale for these variants
                            if len(pa_vids) == 1:
                                size_key = vid_to_size.get(pa_vids[0])
                                correct_scale = PRINTIFY_SCALE.get(size_key, PRINTIFY_SCALE_DEFAULT) if size_key else PRINTIFY_SCALE_DEFAULT
                            else:
                                # Multi-variant group: use max needed scale
                                scales = []
                                for vid in pa_vids:
                                    sk = vid_to_size.get(vid)
                                    scales.append(PRINTIFY_SCALE.get(sk, PRINTIFY_SCALE_DEFAULT) if sk else PRINTIFY_SCALE_DEFAULT)
                                correct_scale = max(scales) if scales else PRINTIFY_SCALE_DEFAULT

                            if abs(old_scale - correct_scale) > 0.001:
                                needs_update = True
                                new_img["scale"] = correct_scale

                            new_images.append(new_img)

                        new_ph["images"] = new_images
                        new_placeholders.append(new_ph)

                    new_pa["placeholders"] = new_placeholders
                    new_print_areas.append(new_pa)

                if not needs_update:
                    results.append({"id": pid, "title": title, "action": "ok"})
                    continue

                if dry_run:
                    changes = []
                    for pa, new_pa in zip(old_print_areas, new_print_areas):
                        for ph, new_ph in zip(pa.get("placeholders", []), new_pa.get("placeholders", [])):
                            for img, new_img in zip(ph.get("images", []), new_ph.get("images", [])):
                                if abs(img.get("scale", 1.0) - new_img.get("scale", 1.0)) > 0.001:
                                    vids = pa.get("variant_ids", [])
                                    size_names = [vid_to_size.get(v, "?") for v in vids]
                                    changes.append(f"{','.join(size_names)}: {img.get('scale')}->{new_img.get('scale')}")
                    results.append({"id": pid, "title": title, "action": "would_fix", "changes": changes})
                else:
                    try:
                        await printify.update_product(product_id=pid, print_areas=new_print_areas)
                        # Re-publish if already on Etsy
                        external = product.get("external")
                        if external and external.get("id"):
                            try:
                                await printify.publish_product(pid)
                            except Exception:
                                pass
                        results.append({"id": pid, "title": title, "action": "fixed"})
                    except Exception as exc:
                        results.append({"id": pid, "title": title, "action": "failed", "error": str(exc)})

            page += 1

        return {
            "dry_run": dry_run,
            "products": results,
            "total": len(results),
            "fixed": sum(1 for r in results if r["action"] in ("fixed", "would_fix")),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
