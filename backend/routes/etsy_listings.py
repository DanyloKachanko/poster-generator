import csv
import io
import logging
import re
import asyncio
import struct
import unicodedata
from pathlib import Path
from typing import Optional, List
from listing_generator import sanitize_tag

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx

import database as db

from etsy import ETSY_COLOR_VALUES, ETSY_PRIMARY_COLOR_PROPERTY_ID, ETSY_SECONDARY_COLOR_PROPERTY_ID
from deps import etsy, listing_gen
from description_utils import clean_description, ensure_disclaimer
from routes.etsy_auth import ensure_etsy_token

router = APIRouter(tags=["etsy"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_seo_data(data: dict) -> dict:
    """Validate and auto-fix SEO data from Claude. Returns data with validation_errors list."""
    errors = []

    # Title length
    title = data.get("title", "")
    if len(title) > 140:
        truncated = title[:140]
        last_pipe = truncated.rfind(" | ")
        if last_pipe > 0:
            data["title"] = truncated[:last_pipe]
        else:
            data["title"] = truncated
        errors.append(f"Title truncated from {len(title)} to {len(data['title'])} chars")

    # Tag fixes
    tags = data.get("tags", [])
    for i, tag in enumerate(tags):
        if len(tag) > 20:
            old = tags[i]
            tags[i] = sanitize_tag(tag)
            errors.append(f"Tag truncated: '{old}' -> '{tags[i]}'")

    # Remove single-word tags
    single_word = [t for t in tags if " " not in t.strip()]
    if single_word:
        tags = [t for t in tags if " " in t.strip()]
        errors.append(f"Removed {len(single_word)} single-word tag(s): {', '.join(single_word)}")

    # Pad to 13
    if len(tags) < 13:
        errors.append(f"Only {len(tags)} tags, padding to 13")
    while len(tags) < 13:
        tags.append(sanitize_tag(f"wall art print {len(tags)}"))
    tags = tags[:13]
    data["tags"] = tags

    # SK checks
    sk = data.get("superstar_keyword", "").lower()
    if sk and sk not in data.get("title", "").lower():
        errors.append(f"SK '{sk}' not found in title")
    if sk and sk not in data.get("description", "")[:160].lower():
        errors.append(f"SK '{sk}' not in first 160 chars of description")

    # Pipe separators
    if " | " not in data.get("title", ""):
        errors.append("Title missing pipe separators")

    data["validation_errors"] = errors
    data["is_valid"] = len(errors) == 0
    return data


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UpdateEtsyListingRequest(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    materials: Optional[List[str]] = None
    who_made: Optional[str] = None
    when_made: Optional[str] = None
    is_supply: Optional[bool] = None
    shop_section_id: Optional[int] = None
    shipping_profile_id: Optional[int] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    should_auto_renew: Optional[bool] = None


class BulkSeoRequest(BaseModel):
    listing_ids: List[str] = Field(..., min_length=1)


class BulkAltTextRequest(BaseModel):
    alt_texts: List[str] = Field(..., min_length=1, max_length=10)


class SeoSuggestRequest(BaseModel):
    title: str
    tags: list[str]
    description: str


class AIFillRequest(BaseModel):
    image_url: str
    current_title: str = ""
    niche: str = ""
    enabled_sizes: list = []


class AIFillBatchItem(BaseModel):
    listing_id: int
    image_url: str
    current_title: str = ""


class AIFillBatchRequest(BaseModel):
    listings: List[AIFillBatchItem]


# ---------------------------------------------------------------------------
# ETSY LISTING MANAGEMENT
# ---------------------------------------------------------------------------


@router.get("/etsy/listings")
async def get_etsy_listings():
    """Get all active Etsy listings for the connected shop."""
    access_token, shop_id = await ensure_etsy_token()

    try:
        listings = await etsy.get_all_listings(access_token, shop_id)
        return {
            "listings": listings,
            "count": len(listings),
            "shop_id": shop_id,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


SPECIAL_CHARS_RE = re.compile(r'[#@!]')


def validate_etsy_tags(tags_str: str) -> dict:
    """Validate and clean Etsy tags. Returns cleaned tags list and issues."""
    raw = [t.strip() for t in tags_str.split(",") if t.strip()]
    seen: set[str] = set()
    issues: list[str] = []
    cleaned: list[str] = []

    for tag in raw:
        # Remove special characters
        original = tag
        tag = SPECIAL_CHARS_RE.sub("", tag).strip()
        if tag != original:
            issues.append(f'stripped special chars: "{original}" -> "{tag}"')
        # Truncate
        if len(tag) > 20:
            issues.append(f'truncated: "{tag}" -> "{tag[:20]}"')
            tag = tag[:20].rstrip()
        if not tag:
            continue
        # Deduplicate
        key = tag.lower()
        if key in seen:
            issues.append(f'duplicate removed: "{tag}"')
            continue
        seen.add(key)
        cleaned.append(tag)

    if len(cleaned) > 13:
        issues.append(f"kept first 13 of {len(cleaned)} tags")
        cleaned = cleaned[:13]

    return {"cleaned": cleaned, "issues": issues}


MIN_WIDTH = 2400
MIN_HEIGHT = 3000


def _parse_png_dimensions(data: bytes) -> tuple[int, int] | None:
    """Extract width/height from PNG header (first 24 bytes)."""
    if len(data) >= 24 and data[:8] == b'\x89PNG\r\n\x1a\n':
        w, h = struct.unpack('>II', data[16:24])
        return w, h
    return None


def _parse_jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Extract width/height from JPEG by scanning SOF markers."""
    i = 2  # skip SOI
    while i < len(data) - 9:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        # SOF0..SOF3 markers contain dimensions
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h, w = struct.unpack('>HH', data[i + 5:i + 9])
            return w, h
        length = struct.unpack('>H', data[i + 2:i + 4])[0]
        i += 2 + length
    return None


async def _get_image_dimensions(client: httpx.AsyncClient, url: str) -> tuple[int, int] | None:
    """Download first ~32KB of image and parse dimensions from header."""
    try:
        resp = await client.get(url, headers={"Range": "bytes=0-32767"}, timeout=10.0)
        if resp.status_code not in (200, 206):
            return None
        data = resp.content
        dims = _parse_png_dimensions(data)
        if dims:
            return dims
        dims = _parse_jpeg_dimensions(data)
        if dims:
            return dims
        return None
    except Exception:
        return None


def _get_primary_image_url(listing: dict) -> str | None:
    """Get url_fullxfull of the primary (rank=1) image from a listing."""
    images = listing.get("images") or []
    if not images:
        return None
    # Sort by rank, pick first
    sorted_imgs = sorted(images, key=lambda x: x.get("rank", 999))
    return sorted_imgs[0].get("url_fullxfull") or sorted_imgs[0].get("url_570xN")


IMAGE_AUDIT_TASK_ID = "image_audit"


@router.get("/etsy/export-csv")
async def export_etsy_csv():
    """Export all active Etsy listings as CSV with tag_issues column."""
    access_token, shop_id = await ensure_etsy_token()
    listings = await etsy.get_all_listings(access_token, shop_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["listing_id", "title", "description", "tags", "price", "quantity", "tag_issues"])

    for li in listings:
        raw_tags = li.get("tags") or []
        tags_str = ", ".join(raw_tags)
        validation = validate_etsy_tags(tags_str)
        tag_issues = "; ".join(validation["issues"]) if validation["issues"] else ""

        price_raw = li.get("price", {})
        if isinstance(price_raw, dict):
            amount = price_raw.get("amount", 0)
            divisor = price_raw.get("divisor", 100)
            price = amount / divisor if divisor else 0
        else:
            price = price_raw or 0
        writer.writerow([
            li.get("listing_id", ""),
            li.get("title", ""),
            li.get("description", ""),
            tags_str,
            f"{price:.2f}",
            li.get("quantity", 0),
            tag_issues,
        ])

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=etsy_listings.csv"},
    )


# --- Digital Downloads ---

@router.get("/etsy/digital-downloads")
async def get_digital_downloads_overview():
    """Get all active listings with their upscale status for digital download management."""
    access_token, shop_id = await ensure_etsy_token()

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.title, p.etsy_listing_id, p.image_url, p.preferred_mockup_url,
                   p.digital_enabled, p.digital_etsy_id,
                   gi.id as gi_id, gi.url as original_url, gi.upscaled_path, gi.upscaled_url,
                   gi.upscaled_width, gi.upscaled_height,
                   g.width as orig_width, g.height as orig_height
            FROM products p
            JOIN generated_images gi ON gi.product_id = p.id
            JOIN generations g ON g.generation_id = gi.generation_id
            WHERE p.etsy_listing_id IS NOT NULL
              AND p.status != 'deleted'
            ORDER BY p.id
            """
        )

    listings = []
    for r in rows:
        has_upscale = bool(r["upscaled_path"])
        orig_w = r["orig_width"] or 0
        orig_h = r["orig_height"] or 0
        up_w = r["upscaled_width"] or 0
        up_h = r["upscaled_height"] or 0

        listings.append({
            "id": r["id"],
            "title": r["title"],
            "etsy_listing_id": r["etsy_listing_id"],
            "thumbnail": r["original_url"] or r["image_url"] or "",
            "has_upscale": has_upscale,
            "orig_resolution": f"{orig_w}x{orig_h}",
            "upscaled_resolution": f"{up_w}x{up_h}" if has_upscale else "",
            "is_digital": bool(r["digital_enabled"]),
            "digital_etsy_id": r.get("digital_etsy_id") or "",
        })

    return {
        "listings": listings,
        "total": len(listings),
        "upscaled": sum(1 for l in listings if l["has_upscale"]),
    }


@router.get("/etsy/digital-zip/{listing_id}")
async def download_digital_zip(listing_id: str):
    """Download the digital ZIP file for a listing."""
    zip_path = DIGITAL_DIR / f"{listing_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP not found")
    return StreamingResponse(
        open(zip_path, "rb"),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={listing_id}_printable.zip"},
    )


@router.post("/etsy/digital-copy-mockups/{physical_listing_id}")
async def copy_mockups_to_digital(physical_listing_id: str):
    """Copy mockup images from physical listing to its digital listing."""
    access_token, shop_id = await ensure_etsy_token()

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        digital_id = await conn.fetchval(
            "SELECT digital_etsy_id FROM products WHERE etsy_listing_id = $1",
            physical_listing_id,
        )
    if not digital_id:
        raise HTTPException(status_code=404, detail="No digital listing found for this product")

    # Get images from physical listing
    phys_images = await etsy.get_listing_images(access_token, physical_listing_id)
    source_imgs = sorted(phys_images.get("results", []), key=lambda x: x.get("rank", 999))

    copied = 0
    async with httpx.AsyncClient() as client:
        for img in source_imgs:
            url = img.get("url_fullxfull", "")
            if not url:
                continue
            try:
                resp = await client.get(url, timeout=30.0, follow_redirects=True)
                if resp.status_code != 200:
                    continue
                await etsy.upload_listing_image(
                    access_token, shop_id, digital_id,
                    resp.content, f"mockup_{copied + 1}.jpg",
                    rank=copied + 1,
                )
                copied += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"copy-mockup: failed for {physical_listing_id}: {e}")

    return {"copied": copied, "digital_listing_id": digital_id}


@router.get("/etsy/upscaled-image/{image_id}")
async def serve_upscaled_image(image_id: int):
    """Serve an upscaled image file from local storage."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        path = await conn.fetchval(
            "SELECT upscaled_path FROM generated_images WHERE id = $1", image_id
        )
    if not path:
        raise HTTPException(status_code=404, detail="No upscaled image")

    from pathlib import Path
    # DB stores /var/www/dovshop/media/..., container mounts at /media
    file_path = Path(path.replace("/var/www/dovshop/media", "/media"))
    if not file_path.exists():
        # Try original path as fallback (running outside container)
        file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return StreamingResponse(
        open(file_path, "rb"),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


class DigitalToggleRequest(BaseModel):
    product_ids: List[int] = Field(..., min_length=1)
    enabled: bool = True


@router.post("/etsy/digital-toggle")
async def toggle_digital_enabled(request: DigitalToggleRequest):
    """Mark/unmark products for digital download creation."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE products SET digital_enabled = $1 WHERE id = ANY($2::int[])",
            request.enabled, request.product_ids,
        )
    return {
        "updated": len(request.product_ids),
        "enabled": request.enabled,
    }


# --- Create Digital Listings ---

DIGITAL_TASK_ID = "create_digital_listings"

# Sizes per aspect ratio — native ratio only, 3 sizes each, no cropping
RATIO_SIZES = {
    "2:3": [
        ("print_20x30.jpg", 6000, 9000),
        ("print_16x24.jpg", 4800, 7200),
        ("print_8x12.jpg",  2400, 3600),
    ],
    "4:5": [
        ("print_24x30.jpg", 7200, 9000),
        ("print_16x20.jpg", 4800, 6000),
        ("print_8x10.jpg",  2400, 3000),
    ],
    "3:4": [
        ("print_18x24.jpg", 5400, 7200),
        ("print_12x16.jpg", 3600, 4800),
        ("print_9x12.jpg",  2700, 3600),
    ],
    "1:1": [
        ("print_20x20.jpg", 6000, 6000),
        ("print_16x16.jpg", 4800, 4800),
        ("print_10x10.jpg", 3000, 3000),
    ],
    "11:14": [
        ("print_22x28.jpg", 6600, 8400),
        ("print_11x14.jpg", 3300, 4200),
        ("print_8x10.jpg",  2400, 3060),
    ],
}

DIGITAL_DIR = Path("/media/digital")


def _detect_ratio(w: int, h: int) -> str:
    """Detect closest standard ratio from image dimensions."""
    r = round(w / h, 2)
    ratios = {0.67: "2:3", 0.75: "3:4", 0.80: "4:5", 0.79: "11:14", 1.00: "1:1"}
    return ratios.get(r, "4:5")  # fallback to 4:5


def _create_size_variants(upscaled_path: str, listing_id: str) -> tuple[bytes, str, list[str]]:
    """Create ZIP with 3 size variants (native ratio). Returns (zip_bytes, ratio, size_names)."""
    import zipfile
    from PIL import Image

    src = Path(upscaled_path.replace("/var/www/dovshop/media", "/media"))
    if not src.exists():
        src = Path(upscaled_path)

    img = Image.open(src)
    if img.mode != "RGB":
        img = img.convert("RGB")

    ratio = _detect_ratio(img.size[0], img.size[1])
    sizes = RATIO_SIZES.get(ratio, RATIO_SIZES["4:5"])

    size_names = []
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, target_w, target_h in sizes:
            resized = img.resize((target_w, target_h), Image.LANCZOS)
            jpg_buf = io.BytesIO()
            # Quality 85 keeps ZIP under 20MB Etsy limit
            resized.save(jpg_buf, format="JPEG", quality=85, dpi=(300, 300))
            zf.writestr(filename, jpg_buf.getvalue())
            size_names.append(filename.replace(".jpg", "").replace("print_", ""))

    return zip_buf.getvalue(), ratio, size_names


@router.post("/etsy/create-digital-listings")
async def create_digital_listings(background_tasks: BackgroundTasks):
    """Create Etsy digital listings for all products with digital_enabled=true."""
    existing = await db.get_background_task(DIGITAL_TASK_ID)
    if existing and existing.get("status") == "running":
        return {
            "started": False,
            "message": f"Already running: {existing.get('done', 0)}/{existing.get('total', 0)} done",
        }

    access_token, shop_id = await ensure_etsy_token()

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        # Add column if needed
        await conn.execute(
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS digital_etsy_id TEXT"
        )
        rows = await conn.fetch(
            """
            SELECT p.id, p.title, p.description, p.tags, p.etsy_listing_id,
                   gi.upscaled_path
            FROM products p
            JOIN generated_images gi ON gi.product_id = p.id
            WHERE p.digital_enabled = true
              AND p.digital_etsy_id IS NULL
              AND gi.upscaled_path IS NOT NULL
              AND p.status != 'deleted'
            ORDER BY p.id
            """
        )

    if not rows:
        return {"started": False, "total": 0, "message": "No products to process"}

    products = [dict(r) for r in rows]
    total = len(products)
    await db.create_background_task(DIGITAL_TASK_ID, "create_digital", total=total)
    await db.update_background_task(DIGITAL_TASK_ID, status="running")

    background_tasks.add_task(
        _run_create_digital, products, access_token, shop_id
    )
    return {"started": True, "total": total, "message": f"Creating {total} digital listings..."}


async def _run_create_digital(products: list, access_token: str, shop_id: str):
    """Background: create ZIP + Etsy digital listing for each product."""
    done = 0
    ok = 0
    errors = []

    DIGITAL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        for prod in products:
            product_id = prod["id"]
            listing_id = prod["etsy_listing_id"]
            title = prod["title"] or ""

            try:
                # 1. Create ZIP with size variants (native ratio, no crop)
                zip_bytes, ratio, size_names = _create_size_variants(prod["upscaled_path"], listing_id)

                zip_path = DIGITAL_DIR / f"{listing_id}.zip"
                zip_path.write_bytes(zip_bytes)

                # 2. Create digital listing on Etsy
                digital_title = f"{title} | Digital Download | Printable Wall Art"[:140]
                raw_tags = prod["tags"] or []
                if isinstance(raw_tags, str):
                    raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                tags = [t[:20] for t in raw_tags][:10]  # Leave room for digital tags
                for dt in ["digital download", "printable wall art", "instant download"]:
                    if dt not in [t.lower() for t in tags] and len(tags) < 13:
                        tags.append(dt)

                sizes_text = "\n".join(f"- {s.replace('x', ' x ')} inches" for s in size_names)
                description = (prod["description"] or "") + "\n\n" + (
                    "INSTANT DOWNLOAD - No physical item will be shipped.\n\n"
                    f"Aspect ratio: {ratio}\n"
                    f"You will receive a ZIP file containing 3 high-resolution JPG files:\n"
                    f"{sizes_text}\n\n"
                    "All files are 300 DPI, print-ready quality."
                )

                new_listing = await etsy.create_listing(access_token, shop_id, {
                    "title": digital_title,
                    "description": description,
                    "tags": tags,
                    "price": 4.99,
                    "quantity": 999,
                    "who_made": "i_did",
                    "when_made": "made_to_order",
                    "taxonomy_id": 1027,
                    "type": "download",
                    "is_supply": False,
                    "should_auto_renew": False,
                    "shop_section_id": 58019908,  # Digital Downloads
                })

                new_listing_id = str(new_listing.get("listing_id", ""))

                # 3. Upload ZIP as digital file
                await etsy.upload_listing_file(
                    access_token, shop_id, new_listing_id,
                    zip_bytes, f"{listing_id}_printable.zip",
                )

                # 4. Upload first image from original listing as preview
                try:
                    orig_images = await etsy.get_listing_images(access_token, listing_id)
                    first_img = (orig_images.get("results") or [{}])[0]
                    img_url = first_img.get("url_fullxfull", "")
                    if img_url:
                        async with httpx.AsyncClient() as client:
                            img_resp = await client.get(img_url, timeout=30.0, follow_redirects=True)
                            if img_resp.status_code == 200:
                                await etsy.upload_listing_image(
                                    access_token, shop_id, new_listing_id,
                                    img_resp.content, "preview.jpg", rank=1,
                                )
                except Exception as img_err:
                    logger.warning(f"digital: could not copy image for {listing_id}: {img_err}")

                # 5. Save to DB
                pool = await db.get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE products SET digital_etsy_id = $1 WHERE id = $2",
                        new_listing_id, product_id,
                    )

                ok += 1
                logger.info(f"digital: {done + 1}/{len(products)} created: {digital_title[:50]} -> {new_listing_id}")

            except httpx.HTTPStatusError as e:
                body = e.response.text[:300] if e.response else ""
                logger.error(f"digital: failed {listing_id}: {e} | {body}")
                errors.append({"listing_id": listing_id, "title": title[:50], "error": f"{e} | {body}"})
            except Exception as e:
                logger.error(f"digital: failed {listing_id}: {e}")
                errors.append({"listing_id": listing_id, "title": title[:50], "error": str(e)})

            done += 1
            await db.update_background_task(
                DIGITAL_TASK_ID, done=done,
                progress_json={"ok": ok, "errors": errors},
            )
            await asyncio.sleep(1)  # rate limit

    except Exception as e:
        logger.error(f"digital: background task crashed: {e}")
        errors.append({"error": f"Fatal: {e}"})
    finally:
        await db.update_background_task(
            DIGITAL_TASK_ID, status="completed", done=done,
            progress_json={"ok": ok, "errors": errors},
        )


@router.get("/etsy/create-digital-status")
async def digital_creation_status():
    """Get digital listing creation progress."""
    task = await db.get_background_task(DIGITAL_TASK_ID)
    if not task:
        return {"status": "not_started"}
    progress = task.get("progress_json") or {}
    return {
        "status": task.get("status", "unknown"),
        "total": task.get("total", 0),
        "done": task.get("done", 0),
        "ok": progress.get("ok", 0),
        "errors": progress.get("errors", []),
    }


# --- Image Quality Audit ---

@router.post("/etsy/image-audit")
async def start_image_audit(background_tasks: BackgroundTasks):
    """Start background image quality audit. Check progress via GET /etsy/image-audit-status."""
    existing = await db.get_background_task(IMAGE_AUDIT_TASK_ID)
    if existing and existing.get("status") == "running":
        return {
            "started": False,
            "message": f"Already running: {existing.get('done', 0)}/{existing.get('total', 0)} done",
            "running": True,
        }

    access_token, shop_id = await ensure_etsy_token()
    listings = await etsy.get_all_listings(access_token, shop_id)

    total = len(listings)
    await db.create_background_task(IMAGE_AUDIT_TASK_ID, "image_audit", total=total)
    await db.update_background_task(IMAGE_AUDIT_TASK_ID, status="running")

    background_tasks.add_task(_run_image_audit, listings)
    return {"started": True, "total": total, "message": f"Auditing {total} listings..."}


async def _run_image_audit(listings: list[dict]):
    """Background task: check primary image resolution for all listings."""
    done = 0
    results = []
    good = 0
    low = 0
    no_image = 0

    try:
        async with httpx.AsyncClient() as client:
            # Process in batches of 10
            for batch_start in range(0, len(listings), 10):
                batch = listings[batch_start:batch_start + 10]
                tasks = []
                for li in batch:
                    url = _get_primary_image_url(li)
                    if url:
                        tasks.append(_get_image_dimensions(client, url))
                    else:
                        tasks.append(_noop())

                dims_list = await asyncio.gather(*tasks, return_exceptions=True)

                for li, dims in zip(batch, dims_list):
                    listing_id = li.get("listing_id", "")
                    title = (li.get("title") or "")[:60]
                    url = _get_primary_image_url(li)

                    if isinstance(dims, Exception) or dims is None:
                        if not url:
                            results.append({
                                "listing_id": listing_id, "title": title,
                                "img_width": 0, "img_height": 0,
                                "img_resolution": "no image", "img_quality": "no image",
                            })
                            no_image += 1
                        else:
                            results.append({
                                "listing_id": listing_id, "title": title,
                                "img_width": 0, "img_height": 0,
                                "img_resolution": "unknown", "img_quality": "unknown",
                            })
                    else:
                        w, h = dims
                        quality = "good" if w >= MIN_WIDTH and h >= MIN_HEIGHT else "low"
                        if quality == "good":
                            good += 1
                        else:
                            low += 1
                        results.append({
                            "listing_id": listing_id, "title": title,
                            "img_width": w, "img_height": h,
                            "img_resolution": f"{w}x{h}",
                            "img_quality": quality,
                        })
                    done += 1

                await db.update_background_task(
                    IMAGE_AUDIT_TASK_ID, done=done,
                    progress_json={"good": good, "low": low, "no_image": no_image},
                )
                await asyncio.sleep(0.2)  # rate limit between batches

    except Exception as e:
        logger.error(f"image-audit crashed: {e}")
    finally:
        # Build CSV in memory and store in progress_json
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["listing_id", "title", "img_width", "img_height", "img_resolution", "img_quality"])
        for r in results:
            writer.writerow([r["listing_id"], r["title"], r["img_width"], r["img_height"], r["img_resolution"], r["img_quality"]])

        await db.update_background_task(
            IMAGE_AUDIT_TASK_ID, status="completed", done=done,
            progress_json={"good": good, "low": low, "no_image": no_image, "csv": buf.getvalue()},
        )
        logger.info(f"image-audit done: {good} good, {low} low, {no_image} no image")


async def _noop():
    return None


@router.get("/etsy/image-audit-status")
async def image_audit_status():
    """Get image audit progress and summary."""
    task = await db.get_background_task(IMAGE_AUDIT_TASK_ID)
    if not task:
        return {"status": "not_started"}
    progress = task.get("progress_json") or {}
    return {
        "status": task.get("status", "unknown"),
        "total": task.get("total", 0),
        "done": task.get("done", 0),
        "good": progress.get("good", 0),
        "low": progress.get("low", 0),
        "no_image": progress.get("no_image", 0),
    }


@router.get("/etsy/image-audit-csv")
async def download_image_audit_csv():
    """Download the completed image audit as CSV."""
    task = await db.get_background_task(IMAGE_AUDIT_TASK_ID)
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Audit not completed yet. Start with POST /etsy/image-audit")
    progress = task.get("progress_json") or {}
    csv_data = progress.get("csv", "")
    if not csv_data:
        raise HTTPException(status_code=404, detail="No audit data found")
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=etsy_image_audit.csv"},
    )


@router.post("/etsy/import-csv")
async def import_etsy_csv(file: UploadFile = File(...)):
    """Import CSV to bulk-update Etsy listings with tag validation."""
    access_token, shop_id = await ensure_etsy_token()

    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    required = {"listing_id", "title", "description", "tags"}
    if not required.issubset(set(reader.fieldnames or [])):
        missing = required - set(reader.fieldnames or [])
        raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(missing)}")

    rows = list(reader)
    results = []
    total_truncated = 0
    total_duplicates = 0
    for i, row in enumerate(rows):
        listing_id = row.get("listing_id", "").strip()
        if not listing_id:
            results.append({"row": i + 1, "status": "skipped", "reason": "no listing_id"})
            continue

        update_data = {}
        title = row.get("title", "").strip()
        if title:
            update_data["title"] = title[:140]
        description = row.get("description", "").strip()
        if description:
            update_data["description"] = description

        tag_issues = []
        tags_str = row.get("tags", "").strip()
        if tags_str:
            validation = validate_etsy_tags(tags_str)
            update_data["tags"] = validation["cleaned"]
            tag_issues = validation["issues"]
            total_truncated += sum(1 for iss in tag_issues if iss.startswith("truncated"))
            total_duplicates += sum(1 for iss in tag_issues if iss.startswith("duplicate"))

        if not update_data:
            results.append({"row": i + 1, "listing_id": listing_id, "status": "skipped", "reason": "nothing to update"})
            continue

        try:
            await etsy.update_listing(access_token, shop_id, listing_id, update_data)
            entry = {"row": i + 1, "listing_id": listing_id, "status": "ok"}
            if tag_issues:
                entry["tag_fixes"] = tag_issues
            results.append(entry)
        except httpx.HTTPStatusError as e:
            body = e.response.text[:200] if e.response else ""
            results.append({"row": i + 1, "listing_id": listing_id, "status": "error", "error": f"{e} | {body}"})
        except Exception as e:
            results.append({"row": i + 1, "listing_id": listing_id, "status": "error", "error": str(e)})

        await asyncio.sleep(0.3)

    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"] == "error")
    return {
        "total": len(rows),
        "updated": ok,
        "errors": errors,
        "tags_truncated": total_truncated,
        "duplicates_removed": total_duplicates,
        "results": results,
    }


@router.get("/etsy/shop-sections")
async def get_etsy_shop_sections():
    """Get shop sections for the connected Etsy shop."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        data = await etsy.get_shop_sections(access_token, shop_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/etsy/shipping-profiles")
async def get_etsy_shipping_profiles():
    """Get shipping profiles for the connected Etsy shop."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        data = await etsy.get_shipping_profiles(access_token, shop_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/etsy/listings/{listing_id}")
async def update_etsy_listing(listing_id: str, request: UpdateEtsyListingRequest):
    """Update a single Etsy listing's title, tags, and/or description."""
    access_token, shop_id = await ensure_etsy_token()

    data = {}
    if request.title is not None:
        if len(request.title) > 140:
            raise HTTPException(status_code=400, detail="Title must be 140 chars or less")
        data["title"] = request.title
    if request.tags is not None:
        if len(request.tags) > 13:
            raise HTTPException(status_code=400, detail="Maximum 13 tags allowed")
        for tag in request.tags:
            if len(tag) > 20:
                raise HTTPException(status_code=400, detail=f"Tag '{tag}' exceeds 20 chars")
        data["tags"] = request.tags
    if request.description is not None:
        if not request.description.strip():
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        data["description"] = request.description
    if request.materials is not None:
        clean_materials = []
        for m in request.materials:
            m = unicodedata.normalize("NFKD", m)
            # Replace hyphens/dashes with spaces (Etsy rejects them)
            m = re.sub(r'[\u2010-\u2015\-\u2212]', ' ', m)
            m = m.encode("ascii", "ignore").decode("ascii")
            # Keep only letters, numbers, spaces
            m = re.sub(r'[^a-zA-Z0-9 ]', '', m)
            m = re.sub(r' +', ' ', m).strip()
            if m:
                clean_materials.append(m)
        data["materials"] = clean_materials
    if request.who_made is not None:
        data["who_made"] = request.who_made
    if request.when_made is not None:
        data["when_made"] = request.when_made
    if request.is_supply is not None:
        data["is_supply"] = request.is_supply
    if request.shop_section_id is not None:
        data["shop_section_id"] = request.shop_section_id
    if request.shipping_profile_id is not None:
        data["shipping_profile_id"] = request.shipping_profile_id
    if request.should_auto_renew is not None:
        data["should_auto_renew"] = request.should_auto_renew

    # Auto-include production partner IDs (Printify)
    try:
        partners = await etsy.get_production_partners(access_token, shop_id)
        if partners:
            data["production_partner_ids"] = [p["production_partner_id"] for p in partners]
    except Exception as e:
        logger.warning(f"Failed to fetch production partners: {e}")

    if not data and request.primary_color is None and request.secondary_color is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        if data:
            result = await etsy.update_listing(access_token, shop_id, listing_id, data)
        else:
            result = {}

        # Update color properties (separate API calls)
        if request.primary_color and request.primary_color in ETSY_COLOR_VALUES:
            try:
                await etsy.update_listing_property(
                    access_token, shop_id, listing_id,
                    ETSY_PRIMARY_COLOR_PROPERTY_ID,
                    [ETSY_COLOR_VALUES[request.primary_color]],
                    [request.primary_color],
                )
            except Exception as e:
                logger.warning(f" Failed to set primary color: {e}")
        if request.secondary_color and request.secondary_color in ETSY_COLOR_VALUES:
            try:
                await etsy.update_listing_property(
                    access_token, shop_id, listing_id,
                    ETSY_SECONDARY_COLOR_PROPERTY_ID,
                    [ETSY_COLOR_VALUES[request.secondary_color]],
                    [request.secondary_color],
                )
            except Exception as e:
                logger.warning(f" Failed to set secondary color: {e}")

        return result
    except httpx.HTTPStatusError as e:
        try:
            etsy_body = e.response.json()
            detail = etsy_body.get("error", str(e))
        except Exception:
            detail = f"{e} | body: {e.response.text[:500]}"
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Etsy Listing Properties & Production Partners ===


@router.get("/etsy/taxonomy/{taxonomy_id}/properties")
async def get_etsy_taxonomy_properties(taxonomy_id: int):
    """Debug: get available properties for a taxonomy."""
    access_token, shop_id = await ensure_etsy_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.etsy.com/v3/application/seller-taxonomy/nodes/{taxonomy_id}/properties",
            headers={"x-api-key": etsy._x_api_key},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


@router.get("/etsy/listings/{listing_id}/properties")
async def get_etsy_listing_properties(listing_id: str):
    """Get listing properties (colors, etc.)."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        props = await etsy.get_listing_properties(access_token, shop_id, listing_id)
        colors = {"primary_color": None, "secondary_color": None}
        for prop in props:
            pid = prop.get("property_id")
            if pid == ETSY_PRIMARY_COLOR_PROPERTY_ID:
                vals = prop.get("values", [])
                colors["primary_color"] = vals[0] if vals else None
            elif pid == ETSY_SECONDARY_COLOR_PROPERTY_ID:
                vals = prop.get("values", [])
                colors["secondary_color"] = vals[0] if vals else None
        return {"properties": props, "colors": colors}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/etsy/production-partners")
async def get_etsy_production_partners():
    """Get production partners for the shop."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        partners = await etsy.get_production_partners(access_token, shop_id)
        return {"partners": partners}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Etsy Listing Image Management ===


@router.put("/etsy/listings/{listing_id}/images/alt-texts")
async def update_etsy_images_alt_texts(listing_id: str, request: BulkAltTextRequest):
    """Set alt texts on the first N images of a listing (re-uploads each image)."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        images_data = await etsy.get_listing_images(access_token, listing_id)
        images = images_data.get("results", [])
        images.sort(key=lambda x: x.get("rank", 999))

        results = []
        for i, alt_text in enumerate(request.alt_texts):
            if i >= len(images) or not alt_text.strip():
                continue
            img = images[i]
            try:
                await etsy.set_image_alt_text(
                    access_token, shop_id, listing_id,
                    str(img["listing_image_id"]),
                    img["url_fullxfull"],
                    alt_text[:250],
                    img.get("rank", i + 1),
                )
                results.append({"image_id": img["listing_image_id"], "status": "ok"})
            except Exception as e:
                logger.warning(f" Failed for image {img['listing_image_id']}: {e}")
                results.append({"image_id": img["listing_image_id"], "status": "error", "error": str(e)})
        return {"results": results}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/etsy/listings/{listing_id}/images")
async def get_etsy_listing_images(listing_id: str):
    """Get all images for an Etsy listing."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        data = await etsy.get_listing_images(access_token, listing_id)
        return data
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/etsy/listings/{listing_id}/images")
async def upload_etsy_listing_image(
    listing_id: str,
    image: UploadFile = File(...),
    rank: Optional[int] = Form(None),
):
    """Upload a new image to an Etsy listing."""
    access_token, shop_id = await ensure_etsy_token()

    if image.content_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, or WebP images allowed")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")

    try:
        result = await etsy.upload_listing_image(
            access_token, shop_id, listing_id,
            image_bytes, image.filename or "image.jpg", rank,
        )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/etsy/listings/{listing_id}/images/{image_id}")
async def delete_etsy_listing_image(listing_id: str, image_id: str):
    """Delete an image from an Etsy listing."""
    access_token, shop_id = await ensure_etsy_token()
    try:
        await etsy.delete_listing_image(access_token, shop_id, listing_id, image_id)
        return {"status": "deleted"}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/etsy/listings/{listing_id}/images/{image_id}/set-primary")
async def set_etsy_listing_image_primary(listing_id: str, image_id: str):
    """Set an existing image as primary by re-uploading with rank=1."""
    access_token, shop_id = await ensure_etsy_token()

    try:
        # Get image details to find URL
        images_data = await etsy.get_listing_images(access_token, listing_id)
        target = None
        for img in images_data.get("results", []):
            if str(img["listing_image_id"]) == image_id:
                target = img
                break
        if not target:
            raise HTTPException(status_code=404, detail="Image not found")

        # Download from Etsy CDN
        async with httpx.AsyncClient() as client:
            resp = await client.get(target["url_fullxfull"], timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            image_bytes = resp.content

        # Delete then re-upload with rank=1
        await etsy.delete_listing_image(access_token, shop_id, listing_id, image_id)
        result = await etsy.upload_listing_image(
            access_token, shop_id, listing_id,
            image_bytes, f"image_{image_id}.jpg", rank=1,
        )
        return result
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/etsy/listings/suggest-seo")
async def suggest_seo(request: SeoSuggestRequest):
    """Generate AI SEO suggestions WITHOUT saving to Etsy. Returns proposed title/tags/description."""
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = await listing_gen.regenerate_seo_from_existing(
            current_title=request.title,
            current_tags=request.tags,
            current_description=request.description,
        )
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === AI Fill (vision-based SEO generation) ===


@router.post("/etsy/listings/ai-fill")
async def ai_fill_listing(request: AIFillRequest):
    """Generate SEO content from poster image using Claude vision. Does NOT save to Etsy."""
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    if not request.image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    try:
        result = await listing_gen.generate_seo_from_image(
            image_url=request.image_url,
            current_title=request.current_title,
            niche=request.niche,
            enabled_sizes=request.enabled_sizes or [],
        )
        result = validate_seo_data(result)
        # Safety net: clean description to only show enabled sizes
        if request.enabled_sizes and result.get("description"):
            result["description"] = clean_description(result["description"], request.enabled_sizes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/etsy/listings/ai-fill-batch")
async def ai_fill_batch(request: AIFillBatchRequest):
    """Generate SEO content for multiple listings. Does NOT save to Etsy."""
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    results = []
    for item in request.listings:
        try:
            result = await listing_gen.generate_seo_from_image(
                image_url=item.image_url,
                current_title=item.current_title,
            )
            result = validate_seo_data(result)
            result["listing_id"] = item.listing_id
            result["status"] = "ok"
            results.append(result)
        except Exception as e:
            results.append({
                "listing_id": item.listing_id,
                "status": "error",
                "error": str(e),
            })

        await asyncio.sleep(1.5)  # rate limit

    return {
        "results": results,
        "total": len(results),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "failed": sum(1 for r in results if r.get("status") == "error"),
    }


@router.post("/etsy/listings/bulk-seo")
async def bulk_update_etsy_seo(request: BulkSeoRequest):
    """Regenerate SEO for multiple Etsy listings using Claude, then update on Etsy."""
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    access_token, shop_id = await ensure_etsy_token()

    results = []
    for listing_id in request.listing_ids:
        try:
            current = await etsy.get_listing(access_token, listing_id)
            current_title = current.get("title", "")
            current_tags = current.get("tags", [])
            current_desc = current.get("description", "")

            new_listing = await listing_gen.regenerate_seo_from_existing(
                current_title=current_title,
                current_tags=current_tags,
                current_description=current_desc,
            )

            update_data = {
                "title": new_listing.title,
                "tags": new_listing.tags,
                "description": new_listing.description,
            }
            await etsy.update_listing(access_token, shop_id, listing_id, update_data)

            results.append({
                "listing_id": listing_id,
                "status": "updated",
                "old_title": current_title,
                "new_title": new_listing.title,
                "new_tags": new_listing.tags,
            })
        except Exception as e:
            results.append({
                "listing_id": listing_id,
                "status": "error",
                "error": str(e),
            })

        await asyncio.sleep(0.25)

    updated = sum(1 for r in results if r["status"] == "updated")
    failed = sum(1 for r in results if r["status"] == "error")

    return {
        "total": len(request.listing_ids),
        "updated": updated,
        "failed": failed,
        "results": results,
    }


@router.post("/etsy/listings/remove-size-line")
async def remove_size_line_from_descriptions(line: str = "24×36 inches (60×90 cm)"):
    """Remove a bullet-point line (e.g. '• 24×36 inches (60×90 cm)') from all active Etsy listing descriptions."""
    access_token, shop_id = await ensure_etsy_token()
    all_listings = await etsy.get_all_listings(access_token, shop_id)

    # Build pattern: optional bullet/dash, the line text (flexible x/×), optional trailing newline
    escaped = re.escape(line)
    # Allow both 'x' and '×' interchangeably, and flexible whitespace
    flexible = escaped.replace(r"×", r"[x×]").replace(r"x", r"[x×]")
    line_pattern = re.compile(
        r"[ \t]*[•\-\*]?\s*" + flexible + r"[ \t]*\n?",
        re.IGNORECASE,
    )

    results = []
    for listing in all_listings:
        listing_id = str(listing["listing_id"])
        desc = listing.get("description", "")
        if not line_pattern.search(desc):
            continue

        new_desc = line_pattern.sub("", desc)
        # Remove resulting blank lines (double newlines → single)
        new_desc = re.sub(r"\n{3,}", "\n\n", new_desc)
        new_desc = new_desc.strip()

        if new_desc == desc:
            continue

        try:
            await etsy.update_listing(access_token, shop_id, listing_id, {"description": new_desc})
            results.append({"listing_id": listing_id, "status": "updated", "title": listing.get("title", "")[:60]})
        except Exception as e:
            results.append({"listing_id": listing_id, "status": "error", "error": str(e)})

        await asyncio.sleep(0.3)

    return {
        "line_removed": line,
        "total_listings": len(all_listings),
        "matched": len(results),
        "updated": sum(1 for r in results if r["status"] == "updated"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }


@router.post("/etsy/listings/add-disclaimer")
async def add_disclaimer_to_all_listings():
    """Add the standard poster disclaimer to all active Etsy listings that don't have it yet."""
    access_token, shop_id = await ensure_etsy_token()
    all_listings = await etsy.get_all_listings(access_token, shop_id)

    results = []
    skipped = 0
    for listing in all_listings:
        listing_id = str(listing["listing_id"])
        desc = listing.get("description", "")

        new_desc = ensure_disclaimer(desc)
        if new_desc == desc:
            skipped += 1
            continue

        # Clean up extra blank lines
        new_desc = re.sub(r"\n{3,}", "\n\n", new_desc).strip()

        try:
            await etsy.update_listing(access_token, shop_id, listing_id, {"description": new_desc})
            results.append({"listing_id": listing_id, "status": "updated", "title": listing.get("title", "")[:60]})
        except Exception as e:
            results.append({"listing_id": listing_id, "status": "error", "error": str(e)})

        await asyncio.sleep(0.3)

    return {
        "total_listings": len(all_listings),
        "already_had_disclaimer": skipped,
        "updated": sum(1 for r in results if r["status"] == "updated"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
