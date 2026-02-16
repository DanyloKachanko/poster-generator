import re
import time
import asyncio
import unicodedata
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import httpx

from etsy import ETSY_COLOR_VALUES, ETSY_PRIMARY_COLOR_PROPERTY_ID, ETSY_SECONDARY_COLOR_PROPERTY_ID
from deps import etsy, printify, listing_gen
from description_utils import clean_description, ensure_disclaimer, POSTER_DISCLAIMER
import database as db

router = APIRouter(tags=["etsy"])

_etsy_pkce_state: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def ensure_etsy_token() -> tuple:
    """Get a valid Etsy access token, auto-refreshing if expired.

    Returns (access_token, shop_id) tuple.
    Auto-fetches shop_id via API if missing from DB.
    """
    tokens = await db.get_etsy_tokens()
    if not tokens:
        raise HTTPException(status_code=400, detail="Etsy not connected")

    access_token = tokens["access_token"]
    shop_id = tokens.get("shop_id", "")

    if tokens["expires_at"] < int(time.time()):
        try:
            new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
            await db.save_etsy_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
                shop_id=shop_id,
            )
            access_token = new_tokens.access_token
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token refresh failed: {e}")

    # Auto-fetch shop_id if missing
    if not shop_id:
        try:
            user_info = await etsy.get_me(access_token)
            user_id = str(user_info.get("user_id", ""))
            if user_id:
                shops_data = await etsy.get_user_shops(access_token, user_id)
                shop_id = str(shops_data.get("shop_id", ""))
                if shop_id:
                    await db.save_etsy_tokens(
                        access_token=access_token,
                        refresh_token=tokens["refresh_token"],
                        expires_at=tokens["expires_at"],
                        shop_id=shop_id,
                    )
        except Exception as e:
            print(f"[ensure_etsy_token] auto-fetch shop_id failed: {e}")

    if not shop_id:
        raise HTTPException(status_code=400, detail="No Etsy shop_id stored. Reconnect Etsy.")

    return access_token, shop_id


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
            words = tag.split()
            shortened = " ".join(words[:3])
            while len(shortened) > 20 and len(words) > 1:
                words = words[:-1]
                shortened = " ".join(words)
            old = tags[i]
            tags[i] = shortened[:20]
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
        tags.append(f"wall art print {len(tags)}"[:20])
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
# ETSY OAUTH + SYNC ENDPOINTS
# ---------------------------------------------------------------------------


@router.get("/etsy/status")
async def get_etsy_status():
    """Check if Etsy is connected."""
    if not etsy.is_configured:
        return {"configured": False, "connected": False}

    tokens = await db.get_etsy_tokens()
    if not tokens:
        return {"configured": True, "connected": False}

    # Check if tokens are expired and try refresh
    if tokens["expires_at"] < int(time.time()):
        try:
            new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
            await db.save_etsy_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
            )
            return {"configured": True, "connected": True, "shop_id": tokens.get("shop_id")}
        except Exception:
            return {"configured": True, "connected": False, "error": "Token expired, re-connect needed"}

    return {"configured": True, "connected": True, "shop_id": tokens.get("shop_id")}


@router.get("/etsy/auth-url")
async def get_etsy_auth_url():
    """Generate Etsy OAuth authorization URL."""
    global _etsy_pkce_state

    if not etsy.is_configured:
        raise HTTPException(status_code=400, detail="ETSY_API_KEY not configured in .env")

    auth_data = etsy.get_auth_url(
        scopes="email_r listings_r listings_w listings_d shops_r shops_w transactions_r"
    )
    _etsy_pkce_state = {
        "state": auth_data["state"],
        "code_verifier": auth_data["code_verifier"],
    }

    return {"url": auth_data["url"]}


@router.get("/etsy/callback")
async def etsy_oauth_callback(code: str, state: str):
    """OAuth callback — exchanges code for tokens."""
    global _etsy_pkce_state

    if not _etsy_pkce_state or _etsy_pkce_state.get("state") != state:
        return {"error": "Invalid state. Please try connecting again."}

    try:
        tokens = await etsy.exchange_code(code, _etsy_pkce_state["code_verifier"])
        _etsy_pkce_state = {}

        # Get user info to find shop_id
        etsy_user_id = ""
        shop_id = ""
        try:
            user_info = await etsy.get_me(tokens.access_token)
            print(f"[Etsy callback] get_me response: {user_info}")
            etsy_user_id = str(user_info.get("user_id", ""))
            shop_id = str(user_info.get("shop_id", ""))
        except Exception as e:
            print(f"[Etsy callback] get_me failed: {e}")
            # Fallback: parse user_id from token (format: "{user_id}.{rest}")
            token_parts = tokens.access_token.split(".")
            if token_parts:
                etsy_user_id = token_parts[0]
            print(f"[Etsy callback] parsed user_id from token: {etsy_user_id}")

        # If shop_id still missing, use authenticated shops endpoint
        if not shop_id and etsy_user_id:
            try:
                shops_data = await etsy.get_user_shops(tokens.access_token, etsy_user_id)
                print(f"[Etsy callback] get_user_shops response: {shops_data}")
                if shops_data.get("shop_id"):
                    shop_id = str(shops_data["shop_id"])
            except Exception as e:
                print(f"[Etsy callback] get_user_shops failed: {e}")

        print(f"[Etsy callback] final: user_id={etsy_user_id}, shop_id={shop_id}")

        await db.save_etsy_tokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.expires_at,
            etsy_user_id=etsy_user_id,
            shop_id=shop_id,
        )

        # Return an HTML page that closes itself and notifies opener
        return HTMLResponse("""
            <html><body>
            <h2>Etsy connected successfully!</h2>
            <p>You can close this window.</p>
            <script>
                if (window.opener) {
                    window.opener.postMessage('etsy-connected', '*');
                }
                setTimeout(() => window.close(), 1500);
            </script>
            </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"""
            <html><body>
            <h2>Connection failed</h2>
            <p>{str(e)}</p>
            <p>Please close this window and try again.</p>
            </body></html>
        """)


@router.post("/etsy/disconnect")
async def disconnect_etsy():
    """Remove stored Etsy tokens."""
    await db.delete_etsy_tokens()
    return {"ok": True}


@router.post("/etsy/sync")
async def sync_etsy_analytics():
    """
    Fetch views/favorites from Etsy for all Printify products.
    Saves lifetime totals as today's snapshot.
    """
    access_token, _shop_id = await ensure_etsy_token()

    # Get Printify products to find Etsy listing IDs
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Printify products: {e}")

    today = time.strftime("%Y-%m-%d")
    synced = []

    for product in products:
        external = product.get("external")
        if not external or not external.get("id"):
            continue

        etsy_listing_id = external["id"]
        printify_product_id = product["id"]

        try:
            listing = await etsy.get_listing(access_token, etsy_listing_id)
            views = listing.get("views", 0) or 0
            favorites = listing.get("num_favorers", 0) or 0

            await db.save_analytics(
                printify_product_id=printify_product_id,
                date=today,
                views=views,
                favorites=favorites,
                notes="etsy_sync",
            )

            synced.append({
                "printify_product_id": printify_product_id,
                "etsy_listing_id": etsy_listing_id,
                "title": product.get("title", ""),
                "views": views,
                "favorites": favorites,
            })
        except Exception as e:
            synced.append({
                "printify_product_id": printify_product_id,
                "etsy_listing_id": etsy_listing_id,
                "error": str(e),
            })

    return {"synced": len(synced), "products": synced, "date": today}


@router.post("/etsy/sync-orders")
async def sync_etsy_orders():
    """Fetch orders/revenue from Etsy receipts and store in analytics."""
    access_token, shop_id = await ensure_etsy_token()

    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        # Build listing_id -> printify_product_id map
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])
        listing_to_product = {}
        for p in products:
            external = p.get("external")
            if external and external.get("id"):
                listing_to_product[str(external["id"])] = p["id"]

        # Fetch receipts from Etsy
        receipts = await etsy.get_shop_receipts(access_token, shop_id)

        # Aggregate orders + revenue by product
        product_orders: dict = {}
        for receipt in receipts:
            for transaction in receipt.get("transactions", []):
                listing_id = str(transaction.get("listing_id", ""))
                printify_id = listing_to_product.get(listing_id)
                if not printify_id:
                    continue

                if printify_id not in product_orders:
                    product_orders[printify_id] = {"orders": 0, "revenue_cents": 0}

                product_orders[printify_id]["orders"] += transaction.get("quantity", 1)
                price = transaction.get("price", {})
                amount = price.get("amount", 0) or 0
                divisor = price.get("divisor", 100) or 100
                product_orders[printify_id]["revenue_cents"] += int(amount / divisor * 100)

        # Save to analytics
        today = time.strftime("%Y-%m-%d")
        synced = []
        for printify_id, data in product_orders.items():
            existing = await db.get_product_analytics_for_date(printify_id, today)
            await db.save_analytics(
                printify_product_id=printify_id,
                date=today,
                views=existing.get("views", 0) if existing else 0,
                favorites=existing.get("favorites", 0) if existing else 0,
                orders=data["orders"],
                revenue_cents=data["revenue_cents"],
                notes="etsy_order_sync",
            )
            synced.append({"printify_product_id": printify_id, **data})

        return {"synced": len(synced), "products": synced, "date": today}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === PRODUCT MANAGER ===


@router.get("/products/manager")
async def get_product_manager_data():
    """Get all products with Printify, analytics, and Etsy data merged."""
    try:
        # Analytics from DB
        analytics = await db.get_analytics_summary()
        analytics_map = {a["printify_product_id"]: a for a in analytics}

        # Printify products
        products = []
        if printify.is_configured:
            page = 1
            while True:
                result = await printify.list_products(page=page, limit=50)
                data = result.get("data", [])
                products.extend(data)
                total = result.get("total", 0)
                if page * 50 >= total or not data:
                    break
                page += 1

        # Etsy listing data (for SEO scoring on frontend)
        etsy_listings_map = {}
        try:
            tokens = await db.get_etsy_tokens()
            if tokens and tokens.get("shop_id"):
                access_token = tokens["access_token"]
                if tokens["expires_at"] < int(time.time()):
                    new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
                    await db.save_etsy_tokens(
                        access_token=new_tokens.access_token,
                        refresh_token=new_tokens.refresh_token,
                        expires_at=new_tokens.expires_at,
                    )
                    access_token = new_tokens.access_token

                etsy_listings = await etsy.get_all_listings(access_token, tokens["shop_id"])
                for listing in etsy_listings:
                    etsy_listings_map[str(listing["listing_id"])] = {
                        "title": listing.get("title", ""),
                        "tags": listing.get("tags", []),
                        "description": listing.get("description", ""),
                        "materials": listing.get("materials", []),
                        "views": listing.get("views", 0),
                        "num_favorers": listing.get("num_favorers", 0),
                    }
        except Exception:
            pass

        # Load custom mockup thumbnails from DB (preferred_mockup_url or first image_mockup)
        mockup_thumbs = {}
        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT p.printify_product_id,
                           COALESCE(
                               p.preferred_mockup_url,
                               (SELECT im.etsy_cdn_url
                                FROM image_mockups im
                                WHERE im.image_id = p.source_image_id
                                  AND im.etsy_cdn_url IS NOT NULL
                                ORDER BY im.rank LIMIT 1)
                           ) AS mockup_url
                    FROM products p
                    WHERE p.printify_product_id = ANY($1::text[])
                      AND p.archived IS NOT TRUE
                """, [p["id"] for p in products])
                for row in rows:
                    if row["mockup_url"]:
                        mockup_thumbs[row["printify_product_id"]] = row["mockup_url"]
        except Exception:
            pass

        # Merge
        merged = []
        for product in products:
            pid = product["id"]
            a = analytics_map.pop(pid, {})

            # Prefer custom mockup, fall back to Printify image
            thumbnail = mockup_thumbs.get(pid)
            if not thumbnail:
                for img in product.get("images", []):
                    if img.get("is_default"):
                        thumbnail = img.get("src")
                        break
                if not thumbnail and product.get("images"):
                    thumbnail = product["images"][0].get("src")

            enabled_variants = [v for v in product.get("variants", []) if v.get("is_enabled")]
            prices = [v.get("price", 0) for v in enabled_variants]
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0

            external = product.get("external")
            etsy_listing_id = None
            etsy_url = None
            if external and external.get("id"):
                etsy_listing_id = str(external["id"])
                handle = external.get("handle", "")
                etsy_url = handle if handle.startswith("http") else f"https://{handle}" if handle else None

            etsy_data = etsy_listings_map.get(etsy_listing_id, {}) if etsy_listing_id else {}
            status = "on_etsy" if etsy_listing_id else "draft"

            merged.append({
                "printify_product_id": pid,
                "title": product.get("title", "Untitled"),
                "thumbnail": thumbnail,
                "status": status,
                "min_price": min_price,
                "max_price": max_price,
                "etsy_url": etsy_url,
                "etsy_listing_id": etsy_listing_id,
                "total_views": a.get("total_views", 0),
                "total_favorites": a.get("total_favorites", 0),
                "total_orders": a.get("total_orders", 0),
                "total_revenue_cents": a.get("total_revenue_cents", 0),
                "etsy_title": etsy_data.get("title", ""),
                "etsy_tags": etsy_data.get("tags", []),
                "etsy_description": etsy_data.get("description", ""),
                "etsy_materials": etsy_data.get("materials", []),
            })

        return {"products": merged}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === ETSY LISTING MANAGEMENT ===


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
        print(f"[Etsy] Failed to fetch production partners: {e}")

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
                print(f"[Etsy] Failed to set primary color: {e}")
        if request.secondary_color and request.secondary_color in ETSY_COLOR_VALUES:
            try:
                await etsy.update_listing_property(
                    access_token, shop_id, listing_id,
                    ETSY_SECONDARY_COLOR_PROPERTY_ID,
                    [ETSY_COLOR_VALUES[request.secondary_color]],
                    [request.secondary_color],
                )
            except Exception as e:
                print(f"[Etsy] Failed to set secondary color: {e}")

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
                print(f"[Etsy alt_text] Failed for image {img['listing_image_id']}: {e}")
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
