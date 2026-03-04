"""Pinterest pin scheduler — publishes queued pins and syncs analytics."""

import asyncio
import logging
import time
from datetime import datetime, timedelta

import database as db
from integrations.pinterest.client import PinterestAPI

logger = logging.getLogger(__name__)

# Rate limit: Pinterest allows ~1000 writes/day, but we go conservative
MAX_PINS_PER_BATCH = 5
MIN_DELAY_BETWEEN_PINS = 10  # seconds


class PinterestScheduler:
    """Publishes queued pins to Pinterest on a schedule."""

    def __init__(self, pinterest_api: PinterestAPI, notifier=None):
        self.pinterest = pinterest_api
        self.notifier = notifier

    async def _get_valid_token(self) -> str | None:
        """Get a valid Pinterest access token, refreshing if needed."""
        tokens = await db.get_pinterest_tokens()
        if not tokens:
            return None

        access_token = tokens["access_token"]

        if tokens["expires_at"] < int(time.time()):
            try:
                new_tokens = await self.pinterest.refresh_access_token(tokens["refresh_token"])
                await db.save_pinterest_tokens(
                    access_token=new_tokens.access_token,
                    refresh_token=new_tokens.refresh_token,
                    expires_at=new_tokens.expires_at,
                )
                access_token = new_tokens.access_token
            except Exception as e:
                logger.error(f"Pinterest token refresh failed: {e}")
                return None

        return access_token

    async def publish_due_pins(self) -> dict:
        """Publish queued pins to Pinterest. Called by APScheduler."""
        access_token = await self._get_valid_token()
        if not access_token:
            logger.debug("Pinterest not connected, skipping pin publish")
            return {"published": 0, "failed": 0, "skipped": "not_connected"}

        queued = await db.get_queued_pins(limit=MAX_PINS_PER_BATCH)
        if not queued:
            return {"published": 0, "failed": 0}

        published = 0
        failed = 0

        for pin in queued:
            # Skip if scheduled for the future
            if pin.get("scheduled_at") and pin["scheduled_at"] > datetime.utcnow():
                continue

            try:
                result = await self.pinterest.create_pin(
                    access_token=access_token,
                    board_id=pin["board_id"],
                    title=pin["title"],
                    description=pin["description"],
                    link=pin["link"],
                    image_url=pin["image_url"],
                    alt_text=pin.get("alt_text", ""),
                )
                pinterest_pin_id = result.get("id", "")
                await db.mark_pin_published(pin["id"], pinterest_pin_id)
                published += 1
                logger.info(f"Published pin {pin['id']} → Pinterest {pinterest_pin_id}")
            except Exception as e:
                error_msg = str(e)[:500]
                await db.mark_pin_failed(pin["id"], error_msg)
                failed += 1
                logger.error(f"Failed to publish pin {pin['id']}: {e}")

            # Rate-limit between pins
            if published + failed < len(queued):
                await asyncio.sleep(MIN_DELAY_BETWEEN_PINS)

        # Telegram notification
        if published > 0 and self.notifier:
            try:
                msg = f"📌 Pinterest: {published} pin(s) published"
                if failed:
                    msg += f", {failed} failed"
                await self.notifier.send_message(msg)
            except Exception:
                pass

        return {"published": published, "failed": failed}

    async def sync_pin_analytics(self) -> dict:
        """Sync analytics for all published pins. Called daily."""
        access_token = await self._get_valid_token()
        if not access_token:
            return {"synced": 0, "skipped": "not_connected"}

        published_pins = await db.get_published_pins(limit=200)
        if not published_pins:
            return {"synced": 0}

        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        synced = 0
        errors = 0

        for pin in published_pins:
            pin_id = pin.get("pin_id")
            if not pin_id:
                continue

            try:
                analytics = await self.pinterest.get_pin_analytics(
                    access_token=access_token,
                    pin_id=pin_id,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Sum up metrics from all data points
                totals = {"IMPRESSION": 0, "SAVE": 0, "PIN_CLICK": 0, "OUTBOUND_CLICK": 0}
                all_data = analytics.get("all", {}).get("daily_metrics", [])
                for day in all_data:
                    for metric_name, val in day.get("data_status", {}).items():
                        if metric_name in totals and isinstance(val, (int, float)):
                            totals[metric_name] += int(val)

                await db.update_pin_analytics(
                    pin_db_id=pin["id"],
                    impressions=totals["IMPRESSION"],
                    saves=totals["SAVE"],
                    clicks=totals["PIN_CLICK"],
                    outbound_clicks=totals["OUTBOUND_CLICK"],
                )
                synced += 1
            except Exception as e:
                errors += 1
                logger.warning(f"Analytics sync failed for pin {pin_id}: {e}")

            # Be nice to the API
            await asyncio.sleep(1)

        return {"synced": synced, "errors": errors}
