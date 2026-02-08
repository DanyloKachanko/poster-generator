"""
Scheduled publishing for Etsy via Printify.

Publishes products at configurable EST times to maximize
Etsy's recency boost. Settings are stored in DB and reload every cycle.
"""

import logging
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import List, Optional

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

    def __init__(self, printify: PrintifyAPI, notifier: NotificationService):
        self.printify = printify
        self.notifier = notifier
        self.scheduler = AsyncIOScheduler()
        # Cached settings — reloaded every check cycle
        self._publish_times: List[dt_time] = list(_DEFAULT_TIMES)
        self._enabled: bool = True

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
        except Exception as e:
            logger.warning("Failed to load schedule settings: %s", e)

    async def reload_settings(self):
        """Public method to immediately reload settings (called after API update)."""
        await self._load_settings()
        logger.info(
            "Schedule settings reloaded: times=%s, enabled=%s",
            [t.strftime("%H:%M") for t in self._publish_times],
            self._enabled,
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
        """Find the next available EST publish slot."""
        last_time_str = await db.get_last_scheduled_time()
        now_utc = datetime.now(timezone.utc)

        if last_time_str:
            last_time = datetime.fromisoformat(last_time_str)
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            return self._next_slot_after(last_time)
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

    async def add_to_queue(self, printify_product_id: str, title: str, image_url: Optional[str] = None) -> dict:
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

        await self.printify.publish_product(printify_product_id)
        await db.update_schedule_status(printify_product_id, "published")
        logger.info("Immediately published %s", printify_product_id)
        stats = await db.get_schedule_stats()
        await self.notifier.notify_published(
            title, stats["pending"], stats["next_publish_at"], image_url=image_url
        )
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
                await self.printify.publish_product(pid)
                await db.update_schedule_status(pid, "published")
                logger.info("Published %s (%s)", pid, item["title"][:40])
                stats = await db.get_schedule_stats()
                await self.notifier.notify_published(
                    item["title"], stats["pending"], stats["next_publish_at"],
                    image_url=item.get("image_url"),
                )
            except Exception as e:
                await db.update_schedule_status(pid, "failed", str(e))
                logger.error("Failed to publish %s: %s", pid, e)
                await self.notifier.notify_publish_failed(item["title"], str(e))

    async def _send_daily_summary(self):
        """Send morning digest via Telegram."""
        try:
            stats = await db.get_daily_summary_stats()
            await self.notifier.notify_daily_summary(stats)
        except Exception as e:
            logger.warning("Failed to send daily summary: %s", e)
