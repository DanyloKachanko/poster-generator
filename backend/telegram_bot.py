"""
Interactive Telegram bot for poster-generator.

Adds command handling and inline keyboards on top of the existing
notification service.  Runs a long-polling loop as an asyncio task
inside the backend process.

Phase 1: /stats — analytics dashboard + top products
Phase 2: /publish — carousel of pending products with Publish Now
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

import database as db

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    {"command": "stats", "description": "📊 Analytics dashboard (live from Etsy)"},
    {"command": "top", "description": "🏆 Top products by views"},
    {"command": "queue", "description": "📅 Publish queue status"},
    {"command": "publish", "description": "🚀 Browse & publish products"},
    {"command": "help", "description": "🤖 List all commands"},
]

EST = timezone(timedelta(hours=-5))


class TelegramBot:
    """Interactive Telegram bot with long-polling."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self._enabled = bool(self.token and self.chat_id)
        self._offset = 0  # getUpdates offset
        self._task: Optional[asyncio.Task] = None
        self._running = False
        # Publish carousel state per chat
        self._carousel: dict = {}  # chat_id -> {"index": int, "message_id": int}

    @property
    def is_configured(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        if not self._enabled:
            logger.info("Telegram bot not configured, skipping")
            return
        self._running = True
        await self._setup_commands()
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram bot started (long-polling)")

    async def _setup_commands(self):
        """Register bot menu commands with Telegram."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.token}/setMyCommands",
                    json={"commands": BOT_COMMANDS},
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning("Failed to set bot commands: %s", e)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram bot stopped")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_loop(self):
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    self._offset = update["update_id"] + 1
                    try:
                        await self._handle_update(update)
                    except Exception as e:
                        logger.error("Error handling update: %s", e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Polling error: %s", e)
                await asyncio.sleep(5)

    async def _get_updates(self) -> list:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                params={"offset": self._offset, "timeout": 30},
                timeout=35.0,
            )
            data = resp.json()
            return data.get("result", [])

    # ------------------------------------------------------------------
    # Update routing
    # ------------------------------------------------------------------

    async def _handle_update(self, update: dict):
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
        elif "message" in update:
            msg = update["message"]
            text = (msg.get("text") or "").strip()
            chat_id = str(msg["chat"]["id"])
            if text.startswith("/"):
                cmd = text.split()[0].lower().split("@")[0]  # strip @botname
                await self._handle_command(cmd, chat_id, msg)

    async def _handle_command(self, cmd: str, chat_id: str, msg: dict):
        handlers = {
            "/stats": self._cmd_stats,
            "/start": self._cmd_stats,
            "/top": self._cmd_top_products,
            "/queue": self._cmd_queue,
            "/publish": self._cmd_publish,
            "/help": self._cmd_help,
        }
        handler = handlers.get(cmd)
        if handler:
            await handler(chat_id)
        else:
            await self._send_text(chat_id, "Unknown command. Try /help")

    async def _handle_callback(self, callback: dict):
        chat_id = str(callback["message"]["chat"]["id"])
        message_id = callback["message"]["message_id"]
        data = callback.get("data", "")

        # Acknowledge callback immediately
        await self._answer_callback(callback["id"])

        if data == "stats":
            await self._cmd_stats(chat_id)
        elif data == "top_products":
            await self._cmd_top_products(chat_id)
        elif data == "queue":
            await self._cmd_queue(chat_id)
        elif data == "refresh_stats":
            await self._edit_stats(chat_id, message_id)
        elif data.startswith("pub_next:") or data.startswith("pub_prev:"):
            direction = 1 if data.startswith("pub_next") else -1
            await self._carousel_navigate(chat_id, message_id, direction)
        elif data.startswith("pub_now:"):
            product_id = data.split(":", 1)[1]
            await self._publish_now(chat_id, message_id, product_id)
        elif data.startswith("pub_confirm:"):
            product_id = data.split(":", 1)[1]
            await self._publish_confirm(chat_id, message_id, product_id)
        elif data == "pub_cancel":
            await self._carousel_navigate(chat_id, message_id, 0)

    # ------------------------------------------------------------------
    # /stats — Analytics dashboard
    # ------------------------------------------------------------------

    async def _cmd_stats(self, chat_id: str):
        text, keyboard = await self._build_stats()
        await self._send_text(chat_id, text, keyboard)

    async def _edit_stats(self, chat_id: str, message_id: int):
        text, keyboard = await self._build_stats()
        await self._edit_text(chat_id, message_id, text, keyboard)

    async def _fetch_live_etsy_stats(self):
        """Fetch live views and favorites from Etsy API for all shop listings."""
        from routes.etsy_auth import ensure_etsy_token
        from deps import etsy as etsy_client

        try:
            access_token, shop_id = await ensure_etsy_token()
        except Exception:
            return None  # Etsy not connected

        try:
            listings = await etsy_client.get_all_listings(access_token, shop_id)
        except Exception as e:
            logger.warning("Failed to fetch Etsy listings: %s", e)
            return None

        products = []
        total_views = 0
        total_favs = 0

        for listing in listings:
            views = listing.get("views", 0) or 0
            favs = listing.get("num_favorers", 0) or 0
            title = (listing.get("title") or "")[:45]
            total_views += views
            total_favs += favs
            products.append({
                "title": title,
                "views": views,
                "favorites": favs,
                "listing_id": str(listing.get("listing_id", "")),
            })

        # Sort by views descending
        products.sort(key=lambda p: p["views"], reverse=True)

        return {
            "total_views": total_views,
            "total_favorites": total_favs,
            "products": products,
            "count": len(products),
        }

    async def _build_stats(self):
        schedule_stats = await db.get_schedule_stats()
        pending = schedule_stats.get("pending", 0)
        next_at = schedule_stats.get("next_publish_at")
        next_str = ""
        if next_at:
            try:
                dt = datetime.fromisoformat(next_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                next_str = dt.astimezone(EST).strftime("%b %d, %H:%M EST")
            except Exception:
                next_str = next_at

        # Try live Etsy data first, fall back to cached DB data
        live = await self._fetch_live_etsy_stats()

        if live:
            total_views = live["total_views"]
            total_favs = live["total_favorites"]
            product_count = live["count"]
            source = "live from Etsy"
        else:
            summary = await db.get_analytics_summary()
            total_views = sum(p.get("total_views", 0) for p in summary)
            total_favs = sum(p.get("total_favorites", 0) for p in summary)
            product_count = len(summary)
            source = "cached"

        # Orders/revenue from DB (Etsy API doesn't expose this easily)
        db_totals = await db.get_analytics_totals_for_period(7)
        orders_7d = db_totals.get("total_orders", 0)
        revenue_7d = db_totals.get("total_revenue_cents", 0)

        text = (
            f"📊 <b>DovShopDesign Stats</b>\n\n"
            f"👁 Listing views: {total_views:,}\n"
            f"❤️ Favorites: {total_favs:,}\n"
            f"🛒 Orders (7d): {orders_7d}\n"
            f"💰 Revenue (7d): ${revenue_7d / 100:.2f}\n\n"
            f"📦 Products: {product_count} on Etsy\n"
            f"📅 Queue: {pending} pending"
        )
        if next_str:
            text += f", next: {next_str}"
        text += f"\n\n<i>📡 {source}</i>"

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🏆 Top Products", "callback_data": "top_products"},
                    {"text": "📅 Queue", "callback_data": "queue"},
                ],
                [
                    {"text": "🔄 Refresh", "callback_data": "refresh_stats"},
                ],
            ]
        }
        return text, keyboard

    # ------------------------------------------------------------------
    # Top Products callback
    # ------------------------------------------------------------------

    async def _cmd_top_products(self, chat_id: str):
        # Try live Etsy data first
        live = await self._fetch_live_etsy_stats()

        if live and live["products"]:
            top = live["products"][:5]
            lines = ["🏆 <b>Top 5 Products</b> (live views)\n"]
            for i, p in enumerate(top, 1):
                title = p["title"]
                if len(title) > 40:
                    title = title[:37] + "..."
                lines.append(f"{i}. {title}\n   👁 {p['views']} | ❤️ {p['favorites']}")
        else:
            top = await db.get_top_products(5)
            if not top:
                await self._send_text(chat_id, "No product analytics yet.")
                return
            lines = ["🏆 <b>Top 5 Products</b> (cached)\n"]
            for i, p in enumerate(top, 1):
                views = p.get("total_views", 0)
                orders = p.get("total_orders", 0)
                product = await db.get_product_by_printify_id(p["printify_product_id"])
                title = (product or {}).get("title", p["printify_product_id"])
                if len(title) > 40:
                    title = title[:37] + "..."
                lines.append(f"{i}. {title}\n   👁 {views} | 🛒 {orders}")

        keyboard = {
            "inline_keyboard": [
                [{"text": "⬅️ Back to Stats", "callback_data": "stats"}]
            ]
        }
        await self._send_text(chat_id, "\n".join(lines), keyboard)

    # ------------------------------------------------------------------
    # /queue — Schedule status
    # ------------------------------------------------------------------

    async def _cmd_queue(self, chat_id: str):
        queue = await db.get_schedule_queue(status="pending")
        if not queue:
            text = "📅 <b>Queue is empty</b> — no pending products."
            keyboard = {
                "inline_keyboard": [
                    [{"text": "⬅️ Back to Stats", "callback_data": "stats"}]
                ]
            }
            await self._send_text(chat_id, text, keyboard)
            return

        lines = [f"📅 <b>Publish Queue</b> ({len(queue)} pending)\n"]
        for i, item in enumerate(queue[:10], 1):
            title = item.get("title", "Unknown")
            if len(title) > 35:
                title = title[:32] + "..."
            scheduled = item.get("scheduled_publish_at", "")
            try:
                dt = datetime.fromisoformat(scheduled)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                time_str = dt.astimezone(EST).strftime("%b %d, %H:%M")
            except Exception:
                time_str = scheduled[:16] if scheduled else "?"
            lines.append(f"{i}. {title}\n   ⏰ {time_str} EST")

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Publish", "callback_data": "queue"},
                    {"text": "⬅️ Stats", "callback_data": "stats"},
                ],
            ]
        }
        await self._send_text(chat_id, "\n".join(lines), keyboard)

    # ------------------------------------------------------------------
    # /publish — Carousel of pending products
    # ------------------------------------------------------------------

    async def _cmd_publish(self, chat_id: str):
        queue = await db.get_schedule_queue(status="pending")
        if not queue:
            await self._send_text(chat_id, "📅 No pending products to publish.")
            return

        self._carousel[chat_id] = {"index": 0, "items": queue}
        await self._send_carousel_card(chat_id, queue, 0)

    async def _send_carousel_card(self, chat_id: str, items: list, index: int):
        item = items[index]
        title = item.get("title", "Unknown")
        scheduled = item.get("scheduled_publish_at", "")
        pid = item.get("printify_product_id", "")
        image_url = item.get("image_url")

        try:
            dt = datetime.fromisoformat(scheduled)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            time_str = dt.astimezone(EST).strftime("%b %d, %H:%M EST")
        except Exception:
            time_str = scheduled[:16] if scheduled else "?"

        caption = (
            f"🖼 <b>{title}</b>\n"
            f"📅 Scheduled: {time_str}\n"
            f"📦 Status: pending"
        )

        nav_row = []
        if index > 0:
            nav_row.append({"text": "⬅️", "callback_data": f"pub_prev:{index}"})
        nav_row.append({"text": f"{index + 1}/{len(items)}", "callback_data": "noop"})
        if index < len(items) - 1:
            nav_row.append({"text": "➡️", "callback_data": f"pub_next:{index}"})

        keyboard = {
            "inline_keyboard": [
                nav_row,
                [{"text": "🚀 Publish Now", "callback_data": f"pub_now:{pid}"}],
            ]
        }

        if image_url:
            await self._send_photo(chat_id, image_url, caption, keyboard)
        else:
            await self._send_text(chat_id, caption, keyboard)

    async def _carousel_navigate(self, chat_id: str, message_id: int, direction: int):
        state = self._carousel.get(chat_id)
        if not state:
            return

        # Refresh queue
        queue = await db.get_schedule_queue(status="pending")
        if not queue:
            await self._edit_text(chat_id, message_id, "📅 No pending products.")
            return

        state["items"] = queue
        new_index = (state["index"] + direction) % len(queue)
        state["index"] = new_index

        item = queue[new_index]
        title = item.get("title", "Unknown")
        scheduled = item.get("scheduled_publish_at", "")
        pid = item.get("printify_product_id", "")

        try:
            dt = datetime.fromisoformat(scheduled)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            time_str = dt.astimezone(EST).strftime("%b %d, %H:%M EST")
        except Exception:
            time_str = scheduled[:16] if scheduled else "?"

        caption = (
            f"🖼 <b>{title}</b>\n"
            f"📅 Scheduled: {time_str}\n"
            f"📦 Status: pending"
        )

        nav_row = []
        if new_index > 0:
            nav_row.append({"text": "⬅️", "callback_data": f"pub_prev:{new_index}"})
        nav_row.append({"text": f"{new_index + 1}/{len(queue)}", "callback_data": "noop"})
        if new_index < len(queue) - 1:
            nav_row.append({"text": "➡️", "callback_data": f"pub_next:{new_index}"})

        keyboard = {
            "inline_keyboard": [
                nav_row,
                [{"text": "🚀 Publish Now", "callback_data": f"pub_now:{pid}"}],
            ]
        }

        await self._edit_text(chat_id, message_id, caption, keyboard)

    async def _publish_now(self, chat_id: str, message_id: int, product_id: str):
        """Show confirmation before publishing."""
        product = await db.get_product_by_printify_id(product_id)
        title = (product or {}).get("title", product_id)
        if len(title) > 40:
            title = title[:37] + "..."

        text = f"⚠️ Publish <b>{title}</b> now?\n\nThis will publish immediately to Etsy."
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Yes, publish", "callback_data": f"pub_confirm:{product_id}"},
                    {"text": "❌ Cancel", "callback_data": "pub_cancel"},
                ]
            ]
        }
        await self._edit_text(chat_id, message_id, text, keyboard)

    async def _publish_confirm(self, chat_id: str, message_id: int, product_id: str):
        """Actually publish the product."""
        from deps import publish_scheduler

        try:
            await publish_scheduler.publish_now(product_id)
            product = await db.get_product_by_printify_id(product_id)
            title = (product or {}).get("title", product_id)
            text = f"✅ <b>Published:</b> {title}\n\nMockups will be applied automatically."
            await self._edit_text(chat_id, message_id, text)
        except Exception as e:
            text = f"❌ Failed to publish: {e}"
            await self._edit_text(chat_id, message_id, text)

    # ------------------------------------------------------------------
    # /help
    # ------------------------------------------------------------------

    async def _cmd_help(self, chat_id: str):
        text = (
            "🤖 <b>DovShop Bot</b>\n\n"
            "/stats — Analytics dashboard\n"
            "/top — Top 5 products by views\n"
            "/queue — Publish queue status\n"
            "/publish — Browse & publish products\n"
            "/help — This message"
        )
        await self._send_text(chat_id, text)

    # ------------------------------------------------------------------
    # Telegram API helpers
    # ------------------------------------------------------------------

    async def _send_text(self, chat_id: str, text: str, reply_markup: dict = None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json=payload,
                    timeout=10.0,
                )
                return resp.json()
        except Exception as e:
            logger.warning("Failed to send message: %s", e)

    async def _edit_text(self, chat_id: str, message_id: int, text: str, reply_markup: dict = None):
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.token}/editMessageText",
                    json=payload,
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning("Failed to edit message: %s", e)

    async def _send_photo(self, chat_id: str, photo_url: str, caption: str, reply_markup: dict = None):
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendPhoto",
                    json=payload,
                    timeout=15.0,
                )
        except Exception as e:
            logger.warning("Failed to send photo: %s", e)

    async def _answer_callback(self, callback_id: str):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{self.token}/answerCallbackQuery",
                    json={"callback_query_id": callback_id},
                    timeout=5.0,
                )
        except Exception:
            pass

    async def send_message(self, text: str, image_url: Optional[str] = None):
        """Public method for sending messages (used by other modules)."""
        if not self._enabled:
            return
        if image_url:
            await self._send_photo(self.chat_id, image_url, text)
        else:
            await self._send_text(self.chat_id, text)
