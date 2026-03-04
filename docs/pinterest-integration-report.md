# Pinterest Integration — Progress Report

**Branch:** `refactor/modular-monolith`
**Date:** 2026-03-03
**Status:** All 8 phases complete, Docker build passes, all imports verified

---

## Summary

Full Pinterest integration module for the DovShop poster admin panel:
- OAuth2 connect/disconnect flow
- Pin creation with AI-generated content (Claude Haiku)
- Queue + publish system with rate limiting
- Analytics tracking (impressions, saves, clicks, outbound)
- Bulk generate for multiple products
- Scheduled background jobs (publish every 2h, analytics daily)
- Frontend tab under Publish > Pinterest

---

## Files Created

### Backend — `integrations/pinterest/`

| File | LOC | Description |
|------|-----|-------------|
| `client.py` | 226 | Pinterest API v5 client (OAuth2, boards, pins, analytics) |
| `generator.py` | 107 | Claude AI pin content generator (Pinterest SEO optimized) |
| `scheduler.py` | 133 | Pin publish scheduler + analytics sync |
| `__init__.py` | 3 | Re-exports |

### Backend — `db/`

| File | LOC | Description |
|------|-----|-------------|
| `pinterest.py` | 231 | All CRUD: tokens, boards, pins, analytics, stats |

### Backend — `routes/`

| File | LOC | Endpoints | Description |
|------|-----|-----------|-------------|
| `pinterest.py` | 275 | 16 | Auth, boards, pins, queue, bulk, analytics |

### Frontend

| File | LOC | Description |
|------|-----|-------------|
| `app/publish/pinterest/page.tsx` | 310 | Full Pinterest tab (queue, published, bulk, analytics) |
| `lib/api.ts` | +160 | 15 API functions + TypeScript interfaces |

---

## Files Modified

| File | Change |
|------|--------|
| `backend/deps.py` | Added `pinterest_api`, `pinterest_generator`, `pinterest_scheduler` singletons |
| `backend/main.py` | Registered `pinterest_router`, added `/pinterest/callback` to public auth paths |
| `backend/db/connection.py` | Added 3 tables: `pinterest_tokens`, `pinterest_boards`, `pinterest_pins` + indexes |
| `backend/db/__init__.py` | Added `from db.pinterest import *` |
| `backend/scheduler.py` | Added 2 APScheduler jobs: pin publish (2h), analytics sync (daily 15:00 UTC) |
| `frontend/app/publish/layout.tsx` | Added "Pinterest" tab |

---

## Database Schema (3 new tables)

```sql
pinterest_tokens    — single-row (id=1), OAuth access/refresh tokens + username
pinterest_boards    — board_id PK, name, description, pin_count, privacy
pinterest_pins      — id SERIAL, product_id FK→products, board_id, pin_id (Pinterest),
                      title, description, image_url, link, alt_text,
                      status (queued/published/failed), scheduled_at, published_at,
                      impressions, saves, clicks, outbound_clicks
```

---

## API Endpoints (16 total, prefix `/pinterest`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Connection status |
| GET | `/auth-url` | Generate OAuth2 URL |
| GET | `/callback` | OAuth2 callback (public, returns HTML) |
| POST | `/disconnect` | Remove tokens |
| GET | `/boards` | List + sync boards |
| POST | `/boards` | Create new board |
| POST | `/pins/queue` | Queue a pin |
| POST | `/pins/publish-now` | Publish all queued pins immediately |
| GET | `/pins/queue` | List queued pins |
| GET | `/pins/published` | List published pins with analytics |
| DELETE | `/pins/{id}` | Delete pin (optionally from Pinterest too) |
| GET | `/pins/product/{id}` | All pins for a product |
| POST | `/pins/generate` | AI-generate pin content for a product |
| POST | `/pins/bulk-generate` | AI-generate + queue for multiple products |
| GET | `/analytics/summary` | Aggregate stats |
| POST | `/analytics/sync` | Sync analytics from Pinterest API |

---

## Scheduled Jobs

| Job | Interval | Description |
|-----|----------|-------------|
| `pinterest_publish` | Every 2 hours | Publish up to 5 queued pins per batch, 10s delay between |
| `pinterest_analytics` | Daily 15:00 UTC | Sync 30-day analytics for all published pins |

---

## Verification

```
Backend Docker build:    OK
Frontend Docker build:   OK
All imports:             OK (16 route endpoints)
All singletons:          OK (PinterestAPI, PinterestPinGenerator, PinterestScheduler)
```

---

## Environment Variables (new, optional)

```
PINTEREST_APP_ID=           # Pinterest app ID
PINTEREST_APP_SECRET=       # Pinterest app secret
PINTEREST_REDIRECT_URI=     # Default: https://design.dovshop.org/api/pinterest/callback
```

---

## Next Steps

1. Add `PINTEREST_APP_ID` + `PINTEREST_APP_SECRET` to prod .env
2. Create a Pinterest developer app at https://developers.pinterest.com
3. Set redirect URI to `https://designapi.dovshop.org/pinterest/callback`
4. Deploy, connect Pinterest account via Publish > Pinterest tab
5. Create a board for wall art pins
6. Use Bulk Generate to queue pins for existing products
