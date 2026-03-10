"""Pinterest integration routes — auth, boards, pins, analytics, bulk generate."""

import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

import database as db
from deps import pinterest_api, pinterest_generator, pinterest_scheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pinterest", tags=["pinterest"])


# === Pydantic models ===

class CreatePinRequest(BaseModel):
    product_id: int
    board_id: str
    title: Optional[str] = None       # If None, AI-generates
    description: Optional[str] = None  # If None, AI-generates
    image_url: Optional[str] = None    # If None, uses product image
    link: Optional[str] = None         # If None, uses Etsy URL
    alt_text: str = ""
    scheduled_at: Optional[str] = None  # ISO format or None for immediate


EST = timezone(timedelta(hours=-5))

# Pinterest publish slots in EST (hours)
PINTEREST_SLOTS_EST = [8, 12, 14, 17, 20]


class BulkGenerateRequest(BaseModel):
    product_ids: List[int]
    board_id: str


# === Helpers ===

async def ensure_pinterest_token() -> str:
    """Get a valid Pinterest access token, refreshing if expired."""
    tokens = await db.get_pinterest_tokens()
    if not tokens:
        raise HTTPException(status_code=400, detail="Pinterest not connected")

    access_token = tokens["access_token"]

    if tokens["expires_at"] < int(time.time()):
        try:
            new_tokens = await pinterest_api.refresh_access_token(tokens["refresh_token"])
            await db.save_pinterest_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
            )
            access_token = new_tokens.access_token
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Pinterest token refresh failed: {e}")

    return access_token


# === Auth ===

@router.get("/status")
async def get_pinterest_status():
    """Check Pinterest connection status."""
    if not pinterest_api.is_configured:
        return {"configured": False, "connected": False}

    tokens = await db.get_pinterest_tokens()
    if not tokens:
        return {"configured": True, "connected": False}

    if tokens["expires_at"] < int(time.time()):
        try:
            new_tokens = await pinterest_api.refresh_access_token(tokens["refresh_token"])
            await db.save_pinterest_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
            )
            return {"configured": True, "connected": True, "username": tokens.get("username")}
        except Exception:
            return {"configured": True, "connected": False, "error": "Token expired, re-connect needed"}

    return {"configured": True, "connected": True, "username": tokens.get("username")}


@router.get("/auth-url")
async def get_pinterest_auth_url():
    """Generate Pinterest OAuth2 authorization URL."""
    if not pinterest_api.is_configured:
        raise HTTPException(status_code=400, detail="PINTEREST_APP_ID not configured in .env")
    return {"url": pinterest_api.get_auth_url()}


@router.get("/callback")
async def pinterest_oauth_callback(code: str, state: str = "dovshop"):
    """OAuth2 callback — exchanges code for tokens."""
    try:
        tokens = await pinterest_api.exchange_code(code)

        # Get username
        username = ""
        try:
            user_info = await pinterest_api.get_user_account(tokens.access_token)
            username = user_info.get("username", "")
        except Exception as e:
            logger.warning(f"Could not fetch Pinterest username: {e}")

        await db.save_pinterest_tokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.expires_at,
            username=username,
        )

        # Auto-sync boards on connect
        try:
            boards = await pinterest_api.get_boards(tokens.access_token)
            await db.save_pinterest_boards(boards)
        except Exception as e:
            logger.warning(f"Could not sync boards on connect: {e}")

        return HTMLResponse("""
            <html><body>
            <h2>Pinterest connected successfully!</h2>
            <p>You can close this window.</p>
            <script>
                if (window.opener) {
                    window.opener.postMessage('pinterest-connected', '*');
                }
                setTimeout(() => window.close(), 1500);
            </script>
            </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"""
            <html><body>
            <h2>Pinterest connection failed</h2>
            <p>{str(e)}</p>
            <p>Please close this window and try again.</p>
            </body></html>
        """)


@router.post("/disconnect")
async def disconnect_pinterest():
    """Remove stored Pinterest tokens."""
    await db.delete_pinterest_tokens()
    return {"ok": True}


# === Boards ===

@router.get("/boards")
async def list_boards():
    """Get Pinterest boards (synced from API)."""
    access_token = await ensure_pinterest_token()
    try:
        boards = await pinterest_api.get_boards(access_token)
        count = await db.save_pinterest_boards(boards)
        return {"boards": boards, "synced": count}
    except Exception as e:
        # Fallback: return cached boards
        cached = await db.get_pinterest_boards()
        if cached:
            return {"boards": cached, "cached": True}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards")
async def create_board(name: str, description: str = ""):
    """Create a new Pinterest board."""
    access_token = await ensure_pinterest_token()
    result = await pinterest_api.create_board(access_token, name, description)
    # Re-sync boards after creation
    boards = await pinterest_api.get_boards(access_token)
    await db.save_pinterest_boards(boards)
    return result


# === Products for pin creation ===

@router.get("/products")
async def list_products_for_pinning():
    """Get all published products with mockup count and pin stats."""
    products = await db.get_pinterest_products()
    return {"products": products}


# === Pins ===

@router.post("/pins/queue")
async def queue_pin(req: CreatePinRequest):
    """Queue a pin for publishing. Auto-generates title/description if not provided."""

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT * FROM products WHERE id = $1", req.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    etsy_url = ""
    if product["etsy_listing_id"]:
        etsy_url = f"https://www.etsy.com/listing/{product['etsy_listing_id']}"

    title = req.title
    description = req.description
    alt_text = req.alt_text

    # Auto-generate if title or description missing
    if not title or not description:
        content = await pinterest_generator.generate_pin_content(
            etsy_title=product["title"] or "",
            etsy_tags=[],
            niche=product.get("style", "wall art"),
            etsy_url=etsy_url,
        )
        title = title or content["title"]
        description = description or content["description"]
        alt_text = alt_text or content.get("alt_text", "")

    image_url = req.image_url or product.get("preferred_mockup_url") or product["image_url"]
    link = req.link or etsy_url or f"https://dovshop.org/poster/{req.product_id}"

    scheduled_at = None
    if req.scheduled_at:
        scheduled_at = datetime.fromisoformat(req.scheduled_at)

    pin_id = await db.queue_pin(
        product_id=req.product_id,
        board_id=req.board_id,
        title=title,
        description=description,
        image_url=image_url,
        link=link,
        alt_text=alt_text,
        scheduled_at=scheduled_at,
    )
    return {"id": pin_id, "status": "queued", "title": title}


@router.post("/pins/publish-now")
async def publish_queued_pins():
    """Immediately publish all queued pins."""
    result = await pinterest_scheduler.publish_due_pins()
    return result


@router.get("/pins/queue")
async def get_pin_queue():
    """Get all queued pins."""
    pins = await db.get_queued_pins(limit=100)
    return {"pins": pins}


@router.get("/pins/published")
async def get_published_pins():
    """Get published pins with analytics."""
    pins = await db.get_published_pins(limit=100)
    return {"pins": pins}


@router.delete("/pins/{pin_db_id}")
async def delete_pin(pin_db_id: int, from_pinterest: bool = False):
    """Delete a pin record. Optionally also delete from Pinterest."""
    if from_pinterest:
        access_token = await ensure_pinterest_token()
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT pin_id FROM pinterest_pins WHERE id = $1", pin_db_id)
        if row and row["pin_id"]:
            try:
                await pinterest_api.delete_pin(access_token, row["pin_id"])
            except Exception as e:
                logger.warning(f"Could not delete pin from Pinterest: {e}")

    await db.delete_pin_record(pin_db_id)
    return {"ok": True}


# === Analytics ===

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Get aggregate Pinterest stats."""
    stats = await db.get_pin_stats_summary()
    return stats


@router.post("/analytics/sync")
async def sync_analytics():
    """Sync analytics for all published pins from Pinterest API."""
    result = await pinterest_scheduler.sync_pin_analytics()
    return result


# === AI Generate ===

@router.post("/pins/generate")
async def generate_pin_content(product_id: int, variant: int = 1):
    """AI-generate Pinterest-optimized pin content for a product."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    etsy_url = ""
    if product["etsy_listing_id"]:
        etsy_url = f"https://www.etsy.com/listing/{product['etsy_listing_id']}"

    result = await pinterest_generator.generate_pin_content(
        etsy_title=product["title"] or "",
        etsy_tags=[],  # Could fetch from Etsy if needed
        niche=product.get("style", "wall art"),
        etsy_url=etsy_url,
        variant=variant,
    )
    return result


async def _next_pinterest_slot() -> datetime:
    """Calculate the next available Pinterest publish slot.

    Uses 5 fixed EST slots per day: 8:00, 12:00, 14:00, 17:00, 20:00.
    Finds the last scheduled pin time, then picks the next slot after it.
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT MAX(scheduled_at) AS last_slot
            FROM pinterest_pins
            WHERE status = 'queued' AND scheduled_at IS NOT NULL
        """)

    now_utc = datetime.now(timezone.utc)
    now_est = now_utc.astimezone(EST)

    if row and row["last_slot"]:
        last = row["last_slot"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        last_est = last.astimezone(EST)
    else:
        last_est = now_est

    # Find next slot after last_est
    for hour in PINTEREST_SLOTS_EST:
        candidate = last_est.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > last_est and candidate > now_est:
            return candidate.astimezone(timezone.utc)

    # All today's slots passed — go to next day's first slot
    next_day = last_est.date() + timedelta(days=1)
    first_slot = datetime(next_day.year, next_day.month, next_day.day,
                          PINTEREST_SLOTS_EST[0], 0, tzinfo=EST)
    # Make sure it's also after now
    if first_slot <= now_est:
        next_day = now_est.date() + timedelta(days=1)
        first_slot = datetime(next_day.year, next_day.month, next_day.day,
                              PINTEREST_SLOTS_EST[0], 0, tzinfo=EST)
    return first_slot.astimezone(timezone.utc)


@router.post("/pins/bulk-generate")
async def bulk_generate_pins(req: BulkGenerateRequest):
    """AI-generate and queue pins for multiple products.

    For each product:
    1. Pick next mockup image via round-robin
    2. AI-generate Pinterest-optimized title/description
    3. Assign next available EST time slot
    4. Queue pin
    """
    pool = await db.get_pool()
    results = []
    queued_count = 0

    for product_id in req.product_ids:
        async with pool.acquire() as conn:
            product = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
        if not product:
            results.append({"product_id": product_id, "error": "not found"})
            continue

        try:
            etsy_url = ""
            if product["etsy_listing_id"]:
                etsy_url = f"https://www.etsy.com/listing/{product['etsy_listing_id']}"

            # Round-robin mockup selection
            image_url = None
            if product.get("source_image_id"):
                image_url = await db.get_next_mockup_url(product_id, product["source_image_id"])
            if not image_url:
                image_url = product.get("preferred_mockup_url") or product["image_url"]

            # Count existing pins to determine variant number
            existing_pins = await db.get_pins_for_product(product_id)
            variant = len(existing_pins) + 1

            content = await pinterest_generator.generate_pin_content(
                etsy_title=product["title"] or "",
                etsy_tags=[],
                niche=product.get("style", "wall art"),
                etsy_url=etsy_url,
                variant=variant,
            )

            scheduled_at = await _next_pinterest_slot()

            pin_id = await db.queue_pin(
                product_id=product_id,
                board_id=req.board_id,
                title=content["title"],
                description=content["description"],
                image_url=image_url,
                link=etsy_url or "https://dovshop.org",
                alt_text=content.get("alt_text", ""),
                scheduled_at=scheduled_at,
            )

            scheduled_est = scheduled_at.astimezone(EST)
            results.append({
                "product_id": product_id,
                "pin_id": pin_id,
                "title": content["title"],
                "image_url": image_url,
                "scheduled_at": scheduled_at.isoformat(),
                "scheduled_est": scheduled_est.strftime("%b %d, %H:%M EST"),
            })
            queued_count += 1
        except Exception as e:
            results.append({"product_id": product_id, "error": str(e)})

    return {
        "results": results,
        "queued": queued_count,
    }


@router.get("/pins/product/{product_id}")
async def get_pins_for_product(product_id: int):
    """Get all pins (queued + published) for a product."""
    pins = await db.get_pins_for_product(product_id)
    return {"pins": pins}
