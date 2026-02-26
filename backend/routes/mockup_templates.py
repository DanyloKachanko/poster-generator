"""Mockup template and pack CRUD + settings routes.

Split from routes/mockups.py — handles template management, packs, and settings.
"""

import asyncio
import base64
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, File, Form, UploadFile
from pydantic import BaseModel

from config import MOCKUP_SCENES, MOCKUP_RATIOS, MOCKUP_STYLES, MODELS, COLOR_GRADE_PRESETS
from routes.mockup_utils import SaveTemplateRequest, _compose_all_templates, _upload_multi_images_to_etsy
from routes.etsy_routes import ensure_etsy_token
import database as db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mockups"])


# --- Scenes & Templates ---

@router.get("/mockups/scenes")
async def list_mockup_scenes():
    """List available mockup scene types, ratios, models, and styles."""
    return {
        "scenes": {k: {"name": v["name"]} for k, v in MOCKUP_SCENES.items()},
        "ratios": {k: {"name": v["name"]} for k, v in MOCKUP_RATIOS.items()},
        "models": {k: {"name": v["name"], "description": v["description"]} for k, v in MODELS.items()},
        "styles": {k: {"name": v["name"], "description": v["description"]} for k, v in MOCKUP_STYLES.items()},
    }


@router.get("/mockups/templates")
async def list_mockup_templates():
    """List all saved mockup templates."""
    templates = await db.get_mockup_templates()
    for t in templates:
        t["corners"] = json.loads(t["corners"])
        t["created_at"] = str(t["created_at"])
    return templates


@router.post("/mockups/templates")
async def create_mockup_template(request: SaveTemplateRequest):
    """Save a scene as a reusable mockup template with 4-corner poster zone."""
    if len(request.corners) != 4:
        raise HTTPException(status_code=400, detail="Exactly 4 corner points required (TL, TR, BR, BL)")
    row = await db.save_mockup_template(
        name=request.name,
        scene_url=request.scene_url,
        scene_width=request.scene_width,
        scene_height=request.scene_height,
        corners=json.dumps(request.corners),
        blend_mode=request.blend_mode,
    )
    row["corners"] = json.loads(row["corners"])
    row["created_at"] = str(row["created_at"])
    return row


@router.put("/mockups/templates/{template_id}")
async def update_mockup_template(template_id: int, request: SaveTemplateRequest):
    """Update an existing mockup template."""
    if len(request.corners) != 4:
        raise HTTPException(status_code=400, detail="Exactly 4 corner points required (TL, TR, BR, BL)")

    row = await db.update_mockup_template(
        template_id=template_id,
        name=request.name,
        scene_url=request.scene_url,
        scene_width=request.scene_width,
        scene_height=request.scene_height,
        corners=json.dumps(request.corners),
        blend_mode=request.blend_mode,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")

    row["corners"] = json.loads(row["corners"])
    row["created_at"] = str(row["created_at"])
    return row


@router.delete("/mockups/templates/{template_id}")
async def delete_mockup_template_endpoint(template_id: int):
    await db.delete_mockup_template(template_id)
    return {"ok": True}


@router.post("/mockups/templates/upload")
async def upload_mockup_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    corners: str = Form(...),  # JSON string of corners
    scene_width: int = Form(...),
    scene_height: int = Form(...),
):
    """Upload a custom mockup image with JSON configuration."""
    try:
        # Parse corners JSON
        corners_data = json.loads(corners)
        if len(corners_data) != 4:
            raise HTTPException(status_code=400, detail="Exactly 4 corner points required")

        # Save uploaded file (you can implement cloud storage later)
        # For now, save to a local directory or return a data URL
        import base64
        contents = await file.read()

        # Convert to base64 data URL for storage
        base64_image = base64.b64encode(contents).decode()
        data_url = f"data:image/png;base64,{base64_image}"

        # Save template to database
        row = await db.save_mockup_template(
            name=name,
            scene_url=data_url,  # Store as data URL for now
            scene_width=scene_width,
            scene_height=scene_height,
            corners=json.dumps(corners_data),
        )

        row["corners"] = json.loads(row["corners"])
        row["created_at"] = str(row["created_at"])
        return row

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in corners field")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Settings: Default Mockup Template ---

@router.get("/mockups/settings/default-template")
async def get_default_template():
    """Get the default mockup template ID."""
    template_id = await db.get_default_mockup_template_id()
    if not template_id:
        return {"default_template_id": None}

    template = await db.get_mockup_template(template_id)
    return {
        "default_template_id": template_id,
        "template": template,
    }


@router.post("/mockups/settings/default-template/{template_id}")
async def set_default_template(template_id: int):
    """Set the default mockup template (also activates it)."""
    template = await db.get_mockup_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.set_default_mockup_template_id(template_id)
    await db.set_template_active(template_id, True)
    return {"success": True, "default_template_id": template_id}


# --- Default Pack ---

@router.get("/mockups/settings/default-pack")
async def get_default_pack():
    """Get the default pack ID used for new products."""
    val = await db.get_setting("default_pack_id")
    pack_id = int(val) if val else None
    pack = None
    if pack_id:
        pack = await db.get_mockup_pack(pack_id)
    return {"default_pack_id": pack_id, "pack": pack}


@router.post("/mockups/settings/default-pack/{pack_id}")
async def set_default_pack(pack_id: int):
    """Set the default pack for new products."""
    pack = await db.get_mockup_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    await db.set_setting("default_pack_id", str(pack_id))
    return {"success": True, "default_pack_id": pack_id}


@router.delete("/mockups/settings/default-pack")
async def clear_default_pack():
    """Clear the default pack (use active templates instead)."""
    await db.set_setting("default_pack_id", "")
    return {"success": True, "default_pack_id": None}


# --- Active Templates ---

@router.get("/mockups/settings/active-templates")
async def get_active_templates():
    """Get all active template IDs and details."""
    templates = await db.get_active_mockup_templates()
    for t in templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])
        t["created_at"] = str(t["created_at"])
    return {"active_templates": templates, "count": len(templates)}


class SetActiveTemplatesRequest(BaseModel):
    template_ids: List[int]


@router.put("/mockups/settings/active-templates")
async def set_active_templates_endpoint(request: SetActiveTemplatesRequest):
    """Set which templates are active (replaces all)."""
    if len(request.template_ids) > 10:
        raise HTTPException(status_code=400, detail="Max 10 active templates")
    await db.set_active_templates(request.template_ids)
    return {"success": True, "active_count": len(request.template_ids)}


@router.post("/mockups/templates/{template_id}/toggle-active")
async def toggle_template_active(template_id: int):
    """Toggle a single template's active state."""
    template = await db.get_mockup_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    current = template.get("is_active", False)
    await db.set_template_active(template_id, not current)
    return {"template_id": template_id, "is_active": not current}


# --- Color Grades ---

@router.get("/mockups/color-grades")
async def list_color_grades():
    """List available color grade presets."""
    grades = [{"id": key, "name": preset["name"]} for key, preset in COLOR_GRADE_PRESETS.items()]
    return {"grades": grades}


# --- Mockup Packs ---

class CreatePackRequest(BaseModel):
    name: str
    template_ids: List[int] = []
    color_grade: str = "none"


class UpdatePackRequest(BaseModel):
    name: str
    template_ids: List[int]
    color_grade: str = "none"


@router.get("/mockups/packs")
async def list_packs():
    """List all mockup packs with template counts."""
    packs = await db.get_mockup_packs()
    for p in packs:
        p["created_at"] = str(p["created_at"])
    return {"packs": packs}


@router.get("/mockups/packs/{pack_id}")
async def get_pack(pack_id: int):
    """Get a single pack with its templates."""
    pack = await db.get_mockup_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    templates = await db.get_pack_templates(pack_id)
    for t in templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])
        t["created_at"] = str(t["created_at"])
    pack["templates"] = templates
    pack["created_at"] = str(pack["created_at"])
    return pack


@router.post("/mockups/packs")
async def create_pack(request: CreatePackRequest):
    """Create a new mockup pack, optionally with initial templates."""
    pack = await db.create_mockup_pack(request.name, request.color_grade)
    if request.template_ids:
        await db.set_pack_templates(pack["id"], request.template_ids)
    templates = await db.get_pack_templates(pack["id"])
    for t in templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])
        t["created_at"] = str(t["created_at"])
    pack["templates"] = templates
    pack["template_count"] = len(templates)
    pack["created_at"] = str(pack["created_at"])
    return pack


@router.put("/mockups/packs/{pack_id}")
async def update_pack(pack_id: int, request: UpdatePackRequest):
    """Update a pack's name and templates. Auto-reapplies to linked products in background."""
    pack = await db.update_mockup_pack(pack_id, request.name, request.color_grade)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    await db.set_pack_templates(pack_id, request.template_ids)
    templates = await db.get_pack_templates(pack_id)
    for t in templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])
        t["created_at"] = str(t["created_at"])
    pack["templates"] = templates
    pack["template_count"] = len(templates)
    pack["created_at"] = str(pack["created_at"])

    # Count products linked to this pack and auto-reapply in background
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        affected = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT p.id)
            FROM image_mockups im
            JOIN generated_images gi ON gi.id = im.image_id
            JOIN products p ON p.source_image_id = gi.id
            WHERE im.pack_id = $1
              AND gi.mockup_status = 'approved'
              AND p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
            """,
            pack_id,
        )

    pack["affected_products"] = affected or 0
    if affected and affected > 0:
        asyncio.create_task(_background_reapply_pack(pack_id))
        logger.info(f" Pack {pack_id} updated — reapplying to {affected} products in background")

    return pack


async def _background_reapply_pack(pack_id: int):
    """Background task: reapply pack to all linked products."""
    try:
        pack = await db.get_mockup_pack(pack_id)
        if not pack:
            return
        templates = await db.get_pack_templates(pack_id)
        if not templates:
            return
        color_grade = pack.get("color_grade", "none")

        for t in templates:
            if isinstance(t.get("corners"), str):
                t["corners"] = json.loads(t["corners"])

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT p.id, p.printify_product_id, p.etsy_listing_id,
                       gi.id as image_id, gi.url as poster_url
                FROM image_mockups im
                JOIN generated_images gi ON gi.id = im.image_id
                JOIN products p ON p.source_image_id = gi.id
                WHERE im.pack_id = $1
                  AND gi.mockup_status = 'approved'
                  AND p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
                """,
                pack_id,
            )

        if not rows:
            return

        try:
            access_token, shop_id = await ensure_etsy_token()
        except Exception as e:
            logger.error(f"pack-reapply: Etsy auth failed: {e}")
            return

        ok = 0
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
                ok += 1
                logger.info(f"pack-reapply: Product {row['id']} OK ({ok}/{len(rows)})")
            except Exception as e:
                logger.error(f"pack-reapply: Product {row['id']} FAILED: {e}")

        logger.info(f"pack-reapply: Done: {ok}/{len(rows)} products updated for pack {pack_id}")
    except Exception as e:
        logger.error(f"pack-reapply: Background task failed: {e}")


@router.delete("/mockups/packs/{pack_id}")
async def delete_pack(pack_id: int):
    """Delete a mockup pack. Templates themselves are NOT deleted."""
    await db.delete_mockup_pack(pack_id)
    return {"ok": True}
