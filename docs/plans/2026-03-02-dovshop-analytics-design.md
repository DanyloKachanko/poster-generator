# DovShop Analytics — Design

**Date:** 2026-03-02
**Approach:** Custom event tracker on DovShop, data consumed by poster-generator dashboard

## 1. Event Collection (DovShop Frontend)

Lightweight client component `<Analytics />` in layout.tsx. Uses `navigator.sendBeacon` to POST events to `/api/analytics/event` without blocking the page.

### Events

| Event | Trigger | Data |
|-------|---------|------|
| `page_view` | Page load | path, referrer, device, screen |
| `etsy_click` | "Buy on Etsy" click | poster_id, source (main/sticky), size, price |
| `poster_view` | Poster card visible | poster_id, collection |
| `gallery_interact` | Photo change in gallery | poster_id, image_index |
| `size_select` | Size selector click | poster_id, size, price |
| `scroll_depth` | 25/50/75/100% scroll | path, depth |
| `collection_click` | Collection card click | collection_id |
| `time_on_page` | beforeunload | path, seconds |

### Session tracking

UUID stored in cookie (`ds_sid`), expires after 30 min inactivity. No PII collected.

## 2. Database (DovShop Prisma SQLite)

### Raw events table

```prisma
model AnalyticsEvent {
  id        Int      @id @default(autoincrement())
  eventType String   // page_view, etsy_click, etc.
  path      String
  posterId  Int?
  data      String?  // JSON for extra fields
  sessionId String
  device    String?  // mobile, desktop, tablet
  referrer  String?
  createdAt DateTime @default(now())

  @@index([eventType, createdAt])
  @@index([posterId, eventType])
  @@index([sessionId])
}
```

### Aggregated daily stats

```prisma
model DailyStats {
  id              Int      @id @default(autoincrement())
  date            String   // YYYY-MM-DD
  path            String?
  posterId        Int?
  pageViews       Int      @default(0)
  etsyClicks      Int      @default(0)
  uniqueVisitors  Int      @default(0)
  avgTimeOnPage   Float    @default(0)
  avgScrollDepth  Float    @default(0)

  @@unique([date, path, posterId])
  @@index([date])
  @@index([posterId, date])
}
```

Aggregation cron: daily at midnight, rolls raw events into DailyStats, prunes raw events older than 30 days.

## 3. DovShop API Endpoints

### `POST /api/analytics/event` (public, no auth)

Accepts beacon payload: `{ events: [{ type, path, posterId?, data?, sessionId, device?, referrer? }] }`

Batched — tracker collects events and sends every 5 seconds or on beforeunload.

### `GET /api/analytics/summary?days=7` (API key required)

Returns aggregated data for poster-generator to consume:

```json
{
  "period": "2026-02-23/2026-03-02",
  "totals": {
    "pageViews": 342,
    "uniqueVisitors": 187,
    "etsyClicks": 24,
    "ctr": 7.02,
    "avgTimeOnPage": 45.3
  },
  "daily": [
    { "date": "2026-03-01", "pageViews": 52, "etsyClicks": 4, "uniqueVisitors": 31 }
  ],
  "topPosters": [
    { "posterId": 42, "slug": "ocean-wave...", "views": 58, "etsyClicks": 8, "ctr": 13.8 }
  ],
  "topReferrers": [
    { "source": "google", "visits": 95 }
  ],
  "devices": { "mobile": 62, "desktop": 35, "tablet": 3 },
  "scrollDepth": { "25": 95, "50": 72, "75": 41, "100": 18 }
}
```

### `GET /api/analytics/poster/:id?days=30` (API key required)

Per-poster daily breakdown: views, clicks, time_on_page, scroll_depth, size_select counts.

## 4. Poster-Generator Integration

### Data sync

New scheduled task: every hour, `GET /api/analytics/summary?days=1` from DovShop prod, store in PostgreSQL `dovshop_analytics` table.

### Dashboard

New tab **"DovShop"** in `/monitor`:

- **Overview cards**: Visitors today, Etsy clicks, CTR, avg time on page
- **Line chart**: Daily views + Etsy clicks (30 days)
- **Top posters table**: Views, clicks, CTR, scroll depth per poster
- **Referrer sources**: Pie chart (Google, Pinterest, direct, other)
- **Device split**: Mobile/desktop/tablet percentages
- **Conversion funnel**: page_view → poster_view → size_select → etsy_click

### API routes

- `GET /dovshop/analytics` — fetch & return cached DovShop analytics
- `POST /dovshop/analytics/sync` — manually trigger sync from DovShop
- `GET /dovshop/analytics/poster/{printify_product_id}` — per-product DovShop stats merged with Etsy stats
