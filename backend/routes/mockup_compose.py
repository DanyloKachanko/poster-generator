"""Mockup generation and composition routes.

Split from routes/mockups.py — handles scene generation and poster composition.
"""

import base64
import io
import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from PIL import Image
import httpx

from config import MOCKUP_SCENES, MOCKUP_RATIOS, MODELS
from deps import leonardo, LEONARDO_API_KEY
from routes.mockup_utils import (
    MockupSceneRequest,
    ComposeRequest,
    calculate_zone_ratio_from_corners,
    letterbox_poster,
    crop_to_fill,
    _blend_poster_onto_scene,
    _find_perspective_coeffs,
    apply_color_grade,
    _compose_all_templates,
)
import database as db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mockups"])


# --- Scene Generation ---

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


# --- Composition ---

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


class ComposeByPackRequest(BaseModel):
    poster_url: str
    pack_id: int
    fill_mode: str = "fill"


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
