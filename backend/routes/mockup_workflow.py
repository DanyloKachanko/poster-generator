"""Mockup workflow, serving, and bulk operation routes.

Split from routes/mockups.py — handles approval workflow, image serving, and bulk operations.
"""

import asyncio
import base64
import io
import json
import logging
import random
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routes.mockup_utils import _compose_all_templates, _upload_multi_images_to_etsy
from routes.etsy_auth import ensure_etsy_token
import database as db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mockups"])


# --- Workflow: Cleanup Originals ---

@router.post("/mockups/workflow/cleanup-originals")
async def cleanup_original_posters():
    """Remove non-mockup images from all Etsy listings. Keeps only known mockup images."""
    from deps import etsy

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT p.id, p.etsy_listing_id,
                   array_agg(im.etsy_image_id) FILTER (WHERE im.etsy_image_id IS NOT NULL AND im.etsy_image_id != '') as mockup_etsy_ids
            FROM products p
            JOIN generated_images gi ON gi.id = p.source_image_id
            JOIN image_mockups im ON im.image_id = gi.id
            WHERE p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
              AND gi.mockup_status = 'approved'
            GROUP BY p.id, p.etsy_listing_id
            """
        )

    if not rows:
        return {"total": 0, "cleaned": 0, "deleted_images": 0}

    try:
        access_token, shop_id = await ensure_etsy_token()
    except Exception as e:
        return {"error": str(e)}

    cleaned = 0
    total_deleted = 0
    for row in rows:
        try:
            known_ids = set(str(x) for x in (row["mockup_etsy_ids"] or []))
            images_resp = await etsy.get_listing_images(access_token, row["etsy_listing_id"])
            all_images = images_resp.get("results", [])

            # Find images that are NOT our mockups
            to_delete = [
                img["listing_image_id"] for img in all_images
                if str(img["listing_image_id"]) not in known_ids
            ]

            if not to_delete:
                continue

            # Keep at least 1 image (Etsy requirement) — only delete if we have mockups left
            if len(all_images) - len(to_delete) < 1:
                to_delete = to_delete[:-1]  # Keep one

            for img_id in to_delete:
                try:
                    await etsy.delete_listing_image(
                        access_token=access_token, shop_id=shop_id,
                        listing_id=row["etsy_listing_id"],
                        listing_image_id=str(img_id),
                    )
                    total_deleted += 1
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to delete image {img_id} from {row['etsy_listing_id']}: {e}")

            if to_delete:
                cleaned += 1
                logger.info(f"Listing {row['etsy_listing_id']}: deleted {len(to_delete)} non-mockup images")
        except Exception as e:
            logger.error(f"Error processing listing {row['etsy_listing_id']}: {e}")

    return {"total": len(rows), "cleaned": cleaned, "deleted_images": total_deleted}


# --- Workflow: Posters ---

@router.get("/mockups/workflow/posters")
async def get_workflow_posters(status: str = "pending", linked_only: bool = True):
    """Get posters for workflow. linked_only=true filters to product-linked images only."""
    posters = await db.get_workflow_posters(status=status, limit=100, linked_only=linked_only)
    return {"posters": posters, "count": len(posters)}


# --- Workflow: Approve ---

class ApproveRequest(BaseModel):
    excluded_template_ids: List[int] = []
    pack_id: Optional[int] = None


@router.post("/mockups/workflow/approve/{image_id}")
async def approve_poster(image_id: int, request: Optional[ApproveRequest] = None):
    """
    Approve a poster with multi-mockup:
    1. Get all active templates
    2. Compose poster with each template
    3. Save each to image_mockups table
    4. Update status to 'approved'
    5. Upload original poster + all mockups to Etsy
    """
    excluded = set(request.excluded_template_ids) if request else set()
    pack_id = request.pack_id if request else None

    # Fall back to default pack if none specified
    if not pack_id:
        default_val = await db.get_setting("default_pack_id")
        if default_val:
            pack_id = int(default_val)

    # Get image details
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        image = await conn.fetchrow(
            "SELECT * FROM generated_images WHERE id = $1", image_id
        )
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

    # Get templates: from pack if specified, else active templates
    if pack_id:
        pack = await db.get_mockup_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")
        all_templates = await db.get_pack_templates(pack_id)
        if not all_templates:
            raise HTTPException(status_code=400, detail=f"Pack '{pack['name']}' has no templates")
    else:
        all_templates = await db.get_active_mockup_templates()
        if not all_templates:
            raise HTTPException(
                status_code=400,
                detail="No active mockup templates. Please activate at least one template."
            )

    # Parse corners
    for t in all_templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])

    # Filter out excluded templates
    templates_to_compose = [t for t in all_templates if t["id"] not in excluded]

    try:
        # Compose poster with all templates
        color_grade = pack.get("color_grade", "none") if pack_id else "none"
        composed = await _compose_all_templates(image["url"], templates_to_compose, "fill", color_grade)

        # Delete old image_mockups and save new ones
        await db.delete_image_mockups(image_id)
        mockup_entries = []  # (db_id, png_bytes)
        for rank_idx, (tid, png_bytes) in enumerate(composed, start=2):
            b64 = base64.b64encode(png_bytes).decode()
            saved = await db.save_image_mockup(
                image_id=image_id,
                template_id=tid,
                mockup_data=f"data:image/png;base64,{b64}",
                rank=rank_idx,
                pack_id=pack_id,
            )
            mockup_entries.append((saved["id"], png_bytes))

        # Also save first mockup as legacy mockup_url for backward compat
        first_mockup_url = None
        if composed:
            b64 = base64.b64encode(composed[0][1]).decode()
            first_mockup_url = f"data:image/png;base64,{b64}"

        # Update status to approved
        await db.update_image_mockup_status(
            image_id=image_id,
            mockup_url=first_mockup_url,
            mockup_status="approved",
        )

        # Upload to Etsy
        etsy_upload_result = None
        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                if image.get("product_id"):
                    product = await conn.fetchrow(
                        "SELECT * FROM products WHERE id = $1",
                        image["product_id"]
                    )
                else:
                    product = await conn.fetchrow(
                        "SELECT * FROM products WHERE image_url = $1",
                        image["url"]
                    )

            if product and product["etsy_listing_id"]:
                access_token, shop_id = await ensure_etsy_token()

                # Shuffle mockup order so each product gets a random primary
                shuffled_entries = mockup_entries[:]
                random.shuffle(shuffled_entries)

                # Upload original poster + all mockups
                upload_results = await _upload_multi_images_to_etsy(
                    access_token=access_token,
                    shop_id=shop_id,
                    listing_id=product["etsy_listing_id"],
                    original_poster_url=image["url"],
                    mockup_entries=shuffled_entries,
                )

                # Save Etsy info back to image_mockups
                for ur in upload_results:
                    if ur.get("mockup_db_id") and ur.get("etsy_image_id"):
                        await db.update_image_mockup_etsy_info(
                            ur["mockup_db_id"],
                            ur["etsy_image_id"],
                            ur.get("etsy_cdn_url", ""),
                        )

                # Save first mockup CDN URL as preferred
                for ur in upload_results:
                    if ur.get("etsy_cdn_url") and ur["type"] == "mockup":
                        await db.set_product_preferred_mockup(
                            product["printify_product_id"], ur["etsy_cdn_url"]
                        )
                        break

                etsy_upload_result = {
                    "success": True,
                    "listing_id": product["etsy_listing_id"],
                    "images_uploaded": len(upload_results),
                }
            elif product:
                etsy_upload_result = {
                    "success": False,
                    "reason": "scheduled",
                    "product_status": product.get("status", "draft"),
                }
            else:
                etsy_upload_result = {"success": False, "reason": "no_product"}
        except Exception as e:
            etsy_upload_result = {"success": False, "error": str(e)}

        return {
            "success": True,
            "image_id": image_id,
            "mockups_composed": len(composed),
            "status": "approved",
            "etsy_upload": etsy_upload_result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Composition failed: {str(e)}")


class BatchApproveRequest(BaseModel):
    image_ids: List[int]
    pack_id: Optional[int] = None


@router.post("/mockups/workflow/approve-batch")
async def approve_batch(request: BatchApproveRequest):
    """Approve multiple posters sequentially. Returns per-image results."""
    results = []
    for image_id in request.image_ids:
        try:
            approve_req = ApproveRequest(pack_id=request.pack_id) if request.pack_id else None
            result = await approve_poster(image_id, approve_req)
            results.append({"image_id": image_id, "success": True, "etsy_upload": result.get("etsy_upload")})
        except Exception as e:
            results.append({"image_id": image_id, "success": False, "error": str(e)})
    succeeded = sum(1 for r in results if r["success"])
    etsy_ok = sum(1 for r in results if r.get("etsy_upload", {}).get("success"))
    return {
        "total": len(request.image_ids),
        "approved": succeeded,
        "etsy_uploaded": etsy_ok,
        "results": results,
    }


# --- Image Mockups per poster ---

@router.get("/mockups/workflow/image/{image_id}/mockups")
async def get_image_mockup_previews(image_id: int):
    """Get all composed mockup previews for a specific image."""
    mockups = await db.get_image_mockups(image_id)
    return {"image_id": image_id, "mockups": mockups}


@router.get("/mockups/serve/{mockup_id}")
async def serve_mockup_image(mockup_id: int):
    """Serve a composed mockup image directly from DB (base64 → binary)."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        data = await conn.fetchval(
            "SELECT mockup_data FROM image_mockups WHERE id = $1", mockup_id
        )
    if not data:
        raise HTTPException(status_code=404, detail="Mockup not found")
    # mockup_data is "data:image/png;base64,..." or raw base64
    if data.startswith("data:"):
        # Strip data URL prefix
        header, b64 = data.split(",", 1)
        media = header.split(";")[0].split(":")[1]  # e.g. image/png
    else:
        b64 = data
        media = "image/png"
    img_bytes = base64.b64decode(b64)
    return StreamingResponse(io.BytesIO(img_bytes), media_type=media)


@router.post("/mockups/workflow/toggle-mockup/{mockup_id}")
async def toggle_mockup_inclusion(mockup_id: int, is_included: bool = True):
    """Toggle whether a specific mockup is included in the Etsy upload."""
    success = await db.update_image_mockup_inclusion(mockup_id, is_included)
    if not success:
        raise HTTPException(status_code=404, detail="Mockup not found")
    return {"mockup_id": mockup_id, "is_included": is_included}


@router.post("/mockups/workflow/toggle-dovshop-mockup/{mockup_id}")
async def toggle_dovshop_mockup(mockup_id: int, dovshop_included: bool = True):
    """Toggle whether a specific mockup is included on DovShop (separate from Etsy)."""
    success = await db.update_image_mockup_dovshop_inclusion(mockup_id, dovshop_included)
    if not success:
        raise HTTPException(status_code=404, detail="Mockup not found")
    return {"mockup_id": mockup_id, "dovshop_included": dovshop_included}


@router.post("/mockups/workflow/set-dovshop-primary/{mockup_id}")
async def set_dovshop_primary(mockup_id: int):
    """Set a mockup as the primary (hero) image for DovShop."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT image_id FROM image_mockups WHERE id = $1", mockup_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Mockup not found")
    await db.set_image_mockup_dovshop_primary(mockup_id, row["image_id"])
    return {"mockup_id": mockup_id, "dovshop_primary": True}


@router.post("/mockups/workflow/decline/{image_id}")
async def decline_poster(image_id: int):
    """
    Decline a poster - mark as 'needs_attention'.
    User will need to manually create a mockup for it.
    """
    success = await db.update_image_mockup_status(
        image_id=image_id,
        mockup_status="needs_attention",
    )

    if not success:
        raise HTTPException(status_code=404, detail="Image not found")

    return {
        "success": True,
        "image_id": image_id,
        "status": "needs_attention",
    }


@router.post("/mockups/workflow/decline-unlinked")
async def decline_unlinked_posters():
    """Decline all pending posters that have no product linked (duplicates from generation)."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE generated_images
            SET mockup_status = 'declined'
            WHERE mockup_status = 'pending'
              AND product_id IS NULL
              AND id IN (
                  SELECT gi.id FROM generated_images gi
                  JOIN generations g ON gi.generation_id = g.generation_id
                  WHERE g.archived = 0
                    AND (g.style IS NULL OR g.style != 'mockup')
              )
            """
        )
        count = int(result.split()[-1]) if result else 0
    return {"declined": count}


@router.post("/mockups/workflow/retry/{image_id}")
async def retry_poster(image_id: int):
    """Reset a declined/needs_attention poster back to pending for re-review."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE generated_images
            SET mockup_status = 'pending', mockup_url = NULL
            WHERE id = $1
              AND mockup_status IN ('needs_attention', 'declined')
            """,
            image_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Image not found or not in declined state")
    return {"success": True, "image_id": image_id, "status": "pending"}


@router.post("/mockups/workflow/retry-all-declined")
async def retry_all_declined():
    """Reset all declined/needs_attention posters (linked to products) back to pending."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE generated_images
            SET mockup_status = 'pending', mockup_url = NULL
            WHERE mockup_status IN ('needs_attention', 'declined')
              AND product_id IS NOT NULL
            """
        )
        count = int(result.split()[-1]) if result else 0
    return {"retried": count}


@router.get("/mockups/workflow/declined")
async def get_declined_posters(limit: int = 100):
    """Get all declined/needs_attention posters linked to products."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT gi.id, gi.url, gi.generation_id, gi.mockup_status,
                   gi.product_id, gi.created_at,
                   g.prompt
            FROM generated_images gi
            JOIN generations g ON gi.generation_id = g.generation_id
            WHERE gi.mockup_status IN ('needs_attention', 'declined')
              AND gi.product_id IS NOT NULL
              AND g.archived = 0
              AND (g.style IS NULL OR g.style != 'mockup')
            ORDER BY gi.created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return {"posters": [dict(r) for r in rows], "count": len(rows)}


# --- Reapply Approved ---

class ReapplyRequest(BaseModel):
    pack_id: Optional[int] = None


# Track background reapply progress
_reapply_status: dict = {"running": False, "total": 0, "done": 0, "ok": 0, "errors": []}


@router.post("/mockups/workflow/reapply-approved")
async def reapply_approved_mockups(request: Optional[ReapplyRequest] = None):
    """Start background reapply of all approved mockups. Returns immediately."""
    global _reapply_status
    if _reapply_status["running"]:
        return {
            "started": False,
            "message": f"Already running: {_reapply_status['done']}/{_reapply_status['total']} done",
            **_reapply_status,
        }

    pack_id = request.pack_id if request else None

    if pack_id:
        pack = await db.get_mockup_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")
        templates = await db.get_pack_templates(pack_id)
        if not templates:
            raise HTTPException(status_code=400, detail="Pack has no templates")
    else:
        templates = await db.get_active_mockup_templates()
        if not templates:
            return {"error": "No active templates configured"}

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.printify_product_id, p.etsy_listing_id,
                   gi.id as image_id, gi.url as poster_url
            FROM products p
            JOIN generated_images gi ON gi.id = p.source_image_id
            WHERE gi.mockup_status = 'approved'
              AND p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
            """
        )

    if not rows:
        return {"started": False, "total": 0, "message": "No approved products with Etsy listings"}

    total = len(rows)
    _reapply_status = {"running": True, "total": total, "done": 0, "ok": 0, "errors": []}
    asyncio.create_task(_background_reapply(pack_id, [dict(r) for r in rows]))
    logger.info(f"reapply: Started background reapply for {total} products (pack_id={pack_id})")

    return {"started": True, "total": total, "message": f"Reapplying to {total} products in background..."}


@router.get("/mockups/workflow/reapply-status")
async def reapply_status():
    """Check progress of background reapply."""
    return _reapply_status


async def _background_reapply(pack_id: Optional[int], rows: list):
    """Background task: reapply to all products."""
    global _reapply_status
    try:
        if pack_id:
            pack = await db.get_mockup_pack(pack_id)
            templates = await db.get_pack_templates(pack_id)
            color_grade = pack.get("color_grade", "none") if pack else "none"
        else:
            templates = await db.get_active_mockup_templates()
            color_grade = "none"

        for t in templates:
            if isinstance(t.get("corners"), str):
                t["corners"] = json.loads(t["corners"])

        try:
            access_token, shop_id = await ensure_etsy_token()
        except Exception as e:
            _reapply_status["running"] = False
            _reapply_status["errors"].append(f"Etsy auth failed: {e}")
            logger.error(f"reapply: Etsy auth failed: {e}")
            return

        for row in rows:
            try:
                composed = await _compose_all_templates(
                    row["poster_url"], templates, "fill", color_grade
                )

                await db.delete_image_mockups(row["image_id"])
                mockup_entries = []
                for rank_idx, (tid, png_bytes) in enumerate(composed, start=2):
                    b64 = base64.b64encode(png_bytes).decode()
                    saved = await db.save_image_mockup(
                        image_id=row["image_id"],
                        template_id=tid,
                        mockup_data=f"data:image/png;base64,{b64}",
                        rank=rank_idx,
                        pack_id=pack_id,
                    )
                    mockup_entries.append((saved["id"], png_bytes))

                upload_results = await _upload_multi_images_to_etsy(
                    access_token=access_token,
                    shop_id=shop_id,
                    listing_id=row["etsy_listing_id"],
                    original_poster_url=row["poster_url"],
                    mockup_entries=mockup_entries,
                )

                for ur in upload_results:
                    if ur.get("mockup_db_id") and ur.get("etsy_image_id"):
                        await db.update_image_mockup_etsy_info(
                            ur["mockup_db_id"], ur["etsy_image_id"], ur.get("etsy_cdn_url", "")
                        )
                for ur in upload_results:
                    if ur.get("etsy_cdn_url") and ur["type"] == "mockup":
                        await db.set_product_preferred_mockup(row["printify_product_id"], ur["etsy_cdn_url"])
                        break

                _reapply_status["ok"] += 1
                logger.info(f"reapply: Product {row['id']} OK ({_reapply_status['done'] + 1}/{_reapply_status['total']})")
            except Exception as e:
                _reapply_status["errors"].append(f"Product {row['id']}: {e}")
                logger.error(f"reapply: Product {row['id']} FAILED: {e}")

            _reapply_status["done"] += 1

        logger.info(f"reapply: Done: {_reapply_status['ok']}/{_reapply_status['total']} products updated")
    except Exception as e:
        logger.error(f"reapply: Background task crashed: {e}")
        _reapply_status["errors"].append(f"Fatal: {e}")
    finally:
        _reapply_status["running"] = False


# ------------------------------------------------------------------
# Apply default pack mockups to published products missing mockups
# ------------------------------------------------------------------

_apply_missing_status = {"running": False, "total": 0, "done": 0, "ok": 0, "errors": []}


@router.post("/mockups/apply-to-published")
async def apply_mockups_to_published():
    """Find published products with missing or un-uploaded mockups and fix them.

    Handles two cases:
    1. Products with no image_mockups at all → compose + upload
    2. Products with image_mockups but etsy_image_id IS NULL → upload existing
    """
    global _apply_missing_status
    if _apply_missing_status["running"]:
        return {
            "started": False,
            "message": f"Already running: {_apply_missing_status['done']}/{_apply_missing_status['total']} done",
            **_apply_missing_status,
        }

    # Get default pack
    default_pack_str = await db.get_setting("default_pack_id")
    if not default_pack_str:
        raise HTTPException(status_code=400, detail="No default pack configured")
    pack_id = int(default_pack_str)

    templates = await db.get_pack_templates(pack_id)
    if not templates:
        raise HTTPException(status_code=400, detail="Default pack has no templates")

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        # Case 1: no mockups at all
        no_mockups = await conn.fetch(
            """
            SELECT p.id, p.printify_product_id, p.etsy_listing_id,
                   gi.id as image_id, gi.url as poster_url, 'compose' as action
            FROM products p
            JOIN generated_images gi ON gi.id = p.source_image_id
            WHERE p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
              AND NOT EXISTS (
                  SELECT 1 FROM image_mockups im WHERE im.image_id = gi.id
              )
            """
        )
        # Case 2: mockups exist but not uploaded to Etsy
        not_uploaded = await conn.fetch(
            """
            SELECT DISTINCT p.id, p.printify_product_id, p.etsy_listing_id,
                   gi.id as image_id, gi.url as poster_url, 'upload' as action
            FROM products p
            JOIN generated_images gi ON gi.id = p.source_image_id
            JOIN image_mockups im ON im.image_id = gi.id
            WHERE p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
              AND im.etsy_image_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM image_mockups im2
                  WHERE im2.image_id = gi.id AND im2.etsy_image_id IS NOT NULL
              )
            """
        )

    rows = [dict(r) for r in no_mockups] + [dict(r) for r in not_uploaded]
    if not rows:
        return {"started": False, "total": 0, "message": "All published products already have mockups on Etsy"}

    total = len(rows)
    _apply_missing_status = {"running": True, "total": total, "done": 0, "ok": 0, "errors": []}
    asyncio.create_task(_background_apply_missing(pack_id, rows))
    compose_count = len(no_mockups)
    upload_count = len(not_uploaded)
    logger.info(f"apply-missing: Started for {total} products (compose={compose_count}, upload={upload_count}) with pack {pack_id}")

    return {
        "started": True, "total": total, "pack_id": pack_id,
        "compose": compose_count, "upload_only": upload_count,
        "message": f"Applying mockups to {total} products...",
    }


@router.get("/mockups/apply-to-published/status")
async def apply_missing_status():
    """Check progress of apply-to-published."""
    return _apply_missing_status


async def _background_apply_missing(pack_id: int, rows: list):
    """Background: compose + upload default pack mockups for products missing them."""
    global _apply_missing_status
    try:
        pack = await db.get_mockup_pack(pack_id)
        templates = await db.get_pack_templates(pack_id)
        color_grade = pack.get("color_grade", "none") if pack else "none"

        for t in templates:
            if isinstance(t.get("corners"), str):
                t["corners"] = json.loads(t["corners"])

        try:
            access_token, shop_id = await ensure_etsy_token()
        except Exception as e:
            _apply_missing_status["running"] = False
            _apply_missing_status["errors"].append(f"Etsy auth failed: {e}")
            logger.error(f"apply-missing: Etsy auth failed: {e}")
            return

        for row in rows:
            try:
                composed = await _compose_all_templates(
                    row["poster_url"], templates, "fill", color_grade
                )

                mockup_entries = []
                for rank_idx, (tid, png_bytes) in enumerate(composed, start=2):
                    b64 = base64.b64encode(png_bytes).decode()
                    saved = await db.save_image_mockup(
                        image_id=row["image_id"],
                        template_id=tid,
                        mockup_data=f"data:image/png;base64,{b64}",
                        rank=rank_idx,
                        pack_id=pack_id,
                    )
                    mockup_entries.append((saved["id"], png_bytes))

                upload_results = await _upload_multi_images_to_etsy(
                    access_token=access_token,
                    shop_id=shop_id,
                    listing_id=row["etsy_listing_id"],
                    original_poster_url=row["poster_url"],
                    mockup_entries=mockup_entries,
                )
                for ur in upload_results:
                    if ur.get("mockup_db_id") and ur.get("etsy_image_id"):
                        await db.update_image_mockup_etsy_info(
                            ur["mockup_db_id"], ur["etsy_image_id"], ur.get("etsy_cdn_url", "")
                        )
                for ur in upload_results:
                    if ur.get("etsy_cdn_url") and ur["type"] == "mockup":
                        await db.set_product_preferred_mockup(row["printify_product_id"], ur["etsy_cdn_url"])
                        break

                _apply_missing_status["ok"] += 1
                logger.info(f"apply-missing: Product {row['id']} OK ({_apply_missing_status['done'] + 1}/{_apply_missing_status['total']})")
            except Exception as e:
                _apply_missing_status["errors"].append(f"Product {row['id']}: {e}")
                logger.error(f"apply-missing: Product {row['id']} FAILED: {e}")

            _apply_missing_status["done"] += 1

        logger.info(f"apply-missing: Done: {_apply_missing_status['ok']}/{_apply_missing_status['total']} products updated")
    except Exception as e:
        logger.error(f"apply-missing: Background task crashed: {e}")
        _apply_missing_status["errors"].append(f"Fatal: {e}")
    finally:
        _apply_missing_status["running"] = False


# --- Reapply Single Product ---

class ReapplySingleRequest(BaseModel):
    pack_id: Optional[int] = None


@router.post("/mockups/workflow/reapply-product/{printify_product_id}")
async def reapply_product_mockups(printify_product_id: str, request: Optional[ReapplySingleRequest] = None):
    """Reapply mockups for a single product by its Printify ID.

    Finds the source image for the product and runs the full approve flow
    (compose + save to DB + upload to Etsy) with the specified pack.
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow(
            "SELECT * FROM products WHERE printify_product_id = $1", printify_product_id
        )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in DB")

    image_id = product.get("source_image_id")
    if not image_id:
        raise HTTPException(status_code=400, detail="Product has no linked source image")

    pack_id = request.pack_id if request else None
    approve_req = ApproveRequest(pack_id=pack_id) if pack_id else None
    result = await approve_poster(image_id, approve_req)
    return result
