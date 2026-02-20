import asyncio
import base64
import io
import json
import time
from typing import Optional, List, Tuple

from fastapi import APIRouter, HTTPException, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
from PIL import Image, ImageEnhance
import numpy as np

from config import MOCKUP_SCENES, MOCKUP_RATIOS, MOCKUP_STYLES, MODELS, DEFAULT_MODEL, COLOR_GRADE_PRESETS
from deps import leonardo, LEONARDO_API_KEY, etsy
from routes.etsy_routes import ensure_etsy_token
import database as db
import os

router = APIRouter(tags=["mockups"])


# --- Models ---

class MockupSceneRequest(BaseModel):
    scene_type: str
    ratio: str = "4:5"
    custom_prompt: Optional[str] = None
    num_images: int = Field(default=2, ge=1, le=2)
    model_id: Optional[str] = None  # Model key from MODELS, defaults to "vision_xl" for mockups
    style: Optional[str] = None  # Style key from MOCKUP_STYLES, defaults to "black_natural"


class SaveTemplateRequest(BaseModel):
    name: str
    scene_url: str
    scene_width: int = 1024
    scene_height: int = 1280
    corners: List[List[float]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] — TL, TR, BR, BL
    blend_mode: str = "normal"  # "normal" or "multiply"


class ComposeRequest(BaseModel):
    template_id: int
    poster_url: str
    fill_mode: str = "fill"  # Options: "stretch", "fit" (letterbox), "fill" (crop)
    color_grade: str = "none"


# --- Utility Functions ---

def calculate_zone_ratio_from_corners(corners: List[List[float]]) -> float:
    """Calculate aspect ratio of the poster zone from 4 corner points.

    Args:
        corners: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] in TL, TR, BR, BL order

    Returns:
        Aspect ratio (width / height) of the zone
    """
    # Average width from top and bottom edges
    top_width = abs(corners[1][0] - corners[0][0])  # TR.x - TL.x
    bottom_width = abs(corners[2][0] - corners[3][0])  # BR.x - BL.x
    avg_width = (top_width + bottom_width) / 2

    # Average height from left and right edges
    left_height = abs(corners[3][1] - corners[0][1])  # BL.y - TL.y
    right_height = abs(corners[2][1] - corners[1][1])  # BR.y - TR.y
    avg_height = (left_height + right_height) / 2

    return avg_width / avg_height if avg_height > 0 else 1.0


def letterbox_poster(poster_img: Image.Image, target_ratio: float) -> Image.Image:
    """Fit poster to target aspect ratio by adding white borders (mat/passepartout).

    Args:
        poster_img: PIL Image of the poster
        target_ratio: Target width/height ratio

    Returns:
        PIL Image with white borders to match target ratio
    """
    w, h = poster_img.size
    poster_ratio = w / h

    # Tolerance check - if ratios are within 2%, no letterboxing needed
    ratio_diff = abs(poster_ratio - target_ratio) / target_ratio
    if ratio_diff < 0.02:
        return poster_img

    # Poster is wider than target - add horizontal bars (top/bottom)
    if poster_ratio > target_ratio:
        new_height = round(w / target_ratio)
        canvas = Image.new('RGBA', (w, new_height), (255, 255, 255, 255))
        # Center vertically
        paste_y = (new_height - h) // 2
        canvas.paste(poster_img, (0, paste_y))
        return canvas

    # Poster is taller than target - add vertical bars (left/right)
    else:
        new_width = round(h * target_ratio)
        canvas = Image.new('RGBA', (new_width, h), (255, 255, 255, 255))
        # Center horizontally
        paste_x = (new_width - w) // 2
        canvas.paste(poster_img, (paste_x, 0))
        return canvas


def crop_to_fill(poster_img: Image.Image, target_ratio: float) -> Image.Image:
    """Scale poster to FILL the target ratio by cropping overflow (no empty space).

    Args:
        poster_img: PIL Image of the poster
        target_ratio: Target width/height ratio

    Returns:
        PIL Image cropped to match target ratio
    """
    w, h = poster_img.size
    poster_ratio = w / h

    # Tolerance check - if ratios are within 2%, no cropping needed
    ratio_diff = abs(poster_ratio - target_ratio) / target_ratio
    if ratio_diff < 0.02:
        return poster_img

    if poster_ratio > target_ratio:
        # Poster is wider than target → crop left/right, keep full height
        crop_w = round(h * target_ratio)
        crop_x = (w - crop_w) // 2  # center crop
        crop_box = (crop_x, 0, crop_x + crop_w, h)
    else:
        # Poster is taller than target → crop top/bottom, keep full width
        crop_h = round(w / target_ratio)
        crop_y = (h - crop_h) // 2  # center crop
        crop_box = (0, crop_y, w, crop_y + crop_h)

    return poster_img.crop(crop_box)


def _blend_poster_onto_scene(
    scene_img: Image.Image,
    warped: Image.Image,
    bbox_x: int,
    bbox_y: int,
    blend_mode: str = "normal",
) -> Image.Image:
    """Paste warped poster onto scene with the given blend mode.

    normal  — standard alpha paste (poster replaces scene pixels)
    multiply — pixel-by-pixel multiply within the poster zone mask
    """
    result = scene_img.copy()
    if blend_mode == "multiply":
        # Extract the scene region under the poster
        region = result.crop((bbox_x, bbox_y, bbox_x + warped.width, bbox_y + warped.height))
        region_rgb = np.array(region.convert("RGB"), dtype=np.float32)
        warped_rgba = np.array(warped)
        warped_rgb = warped_rgba[:, :, :3].astype(np.float32)
        alpha = warped_rgba[:, :, 3].astype(np.float32) / 255.0  # 0..1

        # Multiply blend: out = scene * poster / 255
        blended = (region_rgb * warped_rgb / 255.0)
        # Lerp with alpha: where alpha=1 use blended, where alpha=0 keep scene
        alpha_3ch = alpha[:, :, np.newaxis]
        out = region_rgb * (1 - alpha_3ch) + blended * alpha_3ch
        out = np.clip(out, 0, 255).astype(np.uint8)

        blended_img = Image.fromarray(out, "RGB").convert("RGBA")
        result.paste(blended_img, (bbox_x, bbox_y))
    else:
        # Normal blend — standard alpha paste
        result.paste(warped, (bbox_x, bbox_y), warped)
    return result


# --- Routes ---

@router.get("/mockups/scenes")
async def list_mockup_scenes():
    """List available mockup scene types, ratios, models, and styles."""
    return {
        "scenes": {k: {"name": v["name"]} for k, v in MOCKUP_SCENES.items()},
        "ratios": {k: {"name": v["name"]} for k, v in MOCKUP_RATIOS.items()},
        "models": {k: {"name": v["name"], "description": v["description"]} for k, v in MODELS.items()},
        "styles": {k: {"name": v["name"], "description": v["description"]} for k, v in MOCKUP_STYLES.items()},
    }


@router.post("/mockups/generate-scene")
async def generate_mockup_scene(request: MockupSceneRequest):
    """Generate a room scene with a white poster placeholder using Leonardo AI."""
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")

    if request.custom_prompt:
        prompt = request.custom_prompt
    else:
        scene = MOCKUP_SCENES.get(request.scene_type)
        if not scene:
            raise HTTPException(status_code=400, detail=f"Unknown scene type: {request.scene_type}. Available: {list(MOCKUP_SCENES.keys())}")
        prompt = scene["prompt"]

    ratio_info = MOCKUP_RATIOS.get(request.ratio, MOCKUP_RATIOS["4:5"])
    gen_width = ratio_info["width"]
    gen_height = ratio_info["height"]

    negative_prompt = "text, watermark, signature, words, letters, writing, multiple posters, multiple frames, collage, diptych, triptych, blurry, low quality, distorted"

    # Use provided model or default to vision_xl (best for photorealistic mockups)
    model_key = request.model_id or "vision_xl"
    model_info = MODELS.get(model_key, MODELS.get("vision_xl"))

    try:
        result = await leonardo.create_generation(
            prompt=prompt,
            width=gen_width,
            height=gen_height,
            num_images=request.num_images,
            model_id=model_info["id"],
            negative_prompt=negative_prompt,
        )

        # Save to database for tracking
        await db.save_generation(
            generation_id=result["generation_id"],
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_id=model_info["id"],
            model_name=model_info["name"],
            style="mockup",
            preset=request.scene_type,
            width=gen_width,
            height=gen_height,
            num_images=request.num_images,
            status="PENDING",
        )

        return {
            "generation_id": result["generation_id"],
            "status": "PENDING",
            "scene_type": request.scene_type,
            "ratio": request.ratio,
            "width": gen_width,
            "height": gen_height,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# --- Helpers ---

def _find_perspective_coeffs(src_points, dst_points):
    """Calculate perspective transform coefficients for Pillow.
    src_points / dst_points: list of 4 (x,y) tuples — TL, TR, BR, BL.
    Returns 8-tuple for Image.transform(PERSPECTIVE).
    """
    import numpy as np
    A = []
    B = []
    for (sx, sy), (dx, dy) in zip(dst_points, src_points):
        A.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        A.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        B.append(dx)
        B.append(dy)
    A = np.array(A, dtype=float)
    B = np.array(B, dtype=float)
    coeffs = np.linalg.solve(A, B)
    return tuple(coeffs.tolist())


def apply_color_grade(img: Image.Image, preset_name: str) -> Image.Image:
    """Apply color grade preset to a PIL Image. Returns graded image."""
    preset = COLOR_GRADE_PRESETS.get(preset_name)
    if not preset or preset_name == "none":
        return img

    result = img.copy()

    if preset["brightness"] != 1.0:
        result = ImageEnhance.Brightness(result).enhance(preset["brightness"])

    if preset["saturation"] != 1.0:
        result = ImageEnhance.Color(result).enhance(preset["saturation"])

    if preset["contrast"] != 1.0:
        result = ImageEnhance.Contrast(result).enhance(preset["contrast"])

    warmth = preset.get("warmth", 0)
    if warmth > 0:
        arr = np.array(result, dtype=np.float32)
        factor = warmth / 100.0
        arr[:, :, 0] = np.clip(arr[:, :, 0] * (1 + factor * 0.25), 0, 255)  # R boost
        arr[:, :, 2] = np.clip(arr[:, :, 2] * (1 - factor * 0.35), 0, 255)  # B reduce
        result = Image.fromarray(arr.astype(np.uint8))

    return result


async def _compose_all_templates(
    poster_url: str,
    templates: List[dict],
    fill_mode: str = "fill",
    color_grade: str = "none",
) -> List[Tuple[int, bytes]]:
    """Compose poster with all templates. Returns list of (template_id, png_bytes).

    Downloads the poster once and reuses it across templates.
    """
    # Download poster once
    async with httpx.AsyncClient(follow_redirects=True) as client:
        poster_resp = await client.get(poster_url, timeout=60.0)
        poster_resp.raise_for_status()
    poster_bytes = poster_resp.content

    results = []
    clean_result = None
    clean_saved = False
    for template in templates:
        corners = template["corners"]
        if isinstance(corners, str):
            corners = json.loads(corners)

        # Download scene
        async with httpx.AsyncClient(follow_redirects=True) as client:
            scene_resp = await client.get(template["scene_url"], timeout=60.0)
            scene_resp.raise_for_status()

        scene_img = Image.open(io.BytesIO(scene_resp.content)).convert("RGBA")
        poster_img = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")

        # Apply fill mode
        target_ratio = calculate_zone_ratio_from_corners(corners)
        if fill_mode == "fit":
            poster_img = letterbox_poster(poster_img, target_ratio)
        elif fill_mode == "fill":
            poster_img = crop_to_fill(poster_img, target_ratio)

        sx = scene_img.width / template["scene_width"]
        sy = scene_img.height / template["scene_height"]
        dst_corners = [(c[0] * sx, c[1] * sy) for c in corners]

        xs = [p[0] for p in dst_corners]
        ys = [p[1] for p in dst_corners]
        bbox_x = int(min(xs))
        bbox_y = int(min(ys))
        bbox_w = int(max(xs)) - bbox_x
        bbox_h = int(max(ys)) - bbox_y

        if bbox_w < 10 or bbox_h < 10:
            print(f"[mockup] Skipping template {template['id']} — poster zone too small")
            continue

        poster_resized = poster_img.resize((bbox_w, bbox_h), Image.LANCZOS)
        src_pts = [(0, 0), (bbox_w, 0), (bbox_w, bbox_h), (0, bbox_h)]
        dst_local = [(x - bbox_x, y - bbox_y) for x, y in dst_corners]

        try:
            coeffs = _find_perspective_coeffs(src_pts, dst_local)
            warped = poster_resized.transform(
                (bbox_w, bbox_h), Image.PERSPECTIVE, coeffs, Image.BICUBIC
            )
        except Exception:
            warped = poster_resized

        blend_mode = template.get("blend_mode", "normal") or "normal"
        result = _blend_poster_onto_scene(scene_img, warped, bbox_x, bbox_y, blend_mode)

        result_rgb = result.convert("RGB")

        if color_grade and color_grade != "none":
            # Graded version
            graded_rgb = apply_color_grade(result_rgb, color_grade)
            buf = io.BytesIO()
            graded_rgb.save(buf, format="PNG", quality=95)
            buf.seek(0)
            results.append((template["id"], buf.read()))

            # Save first clean version only (one extra without filter)
            if not clean_saved:
                buf2 = io.BytesIO()
                result_rgb.save(buf2, format="PNG", quality=95)
                buf2.seek(0)
                clean_result = (template["id"], buf2.read())
                clean_saved = True
        else:
            buf = io.BytesIO()
            result_rgb.save(buf, format="PNG", quality=95)
            buf.seek(0)
            results.append((template["id"], buf.read()))

    # All graded mockups first, then one clean version at the end
    if clean_result:
        results.append(clean_result)
    return results


async def _upload_multi_images_to_etsy(
    access_token: str,
    shop_id: str,
    listing_id: str,
    original_poster_url: str,
    mockup_entries: List[Tuple[int, bytes]],
    has_existing_images: bool = True,
) -> List[dict]:
    """Upload only mockups to Etsy listing (no raw poster).

    When has_existing_images=True (default):
      1. Delete all old images except one (Etsy requires min 1)
      2. Upload mockups at rank=1..N (first mockup = Primary)
      3. Delete the kept old image

    When has_existing_images=False (published with images:false):
      Just upload mockups at rank=1..N (no old images to manage).

    Returns per-image results with etsy_image_id + etsy_cdn_url.
    """
    kept_image = None

    if has_existing_images:
        # Get existing images
        old_images = []
        try:
            images_resp = await etsy.get_listing_images(access_token, listing_id)
            old_images = [img["listing_image_id"] for img in images_resp.get("results", [])]
        except Exception as e:
            print(f"[mockup] Warning: could not list images for {listing_id}: {e}")

        # Delete all except last (Etsy needs at least 1)
        if old_images:
            kept_image = old_images[-1]
            to_delete = old_images[:-1]
            if to_delete:
                print(f"[mockup] Deleting {len(to_delete)} of {len(old_images)} old images from {listing_id}")
                for old_id in to_delete:
                    try:
                        await etsy.delete_listing_image(
                            access_token=access_token, shop_id=shop_id,
                            listing_id=listing_id, listing_image_id=str(old_id),
                        )
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"[mockup] Warning: failed to delete image {old_id}: {e}")

    upload_results = []
    rank = 1

    # Upload mockups FIRST (rank 1 = primary = first mockup)
    for mockup_db_id, mockup_bytes in mockup_entries:
        try:
            resp_data = await etsy.upload_listing_image(
                access_token=access_token, shop_id=shop_id,
                listing_id=listing_id, image_bytes=mockup_bytes,
                filename=f"mockup_{mockup_db_id or rank}.png", rank=rank,
            )
            upload_results.append({
                "type": "mockup", "mockup_db_id": mockup_db_id, "rank": rank,
                "etsy_image_id": str(resp_data.get("listing_image_id", "")),
                "etsy_cdn_url": resp_data.get("url_fullxfull") or resp_data.get("url_570xN"),
            })
            rank += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[mockup] Failed to upload mockup {mockup_db_id}: {e}")

    # Delete the last kept old image (only when we had existing images)
    if kept_image:
        try:
            await etsy.delete_listing_image(
                access_token=access_token, shop_id=shop_id,
                listing_id=listing_id, listing_image_id=str(kept_image),
            )
        except Exception as e:
            print(f"[mockup] Warning: failed to delete last image {kept_image}: {e}")

    return upload_results


@router.post("/mockups/workflow/cleanup-originals")
async def cleanup_original_posters():
    """Remove non-mockup images from all Etsy listings. Keeps only known mockup images."""
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
                    print(f"[cleanup] Failed to delete image {img_id} from {row['etsy_listing_id']}: {e}")

            if to_delete:
                cleaned += 1
                print(f"[cleanup] Listing {row['etsy_listing_id']}: deleted {len(to_delete)} non-mockup images")
        except Exception as e:
            print(f"[cleanup] Error processing listing {row['etsy_listing_id']}: {e}")

    return {"total": len(rows), "cleaned": cleaned, "deleted_images": total_deleted}


@router.post("/mockups/compose")
async def compose_mockup(request: ComposeRequest):
    """Compose a poster onto a template scene using perspective transform. Returns PNG."""
    template = await db.get_mockup_template(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    corners = json.loads(template["corners"])  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]

    # Download scene and poster images
    async with httpx.AsyncClient(follow_redirects=True) as client:
        scene_resp = await client.get(template["scene_url"], timeout=60.0)
        scene_resp.raise_for_status()
        poster_resp = await client.get(request.poster_url, timeout=60.0)
        poster_resp.raise_for_status()

    scene_img = Image.open(io.BytesIO(scene_resp.content)).convert("RGBA")
    poster_img = Image.open(io.BytesIO(poster_resp.content)).convert("RGBA")

    # Apply fill mode (fit=letterbox, fill=crop, stretch=no change)
    if request.fill_mode == "fit":
        # Letterbox: add white mat to preserve aspect ratio
        target_ratio = calculate_zone_ratio_from_corners(corners)
        poster_img = letterbox_poster(poster_img, target_ratio)
    elif request.fill_mode == "fill":
        # Crop to fill: scale up and crop overflow (no white bars)
        target_ratio = calculate_zone_ratio_from_corners(corners)
        poster_img = crop_to_fill(poster_img, target_ratio)
    # else "stretch" — do nothing, poster will be stretched to fit zone

    # Corners are in virtual coords (0..scene_width, 0..scene_height).
    # Scale to actual pixel coords of the scene image.
    sx = scene_img.width / template["scene_width"]
    sy = scene_img.height / template["scene_height"]
    dst_corners = [(c[0] * sx, c[1] * sy) for c in corners]

    # Compute bounding box of destination quadrilateral
    xs = [p[0] for p in dst_corners]
    ys = [p[1] for p in dst_corners]
    bbox_x = int(min(xs))
    bbox_y = int(min(ys))
    bbox_w = int(max(xs)) - bbox_x
    bbox_h = int(max(ys)) - bbox_y

    if bbox_w < 10 or bbox_h < 10:
        raise HTTPException(status_code=400, detail="Poster zone too small")

    # Resize poster to bounding box size for quality
    poster_resized = poster_img.resize((bbox_w, bbox_h), Image.LANCZOS)

    # Source corners = full poster rectangle (in bbox-local coords)
    src_pts = [(0, 0), (bbox_w, 0), (bbox_w, bbox_h), (0, bbox_h)]
    # Destination corners shifted to bbox-local
    dst_local = [(x - bbox_x, y - bbox_y) for x, y in dst_corners]

    try:
        coeffs = _find_perspective_coeffs(src_pts, dst_local)
        warped = poster_resized.transform(
            (bbox_w, bbox_h), Image.PERSPECTIVE, coeffs, Image.BICUBIC
        )
    except Exception:
        # Fallback: no perspective, just paste resized
        warped = poster_resized

    # Paste warped poster onto scene with blend mode
    blend_mode = template.get("blend_mode", "normal") or "normal"
    result = _blend_poster_onto_scene(scene_img, warped, bbox_x, bbox_y, blend_mode)

    # Apply color grade if specified
    result_rgb = result.convert("RGB")
    if request.color_grade and request.color_grade != "none":
        result_rgb = apply_color_grade(result_rgb, request.color_grade)

    # Return as PNG
    buf = io.BytesIO()
    result_rgb.save(buf, format="PNG", quality=95)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png", headers={
        "Content-Disposition": f"attachment; filename=mockup-{request.template_id}-{int(time.time())}.png"
    })


# === Settings: Default Mockup Template ===

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


# === Default Pack ===

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


# === Active Templates ===

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


class ComposeAllRequest(BaseModel):
    poster_url: str
    fill_mode: str = "fill"
    color_grade: str = "none"


@router.post("/mockups/compose-all")
async def compose_all_mockups(request: ComposeAllRequest):
    """Compose a poster with all active templates. Returns JSON with base64 previews."""
    active_templates = await db.get_active_mockup_templates()
    if not active_templates:
        raise HTTPException(status_code=400, detail="No active templates configured")

    for t in active_templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])

    results = await _compose_all_templates(request.poster_url, active_templates, request.fill_mode, request.color_grade)

    previews = []
    for template_id, png_bytes in results:
        b64 = base64.b64encode(png_bytes).decode()
        previews.append({
            "template_id": template_id,
            "preview_url": f"data:image/png;base64,{b64}",
        })

    return {"previews": previews, "poster_url": request.poster_url}


@router.get("/mockups/color-grades")
async def list_color_grades():
    """List available color grade presets."""
    grades = [{"id": key, "name": preset["name"]} for key, preset in COLOR_GRADE_PRESETS.items()]
    return {"grades": grades}


# === Mockup Packs ===

class CreatePackRequest(BaseModel):
    name: str
    template_ids: List[int] = []
    color_grade: str = "none"


class UpdatePackRequest(BaseModel):
    name: str
    template_ids: List[int]
    color_grade: str = "none"


class ComposeByPackRequest(BaseModel):
    poster_url: str
    pack_id: int
    fill_mode: str = "fill"


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
        print(f"[pack] Pack {pack_id} updated — reapplying to {affected} products in background")

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
            print(f"[pack-reapply] Etsy auth failed: {e}")
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
                print(f"[pack-reapply] Product {row['id']} OK ({ok}/{len(rows)})")
            except Exception as e:
                print(f"[pack-reapply] Product {row['id']} FAILED: {e}")

        print(f"[pack-reapply] Done: {ok}/{len(rows)} products updated for pack {pack_id}")
    except Exception as e:
        print(f"[pack-reapply] Background task failed: {e}")


@router.delete("/mockups/packs/{pack_id}")
async def delete_pack(pack_id: int):
    """Delete a mockup pack. Templates themselves are NOT deleted."""
    await db.delete_mockup_pack(pack_id)
    return {"ok": True}


@router.post("/mockups/compose-by-pack")
async def compose_by_pack(request: ComposeByPackRequest):
    """Compose a poster with a specific pack's templates. Returns base64 previews."""
    pack = await db.get_mockup_pack(request.pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    templates = await db.get_pack_templates(request.pack_id)
    if not templates:
        raise HTTPException(status_code=400, detail="Pack has no templates")

    for t in templates:
        if isinstance(t.get("corners"), str):
            t["corners"] = json.loads(t["corners"])

    color_grade = pack.get("color_grade", "none")
    results = await _compose_all_templates(request.poster_url, templates, request.fill_mode, color_grade)

    previews = []
    for template_id, png_bytes in results:
        b64 = base64.b64encode(png_bytes).decode()
        previews.append({
            "template_id": template_id,
            "preview_url": f"data:image/png;base64,{b64}",
        })

    return {"previews": previews, "poster_url": request.poster_url, "pack_id": request.pack_id}


# === Mockup Workflow ===

@router.get("/mockups/workflow/posters")
async def get_workflow_posters(status: str = "pending", linked_only: bool = True):
    """Get posters for workflow. linked_only=true filters to product-linked images only."""
    posters = await db.get_workflow_posters(status=status, limit=100, linked_only=linked_only)
    return {"posters": posters, "count": len(posters)}


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

                # Upload original poster + all mockups
                upload_results = await _upload_multi_images_to_etsy(
                    access_token=access_token,
                    shop_id=shop_id,
                    listing_id=product["etsy_listing_id"],
                    original_poster_url=image["url"],
                    mockup_entries=mockup_entries,
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
        "total": len(image_ids),
        "approved": succeeded,
        "etsy_uploaded": etsy_ok,
        "results": results,
    }


# === Image Mockups per poster ===

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
    print(f"[reapply] Started background reapply for {total} products (pack_id={pack_id})")

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
            print(f"[reapply] Etsy auth failed: {e}")
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
                print(f"[reapply] Product {row['id']} OK ({_reapply_status['done'] + 1}/{_reapply_status['total']})")
            except Exception as e:
                _reapply_status["errors"].append(f"Product {row['id']}: {e}")
                print(f"[reapply] Product {row['id']} FAILED: {e}")

            _reapply_status["done"] += 1

        print(f"[reapply] Done: {_reapply_status['ok']}/{_reapply_status['total']} products updated")
    except Exception as e:
        print(f"[reapply] Background task crashed: {e}")
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
    print(f"[apply-missing] Started for {total} products (compose={compose_count}, upload={upload_count}) with pack {pack_id}")

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
            print(f"[apply-missing] Etsy auth failed: {e}")
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
                print(f"[apply-missing] Product {row['id']} OK ({_apply_missing_status['done'] + 1}/{_apply_missing_status['total']})")
            except Exception as e:
                _apply_missing_status["errors"].append(f"Product {row['id']}: {e}")
                print(f"[apply-missing] Product {row['id']} FAILED: {e}")

            _apply_missing_status["done"] += 1

        print(f"[apply-missing] Done: {_apply_missing_status['ok']}/{_apply_missing_status['total']} products updated")
    except Exception as e:
        print(f"[apply-missing] Background task crashed: {e}")
        _apply_missing_status["errors"].append(f"Fatal: {e}")
    finally:
        _apply_missing_status["running"] = False
