#!/usr/bin/env python3
"""Backup original poster images from Leonardo CDN and upscale via Replicate.

Usage (from project root):
  # On VPS via docker exec:
  docker exec -it <backend-container> python scripts/backup_and_upscale.py

  # Or locally with SSH tunnel running:
  cd backend && python scripts/backup_and_upscale.py

Pipeline per image:
  1. Download from Leonardo CDN -> save to /var/www/dovshop/media/originals/
  2. Upscale 4x via Replicate Real-ESRGAN -> save to /var/www/dovshop/media/upscaled/
  3. Update DB with local_path, upscaled_path
  4. Generate report CSV
"""

import asyncio
import csv
import io
import logging
import os
import sys
import time
from pathlib import Path

import asyncpg
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Load .env from project root if running locally
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://poster:poster@localhost:5432/poster_generator",
)
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API") or os.environ.get("REPLICATE_API_TOKEN", "")

# Override with MEDIA_DIR env var if running inside docker
_media_base = Path(os.environ.get("MEDIA_DIR", "/var/www/dovshop/media"))
ORIGINALS_DIR = _media_base / "originals"
UPSCALED_DIR = _media_base / "upscaled"
REPORT_DIR = _media_base

BATCH_SIZE = 5
UPSCALE_MODEL = "nightmareai/real-esrgan:42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73abf41610695738c1d7b"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backup")

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def ensure_columns(pool: asyncpg.Pool):
    """Add backup/upscale columns if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS local_path TEXT"
        )
        await conn.execute(
            "ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS upscaled_path TEXT"
        )
        await conn.execute(
            "ALTER TABLE generated_images ADD COLUMN IF NOT EXISTS upscaled_url TEXT"
        )
    log.info("DB columns ensured")


async def get_images_to_backup(pool: asyncpg.Pool) -> list[dict]:
    """Get generated images for active listings that haven't been backed up."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT gi.id, gi.url, gi.image_id, gi.generation_id,
                   p.etsy_listing_id
            FROM generated_images gi
            JOIN products p ON gi.product_id = p.id
            WHERE p.etsy_listing_id IS NOT NULL
              AND p.status != 'deleted'
              AND gi.local_path IS NULL
              AND gi.url IS NOT NULL
            ORDER BY gi.id
            """
        )
    return [dict(r) for r in rows]


async def get_images_to_upscale(pool: asyncpg.Pool) -> list[dict]:
    """Get backed-up images for active listings that haven't been upscaled."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT gi.id, gi.image_id, gi.local_path, gi.generation_id,
                   p.etsy_listing_id
            FROM generated_images gi
            JOIN products p ON gi.product_id = p.id
            WHERE p.etsy_listing_id IS NOT NULL
              AND p.status != 'deleted'
              AND gi.local_path IS NOT NULL
              AND gi.upscaled_path IS NULL
            ORDER BY gi.id
            """
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Backup: download from CDN
# ---------------------------------------------------------------------------


async def backup_image(
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    img: dict,
) -> dict:
    """Download one image from CDN and save locally."""
    img_id = img["id"]
    listing_id = img["etsy_listing_id"] or "no_listing"
    url = img["url"]
    filename = f"{listing_id}_{img_id}.png"
    local_path = ORIGINALS_DIR / filename

    if local_path.exists():
        # Already on disk, just update DB
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE generated_images SET local_path = $1 WHERE id = $2",
                str(local_path), img_id,
            )
        return {"id": img_id, "listing_id": listing_id, "status": "exists", "local_path": str(local_path)}

    try:
        resp = await client.get(url, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()

        local_path.write_bytes(resp.content)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE generated_images SET local_path = $1 WHERE id = $2",
                str(local_path), img_id,
            )
        return {"id": img_id, "listing_id": listing_id, "status": "ok", "local_path": str(local_path)}

    except Exception as e:
        return {"id": img_id, "listing_id": listing_id, "status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Upscale: Replicate Real-ESRGAN
# ---------------------------------------------------------------------------


async def upscale_image(
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    img: dict,
) -> dict:
    """Upscale one image via Replicate API."""
    img_id = img["id"]
    listing_id = img["etsy_listing_id"] or "no_listing"
    local_path = Path(img["local_path"])
    filename = f"{listing_id}_{img_id}_4x.png"
    upscaled_path = UPSCALED_DIR / filename

    if upscaled_path.exists():
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE generated_images SET upscaled_path = $1 WHERE id = $2",
                str(upscaled_path), img_id,
            )
        return {"id": img_id, "listing_id": listing_id, "status": "exists", "upscaled_path": str(upscaled_path)}

    if not local_path.exists():
        return {"id": img_id, "listing_id": listing_id, "status": "error", "error": "local file missing"}

    try:
        import base64
        from PIL import Image

        MAX_PIXELS = 1_500_000  # Conservative limit for Replicate GPU

        img_pil = Image.open(local_path)
        w, h = img_pil.size
        scale = 4

        if w * h > MAX_PIXELS:
            # Resize to fit GPU, keep aspect ratio
            ratio = (MAX_PIXELS / (w * h)) ** 0.5
            new_w = int(w * ratio) & ~1  # even numbers
            new_h = int(h * ratio) & ~1
            img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)
            log.info(f"    Resized {w}x{h} -> {new_w}x{new_h} to fit GPU, 4x -> {new_w*4}x{new_h*4}")

        buf = io.BytesIO()
        img_pil.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        b64_image = base64.b64encode(image_bytes).decode()
        data_uri = f"data:image/png;base64,{b64_image}"

        # Submit with retry on 429
        for attempt in range(3):
            resp = await client.post(
                "https://api.replicate.com/v1/predictions",
                headers={
                    "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "version": UPSCALE_MODEL.split(":")[1],
                    "input": {"image": data_uri, "scale": scale},
                },
                timeout=30.0,
            )
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f"    429 rate limit, waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            return {"id": img_id, "listing_id": listing_id, "status": "error", "error": "429 after 3 retries"}
        prediction_id = resp.json()["id"]

        # Poll for completion (max ~4 min)
        for _ in range(120):
            await asyncio.sleep(2)
            poll_resp = await client.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {REPLICATE_API_TOKEN}"},
                timeout=15.0,
            )
            poll_resp.raise_for_status()
            result = poll_resp.json()

            if result["status"] == "succeeded":
                output_url = result["output"]
                if isinstance(output_url, list):
                    output_url = output_url[0]

                dl_resp = await client.get(output_url, timeout=120.0, follow_redirects=True)
                dl_resp.raise_for_status()
                upscaled_path.write_bytes(dl_resp.content)

                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE generated_images SET upscaled_path = $1, upscaled_url = $2 WHERE id = $3",
                        str(upscaled_path), output_url, img_id,
                    )
                return {"id": img_id, "listing_id": listing_id, "status": "ok", "upscaled_path": str(upscaled_path)}

            elif result["status"] == "failed":
                return {"id": img_id, "listing_id": listing_id, "status": "error", "error": f"replicate: {result.get('error','')}"}

        return {"id": img_id, "listing_id": listing_id, "status": "error", "error": "replicate timeout"}

    except Exception as e:
        return {"id": img_id, "listing_id": listing_id, "status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run_pipeline():
    if not REPLICATE_API_TOKEN:
        log.warning("REPLICATE_API not set — backup only, no upscale")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    await ensure_columns(pool)

    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    UPSCALED_DIR.mkdir(parents=True, exist_ok=True)

    report: list[dict] = []

    # --- Phase 1: Backup ---
    to_backup = await get_images_to_backup(pool)
    log.info(f"Phase 1: {len(to_backup)} images to backup")

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(to_backup), BATCH_SIZE):
            batch = to_backup[batch_start:batch_start + BATCH_SIZE]
            tasks = [backup_image(client, pool, img) for img in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, res in enumerate(results):
                idx = batch_start + i + 1
                total = len(to_backup)
                if isinstance(res, Exception):
                    log.error(f"  {idx}/{total} backup EXCEPTION: {res}")
                    report.append({"id": batch[i]["id"], "listing_id": batch[i].get("etsy_listing_id", ""), "status": f"error: {res}"})
                elif res["status"] == "ok":
                    log.info(f"  {idx}/{total} backed up: listing_id={res['listing_id']}")
                    report.append(res)
                elif res["status"] == "exists":
                    log.info(f"  {idx}/{total} already on disk: listing_id={res['listing_id']}")
                    report.append(res)
                else:
                    log.error(f"  {idx}/{total} backup failed: listing_id={res['listing_id']} -- {res.get('error','')}")
                    report.append(res)

            await asyncio.sleep(0.5)

    # --- Phase 2: Upscale (one at a time to avoid rate limits) ---
    to_upscale = await get_images_to_upscale(pool)
    log.info(f"Phase 2: {len(to_upscale)} images to upscale")

    async with httpx.AsyncClient() as client:
        for idx, img in enumerate(to_upscale, 1):
            total = len(to_upscale)
            try:
                res = await upscale_image(client, pool, img)
            except Exception as e:
                log.error(f"  {idx}/{total} upscale EXCEPTION: {e}")
                continue

            if res["status"] == "ok":
                log.info(f"  {idx}/{total} upscaled: listing_id={res['listing_id']}")
            elif res["status"] == "exists":
                log.info(f"  {idx}/{total} already upscaled: listing_id={res['listing_id']}")
            else:
                log.error(f"  {idx}/{total} upscale failed: listing_id={res['listing_id']} -- {res.get('error','')}")

            existing = next((r for r in report if r.get("id") == res["id"]), None)
            if existing:
                existing["upscaled_path"] = res.get("upscaled_path", "")
                existing["upscale_status"] = res["status"]
            else:
                report.append(res)

            await asyncio.sleep(5)  # rate limit between images

    # --- Phase 3: Report ---
    report_path = REPORT_DIR / "upscale_report.csv"
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "listing_id", "status", "local_path", "upscaled_path", "upscale_status", "error",
        ], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report)

    ok_backup = sum(1 for r in report if r.get("status") in ("ok", "exists"))
    ok_upscale = sum(1 for r in report if r.get("upscale_status") in ("ok", "exists"))
    errors = sum(1 for r in report if "error" in r.get("status", "") or "error" in r.get("upscale_status", ""))

    log.info("=" * 50)
    log.info(f"DONE: {ok_backup} backed up, {ok_upscale} upscaled, {errors} errors")
    log.info(f"Report: {report_path}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_pipeline())
