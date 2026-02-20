"""
Telegram notification service for poster-generator.

Sends notifications for product lifecycle events:
- Product created in Printify
- Product added to publish queue
- Product published / failed to publish
- Batch generation completed
- Daily summary digest
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

EST = timezone(timedelta(hours=-5))


class NotificationService:
    """Sends notifications via Telegram bot. Silent if not configured."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self._enabled = bool(self.token and self.chat_id)

    @property
    def is_configured(self) -> bool:
        return self._enabled

    async def _send(self, message: str, image_url: Optional[str] = None):
        if not self._enabled:
            return
        try:
            async with httpx.AsyncClient() as client:
                if image_url:
                    url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
                    await client.post(url, json={
                        "chat_id": self.chat_id,
                        "photo": image_url,
                        "caption": message,
                        "parse_mode": "HTML",
                    }, timeout=15.0)
                else:
                    url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                    await client.post(url, json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    }, timeout=10.0)
        except Exception as e:
            logger.warning("Telegram notification failed: %s", e)

    # ------------------------------------------------------------------
    # Product lifecycle
    # ------------------------------------------------------------------

    async def notify_product_created(self, title: str, product_id: str):
        """Product created in Printify."""
        msg = (
            f"🆕 <b>Product Created:</b> {title}\n"
            f"📎 ID: <code>{product_id}</code>"
        )
        await self._send(msg)

    async def notify_queued(self, title: str, scheduled_at: str, image_url: Optional[str] = None):
        """Product added to publish queue."""
        try:
            dt = datetime.fromisoformat(scheduled_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            time_str = dt.astimezone(EST).strftime("%b %d, %H:%M EST")
        except Exception:
            time_str = scheduled_at
        msg = (
            f"📅 <b>Queued:</b> {title}\n"
            f"⏰ Scheduled: {time_str}"
        )
        await self._send(msg, image_url=image_url)

    async def notify_published(
        self, title: str, pending_count: int, next_at: Optional[str] = None,
        image_url: Optional[str] = None,
    ):
        """Product published to Etsy."""
        lines = [f"✅ <b>Published:</b> {title}"]
        lines.append(f"📦 Remaining in queue: {pending_count}")
        if next_at:
            try:
                next_dt = datetime.fromisoformat(next_at)
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                next_est = next_dt.astimezone(EST)
                lines.append(
                    f"⏰ Next publish: {next_est.strftime('%b %d, %H:%M')} EST"
                )
            except Exception:
                lines.append(f"⏰ Next publish: {next_at}")
        await self._send("\n".join(lines), image_url=image_url)

    async def notify_publish_failed(self, title: str, error: str):
        """Publish failed."""
        msg = f"❌ <b>Failed to publish:</b> {title}\n<code>{error[:200]}</code>"
        await self._send(msg)

    # ------------------------------------------------------------------
    # DovShop
    # ------------------------------------------------------------------

    async def notify_dovshop_published(
        self, title: str, collection: str | None = None,
        categories: list[str] | None = None, image_url: str | None = None,
    ):
        """Product auto-published to DovShop."""
        lines = [f"\U0001f310 <b>DovShop:</b> {title}"]
        if collection:
            lines.append(f"\U0001f4c1 Collection: {collection}")
        if categories:
            lines.append(f"\U0001f3f7 Categories: {', '.join(categories)}")
        await self._send("\n".join(lines), image_url=image_url)

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    async def notify_batch_completed(
        self, batch_id: str, total: int, completed: int, failed: int
    ):
        """Batch generation finished."""
        msg = (
            f"📦 <b>Batch Complete:</b> {batch_id[:8]}...\n"
            f"✅ Completed: {completed}/{total}"
        )
        if failed > 0:
            msg += f"\n❌ Failed: {failed}"
        await self._send(msg)

    # ------------------------------------------------------------------
    # Daily summary
    # ------------------------------------------------------------------

    async def notify_daily_summary(self, stats: dict):
        """Morning digest with queue status."""
        msg = (
            f"📊 <b>Daily Summary</b>\n\n"
            f"📦 Queue: {stats.get('pending', 0)} pending\n"
            f"✅ Published yesterday: {stats.get('published_yesterday', 0)}\n"
            f"📅 Upcoming today: {stats.get('upcoming_today', 0)}"
        )
        if stats.get("failed", 0) > 0:
            msg += f"\n⚠️ Failed: {stats['failed']}"
        await self._send(msg)
