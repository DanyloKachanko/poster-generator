"""
Scheduled publishing for Etsy via Printify.

Publishes products at configurable EST times to maximize
Etsy's recency boost. Settings are stored in DB and reload every cycle.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import List, Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from notifications import NotificationService
from printify import PrintifyAPI

logger = logging.getLogger(__name__)

# EST = UTC-5
EST = timezone(timedelta(hours=-5))

_DEFAULT_TIMES = [dt_time(10, 0), dt_time(14, 0), dt_time(18, 0)]


class PublishScheduler:
    CHECK_INTERVAL_MINUTES = 5

    def __init__(self, printify: PrintifyAPI, notifier: NotificationService, etsy=None, listing_gen=None, etsy_sync=None):
        self.printify = printify
        self.notifier = notifier
        self.etsy = etsy
        self.listing_gen = listing_gen
        self.etsy_sync = etsy_sync
        self.scheduler = AsyncIOScheduler()
        # Cached settings — reloaded every check cycle
        self._publish_times: List[dt_time] = list(_DEFAULT_TIMES)
        self._enabled: bool = True
        self._preferred_primary_camera: str = ""
        self._default_shipping_profile_id: Optional[int] = None
        self._default_shop_section_id: Optional[int] = None

    async def _load_settings(self):
        """Load publish times from DB. Falls back to defaults."""
        try:
            settings = await db.get_schedule_settings()
            times = []
            for t_str in settings.get("publish_times", []):
                parts = t_str.split(":")
                times.append(dt_time(int(parts[0]), int(parts[1])))
            if times:
                self._publish_times = sorted(times)
            self._enabled = bool(settings.get("enabled", 1))
            self._preferred_primary_camera = settings.get("preferred_primary_camera", "")
            self._default_shipping_profile_id = settings.get("default_shipping_profile_id")
            self._default_shop_section_id = settings.get("default_shop_section_id")
        except Exception as e:
            logger.warning("Failed to load schedule settings: %s", e)

    async def reload_settings(self):
        """Public method to immediately reload settings (called after API update)."""
        await self._load_settings()
        logger.info(
            "Schedule settings reloaded: times=%s, enabled=%s, primary_camera=%s",
            [t.strftime("%H:%M") for t in self._publish_times],
            self._enabled,
            self._preferred_primary_camera or "(none)",
        )

    async def start(self):
        """Start the background publish checker and daily summary."""
        await self._load_settings()
        self.scheduler.add_job(
            self._check_and_publish,
            "interval",
            minutes=self.CHECK_INTERVAL_MINUTES,
            id="publish_checker",
            replace_existing=True,
        )
        # Daily summary at 9:00 EST
        self.scheduler.add_job(
            self._send_daily_summary,
            "cron",
            hour=14,  # 14:00 UTC = 9:00 EST
            minute=0,
            id="daily_summary",
            replace_existing=True,
        )
        # Description guardian — twice daily (6:00 and 18:00 UTC)
        self.scheduler.add_job(
            self._guard_descriptions,
            "cron",
            hour="6,18",
            minute=0,
            id="description_guardian",
            replace_existing=True,
        )
        # Mockup catch-up — fill missing etsy_listing_ids and apply mockups
        self.scheduler.add_job(
            self._catchup_mockups,
            "interval",
            minutes=5,
            id="mockup_catchup",
            replace_existing=True,
        )
        # Auto SEO refresh — weekly on Mondays at 11:00 UTC (6:00 EST)
        self.scheduler.add_job(
            self._auto_seo_refresh,
            "cron",
            day_of_week="mon",
            hour=11,
            minute=0,
            id="auto_seo_refresh",
            replace_existing=True,
        )
        # Etsy analytics auto-sync — every 6 hours
        self.scheduler.add_job(
            self._auto_etsy_sync,
            "interval",
            hours=6,
            id="etsy_auto_sync",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(
            "Publish scheduler started (checking every %d min, slots: %s EST)",
            self.CHECK_INTERVAL_MINUTES,
            ", ".join(t.strftime("%H:%M") for t in self._publish_times),
        )

    async def stop(self):
        """Shutdown scheduler gracefully."""
        self.scheduler.shutdown(wait=False)
        logger.info("Publish scheduler stopped")

    # ------------------------------------------------------------------
    # Slot calculation
    # ------------------------------------------------------------------

    async def _calculate_next_slot(self) -> datetime:
        """Find the next available EST publish slot.

        Uses whichever is later: the last scheduled time or now.
        This prevents scheduling into the past after a gap.
        """
        last_time_str = await db.get_last_scheduled_time()
        now_utc = datetime.now(timezone.utc)

        if last_time_str:
            last_time = datetime.fromisoformat(last_time_str)
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            reference = max(last_time, now_utc)
            return self._next_slot_after(reference)
        else:
            return self._next_slot_after(now_utc)

    def _next_slot_after(self, after_utc: datetime) -> datetime:
        """Return the next EST publish slot strictly after `after_utc`."""
        after_est = after_utc.astimezone(EST)
        current_date = after_est.date()

        # Check remaining slots today
        for slot_time in self._publish_times:
            candidate_est = datetime.combine(current_date, slot_time, tzinfo=EST)
            if candidate_est > after_est:
                return candidate_est.astimezone(timezone.utc)

        # All today's slots passed -> first slot tomorrow
        next_date = current_date + timedelta(days=1)
        first_slot = datetime.combine(
            next_date, self._publish_times[0], tzinfo=EST
        )
        return first_slot.astimezone(timezone.utc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def _get_product_image(self, printify_product_id: str) -> Optional[str]:
        """Fetch the default mockup image URL from Printify."""
        try:
            product = await self.printify.get_product(printify_product_id)
            images = product.get("images", [])
            if images:
                return images[0].get("src")
        except Exception as e:
            logger.warning("Failed to fetch product image for %s: %s", printify_product_id, e)
        return None

    async def add_to_queue(
        self, printify_product_id: str, title: str,
        image_url: Optional[str] = None, etsy_metadata: Optional[dict] = None,
    ) -> dict:
        """Add product to schedule with auto-calculated slot."""
        await self._load_settings()
        next_slot = await self._calculate_next_slot()
        if not image_url:
            image_url = await self._get_product_image(printify_product_id)
        result = await db.add_to_schedule(
            printify_product_id=printify_product_id,
            title=title,
            scheduled_publish_at=next_slot.isoformat(),
            image_url=image_url,
            etsy_metadata=etsy_metadata,
        )
        slot_est = next_slot.astimezone(EST)
        logger.info(
            "Queued %s (%s) for %s EST",
            printify_product_id,
            title[:40],
            slot_est.strftime("%Y-%m-%d %H:%M"),
        )
        await self.notifier.notify_queued(title, next_slot.isoformat(), image_url=image_url)
        return result

    async def publish_now(self, printify_product_id: str) -> dict:
        """Immediately publish a product, bypassing the schedule."""
        # Get info before publishing (status changes after)
        queue = await db.get_schedule_queue()
        item_info = next(
            (item for item in queue if item["printify_product_id"] == printify_product_id),
            None,
        )
        title = item_info["title"] if item_info else printify_product_id
        image_url = item_info.get("image_url") if item_info else None
        etsy_metadata = item_info.get("etsy_metadata", {}) if item_info else {}

        # Skip Printify images if custom mockups are ready
        mockups_ready = await self._check_mockups_ready(printify_product_id)
        sync_images = not mockups_ready
        if not sync_images:
            logger.info("Mockups ready for %s — publishing without Printify images", printify_product_id)

        await self.printify.publish_product(printify_product_id, sync_images=sync_images)
        await db.update_schedule_status(printify_product_id, "published")
        logger.info("Immediately published %s", printify_product_id)
        stats = await db.get_schedule_stats()
        await self.notifier.notify_published(
            title, stats["pending"], stats["next_publish_at"], image_url=image_url
        )

        # Post-publish: fill Etsy metadata + set primary image in background
        asyncio.create_task(self._post_publish_etsy_setup(printify_product_id, etsy_metadata, sync_images=sync_images))

        return {"printify_product_id": printify_product_id, "status": "published"}

    # ------------------------------------------------------------------
    # Background jobs
    # ------------------------------------------------------------------

    async def _check_and_publish(self):
        """Called every CHECK_INTERVAL_MINUTES — publish all due items."""
        await self._load_settings()
        if not self._enabled:
            return

        due_items = await db.get_pending_due()
        if not due_items:
            return

        logger.info("Found %d due items to publish", len(due_items))
        for item in due_items:
            pid = item["printify_product_id"]
            try:
                # Skip Printify images if custom mockups are ready
                mockups_ready = await self._check_mockups_ready(pid)
                sync_images = not mockups_ready
                if not sync_images:
                    logger.info("Mockups ready for %s — publishing without Printify images", pid)

                await self.printify.publish_product(pid, sync_images=sync_images)
                await db.update_schedule_status(pid, "published")
                logger.info("Published %s (%s)", pid, item["title"][:40])
                stats = await db.get_schedule_stats()
                await self.notifier.notify_published(
                    item["title"], stats["pending"], stats["next_publish_at"],
                    image_url=item.get("image_url"),
                )
                # Post-publish: fill Etsy metadata + set primary image
                etsy_metadata = item.get("etsy_metadata", {})
                asyncio.create_task(self._post_publish_etsy_setup(pid, etsy_metadata, sync_images=sync_images))
            except Exception as e:
                await db.update_schedule_status(pid, "failed", str(e))
                await db.update_product_status(pid, "failed")
                logger.error("Failed to publish %s: %s", pid, e)
                await self.notifier.notify_publish_failed(item["title"], str(e))

    async def _send_daily_summary(self):
        """Send morning digest via Telegram."""
        try:
            stats = await db.get_daily_summary_stats()
            await self.notifier.notify_daily_summary(stats)
        except Exception as e:
            logger.warning("Failed to send daily summary: %s", e)

    # ------------------------------------------------------------------
    # Post-publish: fill Etsy metadata + set preferred primary image
    # ------------------------------------------------------------------

    async def _get_etsy_token(self) -> Optional[tuple]:
        """Get a valid Etsy access token for background use. Returns (access_token, shop_id) or None."""
        try:
            tokens = await db.get_etsy_tokens()
            if not tokens:
                return None

            access_token = tokens["access_token"]
            shop_id = tokens.get("shop_id", "")
            if not shop_id:
                return None

            if tokens["expires_at"] < int(time.time()):
                if not self.etsy:
                    return None
                new_tokens = await self.etsy.refresh_access_token(tokens["refresh_token"])
                await db.save_etsy_tokens(
                    access_token=new_tokens.access_token,
                    refresh_token=new_tokens.refresh_token,
                    expires_at=new_tokens.expires_at,
                )
                access_token = new_tokens.access_token

            return access_token, shop_id
        except Exception as e:
            logger.warning("Failed to get Etsy token: %s", e)
            return None

    async def _check_mockups_ready(self, printify_product_id: str) -> bool:
        """Return True if product has approved, included mockups ready for Etsy."""
        try:
            product = await db.get_product_by_printify_id(printify_product_id)
            if not product:
                return False
            source_image_id = product.get("source_image_id")
            if not source_image_id:
                return False
            # mockup_status lives on generated_images, not products
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT mockup_status FROM generated_images WHERE id = $1",
                    source_image_id,
                )
            if not row or row["mockup_status"] != "approved":
                return False
            mockups = await db.get_image_mockups(source_image_id)
            included = [m for m in mockups if m.get("is_included", True)]
            return len(included) > 0
        except Exception as e:
            logger.debug("Mockup readiness check failed for %s: %s", printify_product_id, e)
            return False

    async def _post_publish_etsy_setup(self, printify_product_id: str, etsy_metadata: dict = None, sync_images: bool = True):
        """After publishing, fill Etsy listing metadata and set preferred primary image.

        Runs as a background task — polls until the Etsy listing appears,
        then updates metadata and optionally uploads the preferred mockup.
        When sync_images=False, Printify didn't send images — skip delete step.
        """
        if not self.etsy:
            return

        metadata = etsy_metadata or {}
        camera = self._preferred_primary_camera
        has_metadata = bool(metadata)
        has_camera = bool(camera)

        # Check if product has a source image (for mockup composition)
        has_source_image = False
        try:
            local = await db.get_product_by_printify_id(printify_product_id)
            if local and local.get("source_image_id"):
                has_source_image = True
        except Exception:
            pass

        if not has_metadata and not has_camera and not has_source_image:
            return

        logger.info("Post-publish setup for %s (metadata=%s, camera=%s, source_image=%s)...",
                     printify_product_id, has_metadata, camera or "none",
                     has_source_image)

        # Poll for Etsy listing ID to appear (Printify publishes async)
        etsy_listing_id = None
        product = None
        for attempt in range(20):  # ~5 min total
            await asyncio.sleep(15)
            try:
                product = await self.printify.get_product(printify_product_id)
                external = product.get("external") or {}
                if external.get("id"):
                    etsy_listing_id = str(external["id"])
                    break
            except Exception as e:
                logger.debug("Poll attempt %d for %s: %s", attempt + 1, printify_product_id, e)

        if not etsy_listing_id or not product:
            logger.warning("Etsy listing not found for %s after polling", printify_product_id)
            await db.update_product_status(printify_product_id, "published")
            return

        # Update product tracking with Etsy listing ID
        await db.update_product_status(printify_product_id, "published", etsy_listing_id)

        # Get Etsy token
        token_data = await self._get_etsy_token()
        if not token_data:
            logger.warning("No Etsy token for post-publish setup (product %s)", printify_product_id)
            return
        access_token, shop_id = token_data

        # --- Step 1: Fill Etsy metadata ---
        if has_metadata:
            try:
                update_data = {}
                if metadata.get("materials"):
                    update_data["materials"] = metadata["materials"]
                if metadata.get("who_made"):
                    update_data["who_made"] = metadata["who_made"]
                if metadata.get("when_made"):
                    update_data["when_made"] = metadata["when_made"]
                if "is_supply" in metadata:
                    update_data["is_supply"] = metadata["is_supply"]
                # Add defaults from schedule settings
                ship_id = self._default_shipping_profile_id
                if ship_id:
                    update_data["shipping_profile_id"] = ship_id
                section_id = self._default_shop_section_id
                if section_id:
                    update_data["shop_section_id"] = section_id

                if update_data:
                    await self.etsy.update_listing(access_token, shop_id, etsy_listing_id, update_data)
                    logger.info("Filled Etsy metadata for %s (etsy=%s): %s",
                                printify_product_id, etsy_listing_id, list(update_data.keys()))
            except Exception as e:
                logger.error("Failed to fill Etsy metadata for %s: %s", printify_product_id, e)

        # --- Step 2: Fix description on Etsy (overwrite Printify's sync) ---
        local_product = await db.get_product_by_printify_id(printify_product_id)
        local_desc = (local_product or {}).get("description")
        if local_desc:
            try:
                await asyncio.sleep(5)  # Let Printify finish its initial sync
                await self.etsy.update_listing(
                    access_token, shop_id, etsy_listing_id,
                    {"description": local_desc},
                )
                logger.info("Fixed Etsy description for %s (etsy=%s)",
                            printify_product_id, etsy_listing_id)
            except Exception as e:
                logger.error("Failed to fix Etsy description for %s: %s", printify_product_id, e)

        # --- Step 3: Upload multi-mockup images ---
        source_image_id = (local_product or {}).get("source_image_id")

        # Fallback: if no source_image_id, try to get poster URL from Printify
        poster_url = None
        row = None
        if source_image_id:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT url, mockup_status FROM generated_images WHERE id = $1",
                    source_image_id,
                )
            if row:
                poster_url = row["url"]
        if not poster_url and product:
            # Extract uploaded image from Printify print_areas
            for pa in product.get("print_areas", []):
                for ph in pa.get("placeholders", []):
                    imgs = ph.get("images", [])
                    if imgs:
                        poster_url = imgs[0].get("src")
                        break
                if poster_url:
                    break

        if poster_url:
            try:
                import base64 as b64_mod

                # Check for pre-composed image_mockups (only if approved)
                included = []
                if source_image_id and row and row["mockup_status"] == "approved":
                    mockups = await db.get_image_mockups(source_image_id)
                    included = [m for m in mockups if m.get("is_included", True)]

                if included:
                    # Use existing pre-composed mockups
                    mockup_entries = []
                    for m in included:
                        data_url = m["mockup_data"]
                        if data_url.startswith("data:image"):
                            mockup_bytes = b64_mod.b64decode(data_url.split(",", 1)[1])
                        else:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(data_url, timeout=30.0, follow_redirects=True)
                                resp.raise_for_status()
                                mockup_bytes = resp.content
                        mockup_entries.append((m["id"], mockup_bytes))

                    from routes.mockup_utils import _upload_multi_images_to_etsy
                    upload_results = await _upload_multi_images_to_etsy(
                        access_token, shop_id, etsy_listing_id,
                        poster_url, mockup_entries,
                        has_existing_images=sync_images,
                    )
                    for ur in upload_results:
                        if ur.get("mockup_db_id") and ur.get("etsy_image_id"):
                            await db.update_image_mockup_etsy_info(
                                ur["mockup_db_id"], ur["etsy_image_id"], ur.get("etsy_cdn_url", "")
                            )
                    for ur in upload_results:
                        if ur.get("etsy_cdn_url") and ur["type"] == "mockup":
                            await db.set_product_preferred_mockup(printify_product_id, ur["etsy_cdn_url"])
                            break
                    logger.info("Uploaded %d images for %s (etsy=%s) from pre-composed mockups",
                                len(upload_results), printify_product_id, etsy_listing_id)
                else:
                    # Compose on-the-fly — prefer default pack
                    default_pack_str = await db.get_setting("default_pack_id")
                    if default_pack_str:
                        compose_pack_id = int(default_pack_str)
                        active_templates = await db.get_pack_templates(compose_pack_id)
                    elif source_image_id:
                        compose_pack_id = await db.get_image_mockup_pack_id(source_image_id)
                        if compose_pack_id:
                            active_templates = await db.get_pack_templates(compose_pack_id)
                        else:
                            active_templates = await db.get_active_mockup_templates()
                            compose_pack_id = None
                    else:
                        active_templates = await db.get_active_mockup_templates()
                        compose_pack_id = None

                    if active_templates:
                        import json as json_mod
                        for t in active_templates:
                            if isinstance(t.get("corners"), str):
                                t["corners"] = json_mod.loads(t["corners"])

                        from routes.mockup_utils import _compose_all_templates, _upload_multi_images_to_etsy
                        composed = await _compose_all_templates(poster_url, active_templates)

                        mockup_entries = []
                        for rank_idx, (tid, png_bytes) in enumerate(composed, start=2):
                            if source_image_id:
                                b64_str = b64_mod.b64encode(png_bytes).decode()
                                saved = await db.save_image_mockup(
                                    image_id=source_image_id,
                                    template_id=tid,
                                    mockup_data=f"data:image/png;base64,{b64_str}",
                                    rank=rank_idx,
                                    pack_id=compose_pack_id,
                                )
                                mockup_entries.append((saved["id"], png_bytes))
                            else:
                                # No source image in DB — upload without saving mockup record
                                mockup_entries.append((None, png_bytes))

                        upload_results = await _upload_multi_images_to_etsy(
                            access_token, shop_id, etsy_listing_id,
                            poster_url, mockup_entries,
                            has_existing_images=sync_images,
                        )
                        for ur in upload_results:
                            if ur.get("mockup_db_id") and ur.get("etsy_image_id"):
                                await db.update_image_mockup_etsy_info(
                                    ur["mockup_db_id"], ur["etsy_image_id"], ur.get("etsy_cdn_url", "")
                                )
                        for ur in upload_results:
                            if ur.get("etsy_cdn_url") and ur["type"] == "mockup":
                                await db.set_product_preferred_mockup(printify_product_id, ur["etsy_cdn_url"])
                                break
                        logger.info("Composed + uploaded %d images for %s (etsy=%s) via pack=%s (source_image=%s)",
                                    len(upload_results), printify_product_id, etsy_listing_id,
                                    compose_pack_id, source_image_id or "printify-fallback")
                    else:
                        logger.info("No active templates for %s, skipping mockup upload",
                                    printify_product_id)
            except Exception as e:
                logger.error("Failed to upload mockup images for %s: %s", printify_product_id, e)
        else:
            logger.info("No poster URL found for %s, skipping mockup upload", printify_product_id)

        # --- Step 4: Auto-publish to DovShop ---
        try:
            from deps import dovshop_client
            if dovshop_client.is_configured:
                from dovshop_ai import enrich_product

                # Gather product info
                tags = []
                raw_tags = (local_product or {}).get("tags") or []
                if isinstance(raw_tags, str):
                    import json as json_mod2
                    try:
                        tags = json_mod2.loads(raw_tags)
                    except Exception:
                        tags = []
                else:
                    tags = list(raw_tags)

                # Get style from generations
                gen_style = None
                sid = (local_product or {}).get("source_image_id")
                if sid:
                    pool = await db.get_pool()
                    async with pool.acquire() as conn:
                        style_row = await conn.fetchrow(
                            """SELECT g.style FROM generated_images gi
                               JOIN generations g ON g.generation_id = gi.generation_id
                               WHERE gi.id = $1""", sid
                        )
                    if style_row:
                        gen_style = style_row["style"]

                # Get existing DovShop context
                collections = await dovshop_client.get_collections()
                try:
                    categories = await dovshop_client.get_categories()
                except Exception:
                    categories = []

                title = (local_product or {}).get("title", "")
                desc = (local_product or {}).get("description", "")
                img_url = (local_product or {}).get("image_url", "")

                # AI enrichment
                enrichment = await enrich_product(
                    title=title, tags=tags, style=gen_style,
                    description=desc, image_url=img_url,
                    existing_collections=collections,
                    existing_categories=categories,
                )

                coll_name = enrichment.get("collection_name")

                # Build images list
                push_images = []
                preferred = (local_product or {}).get("preferred_mockup_url")
                if preferred:
                    push_images.append(preferred)
                if img_url and img_url not in push_images:
                    push_images.append(img_url)

                etsy_url_ds = f"https://www.etsy.com/listing/{etsy_listing_id}" if etsy_listing_id else ""

                # Push to DovShop
                dovshop_result = await dovshop_client.push_product(
                    name=title,
                    images=push_images,
                    etsy_url=etsy_url_ds,
                    featured=enrichment.get("featured", False),
                    description=enrichment.get("seo_description", desc),
                    tags=tags,
                    external_id=printify_product_id,
                    preferred_mockup_url=preferred or "",
                )

                dovshop_id = dovshop_result.get("id") or dovshop_result.get("_id", "")
                if dovshop_id:
                    await db.set_product_dovshop_id(printify_product_id, str(dovshop_id))

                # Telegram notification
                await self.notifier.notify_dovshop_published(
                    title=title,
                    collection=coll_name,
                    categories=enrichment.get("categories"),
                    image_url=img_url,
                )

                logger.info("Auto-published %s to DovShop (id=%s, categories=%s)",
                            printify_product_id, dovshop_id,
                            enrichment.get("categories"))
        except Exception as e:
            logger.error("Failed to auto-publish %s to DovShop: %s", printify_product_id, e)

    # ------------------------------------------------------------------
    # Mockup catch-up — fill missing etsy_listing_ids + apply mockups
    # ------------------------------------------------------------------

    async def _catchup_mockups(self):
        """Periodic check: find published products missing etsy_listing_id or mockups.

        Three passes:
        0. Auto-import orphan scheduled_products (published but not in products table)
        1. Fill missing etsy_listing_ids from Printify
        2. Compose + upload mockups for products that have etsy_listing_id but no mockups on Etsy
        """
        import base64 as b64_mod
        import json as json_mod

        pool = await db.get_pool()

        # --- Pass 0: auto-import orphan scheduled_products ---
        async with pool.acquire() as conn:
            orphans = await conn.fetch(
                """
                SELECT sp.printify_product_id, sp.title
                FROM scheduled_products sp
                WHERE sp.status = 'published'
                  AND NOT EXISTS (
                      SELECT 1 FROM products p WHERE p.printify_product_id = sp.printify_product_id
                  )
                """
            )
        for orphan in orphans:
            pid = orphan["printify_product_id"]
            try:
                from routes.products import _import_printify_product
                p = await self.printify.get_product(pid)
                await _import_printify_product(p)
                logger.info("[catchup] Auto-imported orphan product %s (%s)", pid, orphan["title"][:40])
            except Exception as e:
                logger.warning("[catchup] Failed to import orphan %s: %s", pid, e)

        # --- Pass 1: fill missing etsy_listing_ids ---
        async with pool.acquire() as conn:
            missing_etsy = await conn.fetch(
                """
                SELECT p.id, p.printify_product_id
                FROM products p
                JOIN scheduled_products sp ON sp.printify_product_id = p.printify_product_id
                WHERE sp.status = 'published'
                  AND (p.etsy_listing_id IS NULL OR p.etsy_listing_id = '')
                """
            )

        for row in missing_etsy:
            pid = row["printify_product_id"]
            try:
                product = await self.printify.get_product(pid)
                external = product.get("external") or {}
                etsy_listing_id = str(external["id"]) if external.get("id") else None
                if not etsy_listing_id:
                    continue
                await db.update_product_status(pid, "published", etsy_listing_id)
                logger.info("[catchup] Filled etsy_listing_id=%s for %s", etsy_listing_id, pid)
            except Exception as e:
                logger.warning("[catchup] Failed to get etsy_id for %s: %s", pid, e)

        # --- Pass 2: compose + upload mockups for products missing them on Etsy ---
        async with pool.acquire() as conn:
            needs_mockups = await conn.fetch(
                """
                SELECT p.id, p.printify_product_id, p.etsy_listing_id,
                       p.source_image_id, gi.url as poster_url
                FROM products p
                JOIN generated_images gi ON gi.id = p.source_image_id
                WHERE p.etsy_listing_id IS NOT NULL AND p.etsy_listing_id != ''
                  AND NOT EXISTS (
                      SELECT 1 FROM image_mockups im
                      WHERE im.image_id = gi.id AND im.etsy_image_id IS NOT NULL
                  )
                """
            )

        if not needs_mockups:
            return

        logger.info("[catchup] Found %d products needing mockup upload", len(needs_mockups))

        # Get default pack templates
        default_pack_str = await db.get_setting("default_pack_id")
        if not default_pack_str:
            logger.warning("[catchup] No default pack configured, skipping")
            return
        pack_id = int(default_pack_str)
        templates = await db.get_pack_templates(pack_id)
        if not templates:
            logger.warning("[catchup] Default pack %d has no templates", pack_id)
            return
        for t in templates:
            if isinstance(t.get("corners"), str):
                t["corners"] = json_mod.loads(t["corners"])

        pack = await db.get_mockup_pack(pack_id)
        color_grade = pack.get("color_grade", "none") if pack else "none"

        # Get Etsy token
        token_data = await self._get_etsy_token()
        if not token_data:
            logger.warning("[catchup] No Etsy token, skipping mockup upload")
            return
        access_token, shop_id = token_data

        from routes.mockup_utils import _compose_all_templates, _upload_multi_images_to_etsy

        for row in needs_mockups:
            pid = row["printify_product_id"]
            try:
                source_image_id = row["source_image_id"]
                etsy_listing_id = row["etsy_listing_id"]

                # Check if mockups already composed in DB
                existing = await db.get_image_mockups(source_image_id)
                included = [m for m in existing if m.get("is_included", True)]

                if included:
                    # Mockups exist — just upload
                    mockup_entries = []
                    for m in included:
                        data_url = m["mockup_data"]
                        if data_url.startswith("data:image"):
                            mockup_bytes = b64_mod.b64decode(data_url.split(",", 1)[1])
                        else:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(data_url, timeout=30.0, follow_redirects=True)
                                resp.raise_for_status()
                                mockup_bytes = resp.content
                        mockup_entries.append((m["id"], mockup_bytes))
                else:
                    # Compose from scratch
                    composed = await _compose_all_templates(
                        row["poster_url"], templates, "fill", color_grade
                    )
                    mockup_entries = []
                    for rank_idx, (tid, png_bytes) in enumerate(composed, start=2):
                        b64_str = b64_mod.b64encode(png_bytes).decode()
                        saved = await db.save_image_mockup(
                            image_id=source_image_id,
                            template_id=tid,
                            mockup_data=f"data:image/png;base64,{b64_str}",
                            rank=rank_idx,
                            pack_id=pack_id,
                        )
                        mockup_entries.append((saved["id"], png_bytes))

                upload_results = await _upload_multi_images_to_etsy(
                    access_token, shop_id, etsy_listing_id,
                    row["poster_url"], mockup_entries,
                )
                for ur in upload_results:
                    if ur.get("mockup_db_id") and ur.get("etsy_image_id"):
                        await db.update_image_mockup_etsy_info(
                            ur["mockup_db_id"], ur["etsy_image_id"], ur.get("etsy_cdn_url", "")
                        )
                for ur in upload_results:
                    if ur.get("etsy_cdn_url") and ur["type"] == "mockup":
                        await db.set_product_preferred_mockup(pid, ur["etsy_cdn_url"])
                        break
                logger.info("[catchup] Mockups uploaded for %s (etsy=%s)", pid, etsy_listing_id)
            except Exception as e:
                logger.error("[catchup] Failed mockup upload for %s: %s", pid, e)

    # ------------------------------------------------------------------
    # Description guardian — verify Etsy descriptions match local DB
    # ------------------------------------------------------------------

    async def _guard_descriptions(self):
        """Check published products and re-apply descriptions if Printify overwrote them."""
        if not self.etsy:
            return

        token_data = await self._get_etsy_token()
        if not token_data:
            return
        access_token, shop_id = token_data

        products = await db.get_all_products(status="published", limit=50)
        items = products.get("items", [])
        if not items:
            return

        fixed = 0
        checked = 0
        for product in items:
            etsy_listing_id = product.get("etsy_listing_id")
            local_desc = product.get("description")
            if not etsy_listing_id or not local_desc:
                continue

            try:
                listing = await self.etsy.get_listing(access_token, etsy_listing_id)
                etsy_desc = listing.get("description", "")
                checked += 1

                # Compare stripped versions to avoid whitespace noise
                if etsy_desc.strip() != local_desc.strip():
                    await self.etsy.update_listing(
                        access_token, shop_id, etsy_listing_id,
                        {"description": local_desc},
                    )
                    fixed += 1
                    logger.info("Guardian fixed description for %s (etsy=%s)",
                                product["printify_product_id"], etsy_listing_id)

                await asyncio.sleep(0.5)  # Rate limit

            except Exception as e:
                logger.debug("Guardian skip %s: %s", product.get("printify_product_id"), e)

        if fixed > 0:
            logger.info("Description guardian: checked %d, fixed %d", checked, fixed)

    # ------------------------------------------------------------------
    # Auto SEO refresh — regenerate SEO for underperforming listings
    # ------------------------------------------------------------------

    async def _auto_seo_refresh(self, max_items: int = 5):
        """Weekly job: find listings with low views, regenerate SEO via Claude, update on Etsy."""
        if not self.etsy or not self.listing_gen:
            return

        token_data = await self._get_etsy_token()
        if not token_data:
            return
        access_token, shop_id = token_data

        candidates = await db.get_seo_refresh_candidates(
            min_days_since_publish=14,
            max_views=5,
            limit=max_items,
        )
        if not candidates:
            logger.info("Auto SEO refresh: no candidates found")
            return

        logger.info("Auto SEO refresh: %d candidates", len(candidates))
        refreshed = 0

        for product in candidates:
            pid = product["printify_product_id"]
            etsy_listing_id = product["etsy_listing_id"]

            try:
                # Fetch current Etsy listing
                listing = await self.etsy.get_listing(access_token, etsy_listing_id)
                old_title = listing.get("title", "")
                old_tags = listing.get("tags", [])
                old_desc = listing.get("description", "")

                # Regenerate SEO via Claude
                new_listing = await self.listing_gen.regenerate_seo_from_existing(
                    current_title=old_title,
                    current_tags=old_tags,
                    current_description=old_desc,
                )

                # Update on Etsy
                update_data = {
                    "title": new_listing.title,
                    "tags": new_listing.tags,
                    "description": new_listing.description,
                }
                await self.etsy.update_listing(access_token, shop_id, etsy_listing_id, update_data)

                # Also update local DB description
                pool = await db.get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE products SET description = $1, title = $2, tags = $3, updated_at = NOW() WHERE printify_product_id = $4",
                        new_listing.description, new_listing.title, new_listing.tags, pid,
                    )

                # Log the refresh
                await db.save_seo_refresh_log(
                    printify_product_id=pid,
                    etsy_listing_id=etsy_listing_id,
                    reason="low_views",
                    old_title=old_title,
                    new_title=new_listing.title,
                    old_tags=old_tags,
                    new_tags=new_listing.tags,
                )

                refreshed += 1
                logger.info("SEO refreshed for %s: '%s' -> '%s'",
                            pid, old_title[:50], new_listing.title[:50])

                await asyncio.sleep(2)  # Rate limit (Claude + Etsy)

            except Exception as e:
                logger.error("SEO refresh failed for %s: %s", pid, e)
                try:
                    await db.save_seo_refresh_log(
                        printify_product_id=pid,
                        etsy_listing_id=etsy_listing_id,
                        reason="low_views",
                        old_title="",
                        new_title="",
                        status="error",
                    )
                except Exception:
                    pass

        logger.info("Auto SEO refresh complete: %d/%d refreshed", refreshed, len(candidates))
        if refreshed > 0:
            await self.notifier.send_message(
                f"🔄 Auto SEO refresh: updated {refreshed}/{len(candidates)} listings with low views"
            )

    async def _auto_etsy_sync(self):
        """Every 6 hours: batch-fetch Etsy views/favorites/orders."""
        if not self.etsy_sync:
            return
        try:
            result = await self.etsy_sync.full_sync()
            views_count = result["views"]["synced"]
            orders_count = result["orders"]["synced"]
            logger.info("Auto Etsy sync: %d views/favs, %d orders", views_count, orders_count)
        except Exception as e:
            logger.error("Auto Etsy sync failed: %s", e)
