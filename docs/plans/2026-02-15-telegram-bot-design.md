# Telegram Bot — Interactive Commands

## Architecture

Long-polling (`getUpdates`) in asyncio task inside backend. Single file `backend/telegram_bot.py` with command handlers and callback router. Starts alongside scheduler in `lifespan`.

Uses existing DB functions and services directly — no HTTP calls to self.

## Phases

### Phase 1: Analytics (priority)

**`/stats`** — Main dashboard with views, favorites, orders, revenue, conversion rate, 7-day trends, product count, queue status. Inline buttons: `Top Products`, `Queue`, `Refresh`.

**`Top Products` callback** — Top 5 by views (7 days) with orders count. Back button.

### Phase 2: Publish carousel

**`/publish`** — Shows pending products one by one with photo (mockup or Printify image) + title + scheduled time. Inline buttons: Prev/Next navigation, Publish Now (with confirmation), counter (1/N).

### Phase 3 (future): Generation

**`/generate <prompt>`** — Leonardo generation → auto-product with description → mockups → add to schedule.

## Implementation

- `backend/telegram_bot.py` — TelegramBot class with:
  - `start()` / `stop()` — polling lifecycle
  - `_poll_updates()` — long-polling loop
  - `_handle_command()` — route /commands
  - `_handle_callback()` — route inline button presses
  - `_cmd_stats()` — analytics dashboard
  - `_cmd_publish()` — publish carousel
  - `_send_product_card()` — render product card with photo + buttons
- Start in `main.py` lifespan alongside scheduler
- Config: reuses TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID from env
