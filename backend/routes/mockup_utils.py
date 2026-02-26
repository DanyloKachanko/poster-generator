"""Shared utility functions and Pydantic models for mockup routes.

Split from routes/mockups.py — used by mockup_templates, mockup_compose, mockup_workflow.
"""

import io
import json
import logging
from typing import List, Tuple, Optional

from PIL import Image, ImageEnhance
from pydantic import BaseModel, Field
import numpy as np
import httpx

from config import COLOR_GRADE_PRESETS

logger = logging.getLogger(__name__)


# --- Pydantic Models ---

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
            logger.info(f"Skipping template {template['id']} — poster zone too small")
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
    import asyncio
    from deps import etsy

    kept_image = None

    if has_existing_images:
        # Get existing images
        old_images = []
        try:
            images_resp = await etsy.get_listing_images(access_token, listing_id)
            old_images = [img["listing_image_id"] for img in images_resp.get("results", [])]
        except Exception as e:
            logger.warning(f": could not list images for {listing_id}: {e}")

        # Delete all except last (Etsy needs at least 1)
        if old_images:
            kept_image = old_images[-1]
            to_delete = old_images[:-1]
            if to_delete:
                logger.info(f"Deleting {len(to_delete)} of {len(old_images)} old images from {listing_id}")
                for old_id in to_delete:
                    try:
                        await etsy.delete_listing_image(
                            access_token=access_token, shop_id=shop_id,
                            listing_id=listing_id, listing_image_id=str(old_id),
                        )
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.warning(f": failed to delete image {old_id}: {e}")

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
            logger.error(f"Failed to upload mockup {mockup_db_id}: {e}")

    # Delete the last kept old image (only when we had existing images)
    if kept_image:
        try:
            await etsy.delete_listing_image(
                access_token=access_token, shop_id=shop_id,
                listing_id=listing_id, listing_image_id=str(kept_image),
            )
        except Exception as e:
            logger.warning(f": failed to delete last image {kept_image}: {e}")

    return upload_results
