"""EtsySyncService — batch-fetches Etsy stats and orders, stores in analytics."""

import logging
import time
from typing import Optional

import database as db
from etsy import EtsyAPI
from printify import PrintifyAPI

logger = logging.getLogger(__name__)


class EtsySyncService:
    """Pulls views, favorites, and orders from Etsy in batch.

    Used by both manual endpoints and the scheduler.
    """

    def __init__(self, etsy: EtsyAPI, printify: PrintifyAPI):
        self.etsy = etsy
        self.printify = printify

    async def _get_credentials(self) -> tuple[str, str]:
        """Get valid Etsy access_token and shop_id (auto-refreshes)."""
        tokens = await db.get_etsy_tokens()
        if not tokens:
            raise RuntimeError("Etsy not connected")

        access_token = tokens["access_token"]
        shop_id = tokens.get("shop_id", "")

        if tokens["expires_at"] < int(time.time()):
            new_tokens = await self.etsy.refresh_access_token(tokens["refresh_token"])
            await db.save_etsy_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
                shop_id=shop_id,
            )
            access_token = new_tokens.access_token

        if not shop_id:
            raise RuntimeError("No Etsy shop_id stored. Reconnect Etsy.")

        return access_token, shop_id

    async def _build_listing_map(self) -> dict[str, str]:
        """Map etsy_listing_id -> printify_product_id from Printify."""
        result = await self.printify.list_products(page=1, limit=50)
        products = result.get("data", [])
        mapping = {}
        for p in products:
            external = p.get("external")
            if external and external.get("id"):
                mapping[str(external["id"])] = p["id"]
        return mapping

    async def sync_views_favorites(self) -> dict:
        """Batch-fetch views/favorites for all listings via get_all_listings.

        Returns summary dict with synced count and per-product details.
        """
        access_token, shop_id = await self._get_credentials()
        listing_map = await self._build_listing_map()

        # Batch fetch all listings (views + num_favorers included)
        all_listings = await self.etsy.get_all_listings(access_token, shop_id)

        today = time.strftime("%Y-%m-%d")
        synced = []

        for listing in all_listings:
            listing_id = str(listing.get("listing_id", ""))
            printify_id = listing_map.get(listing_id)
            if not printify_id:
                continue

            views = listing.get("views", 0) or 0
            favorites = listing.get("num_favorers", 0) or 0

            try:
                # Preserve existing orders/revenue for today
                existing = await db.get_product_analytics_for_date(printify_id, today)
                await db.save_analytics(
                    printify_product_id=printify_id,
                    date=today,
                    views=views,
                    favorites=favorites,
                    orders=existing["orders"] if existing else 0,
                    revenue_cents=existing["revenue_cents"] if existing else 0,
                    notes="etsy_sync",
                )
                synced.append({
                    "printify_product_id": printify_id,
                    "etsy_listing_id": listing_id,
                    "views": views,
                    "favorites": favorites,
                })
            except Exception as e:
                logger.warning("sync views failed for %s: %s", listing_id, e)
                synced.append({
                    "printify_product_id": printify_id,
                    "etsy_listing_id": listing_id,
                    "error": str(e),
                })

        logger.info("Etsy sync complete: %d products synced", len(synced))
        return {"synced": len(synced), "products": synced, "date": today}

    async def sync_orders(self, min_created: Optional[int] = None) -> dict:
        """Fetch orders/revenue from Etsy receipts and store in analytics.

        Args:
            min_created: Unix timestamp — only fetch receipts created after this.
                         Defaults to None (all receipts).
        """
        access_token, shop_id = await self._get_credentials()
        listing_map = await self._build_listing_map()

        receipts = await self.etsy.get_shop_receipts(
            access_token, shop_id, min_created=min_created,
        )

        # Aggregate orders + revenue by product
        product_orders: dict = {}
        for receipt in receipts:
            for txn in receipt.get("transactions", []):
                listing_id = str(txn.get("listing_id", ""))
                printify_id = listing_map.get(listing_id)
                if not printify_id:
                    continue

                if printify_id not in product_orders:
                    product_orders[printify_id] = {"orders": 0, "revenue_cents": 0}

                product_orders[printify_id]["orders"] += txn.get("quantity", 1)
                price = txn.get("price", {})
                amount = price.get("amount", 0) or 0
                divisor = price.get("divisor", 100) or 100
                product_orders[printify_id]["revenue_cents"] += int(amount / divisor * 100)

        # Save to analytics — preserve existing views/favorites
        today = time.strftime("%Y-%m-%d")
        synced = []
        for printify_id, data in product_orders.items():
            existing = await db.get_product_analytics_for_date(printify_id, today)
            await db.save_analytics(
                printify_product_id=printify_id,
                date=today,
                views=existing["views"] if existing else 0,
                favorites=existing["favorites"] if existing else 0,
                orders=data["orders"],
                revenue_cents=data["revenue_cents"],
                notes="etsy_order_sync",
            )
            synced.append({"printify_product_id": printify_id, **data})

        logger.info("Etsy order sync complete: %d products", len(synced))
        return {"synced": len(synced), "products": synced, "date": today}

    async def full_sync(self) -> dict:
        """Run both views/favorites and orders sync."""
        views_result = await self.sync_views_favorites()
        orders_result = await self.sync_orders()
        return {
            "views": views_result,
            "orders": orders_result,
        }
