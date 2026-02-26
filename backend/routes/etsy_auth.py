import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
import httpx

from deps import etsy, printify
import database as db

router = APIRouter(tags=["etsy"])

logger = logging.getLogger(__name__)

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
            logger.warning(f"auto-fetch shop_id failed: {e}")

    if not shop_id:
        raise HTTPException(status_code=400, detail="No Etsy shop_id stored. Reconnect Etsy.")

    return access_token, shop_id


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
            logger.debug(f" get_me response: {user_info}")
            etsy_user_id = str(user_info.get("user_id", ""))
            shop_id = str(user_info.get("shop_id", ""))
        except Exception as e:
            logger.debug(f" get_me failed: {e}")
            # Fallback: parse user_id from token (format: "{user_id}.{rest}")
            token_parts = tokens.access_token.split(".")
            if token_parts:
                etsy_user_id = token_parts[0]
            logger.debug(f" parsed user_id from token: {etsy_user_id}")

        # If shop_id still missing, use authenticated shops endpoint
        if not shop_id and etsy_user_id:
            try:
                shops_data = await etsy.get_user_shops(tokens.access_token, etsy_user_id)
                logger.debug(f" get_user_shops response: {shops_data}")
                if shops_data.get("shop_id"):
                    shop_id = str(shops_data["shop_id"])
            except Exception as e:
                logger.debug(f" get_user_shops failed: {e}")

        logger.info(f"OAuth callback: user_id={etsy_user_id}, shop_id={shop_id}")

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
    """Get all products from local DB with analytics and Etsy data merged."""
    try:
        pool = await db.get_pool()

        # All products from local DB
        async with pool.acquire() as conn:
            db_products = await conn.fetch("""
                SELECT p.*,
                       COALESCE(
                           p.preferred_mockup_url,
                           (SELECT im.etsy_cdn_url
                            FROM image_mockups im
                            WHERE im.image_id = p.source_image_id
                              AND im.etsy_cdn_url IS NOT NULL
                            ORDER BY im.rank LIMIT 1)
                       ) AS mockup_url
                FROM products p
                ORDER BY p.created_at DESC
            """)

        # Analytics from DB
        analytics = await db.get_analytics_summary()
        analytics_map = {a["printify_product_id"]: a for a in analytics}

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

        # Merge
        merged = []
        for product in db_products:
            pid = product["printify_product_id"]
            a = analytics_map.get(pid, {})

            thumbnail = product["mockup_url"] or product["image_url"]
            etsy_listing_id = product["etsy_listing_id"]
            status = "on_etsy" if etsy_listing_id else "draft"

            etsy_data = etsy_listings_map.get(etsy_listing_id, {}) if etsy_listing_id else {}

            merged.append({
                "printify_product_id": pid,
                "title": product["title"] or "Untitled",
                "thumbnail": thumbnail,
                "status": status,
                "min_price": 0,
                "max_price": 0,
                "etsy_url": None,
                "etsy_listing_id": etsy_listing_id,
                "total_views": a.get("total_views", 0),
                "total_favorites": a.get("total_favorites", 0),
                "total_orders": a.get("total_orders", 0),
                "total_revenue_cents": a.get("total_revenue_cents", 0),
                "etsy_title": etsy_data.get("title", ""),
                "etsy_tags": etsy_data.get("tags", []),
                "etsy_description": etsy_data.get("description", ""),
                "etsy_materials": etsy_data.get("materials", []),
                "created_at": str(product["created_at"] or ""),
            })

        return {"products": merged}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
