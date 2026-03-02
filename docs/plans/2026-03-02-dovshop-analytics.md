# DovShop Analytics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Full analytics system: DovShop collects user events, poster-generator displays them in /monitor dashboard.

**Architecture:** Lightweight JS tracker on DovShop sends batched events to `/api/analytics/event`. Events stored in SQLite via Prisma. Aggregated daily. Poster-generator fetches summary via `/api/analytics/summary` endpoint and displays in new "DovShop" monitor tab.

**Tech Stack:** Next.js API routes (DovShop), Prisma + SQLite, FastAPI (poster-generator), custom Tailwind charts (no libraries)

---

### Task 1: Prisma Schema — Analytics Tables

**Files:**
- Modify: `/home/dovek/dev-database/Github/pinterest-service/prisma/schema.prisma`

**Step 1: Add AnalyticsEvent and DailyStats models to schema**

Add at the end of `schema.prisma`:

```prisma
model AnalyticsEvent {
  id        Int      @id @default(autoincrement())
  eventType String
  path      String
  posterId  Int?
  data      String?
  sessionId String
  device    String?
  referrer  String?
  createdAt DateTime @default(now())

  @@index([eventType, createdAt])
  @@index([posterId, eventType])
  @@index([sessionId])
}

model DailyStats {
  id              Int    @id @default(autoincrement())
  date            String
  path            String @default("/")
  posterId        Int?
  pageViews       Int    @default(0)
  etsyClicks      Int    @default(0)
  uniqueVisitors  Int    @default(0)
  avgTimeOnPage   Float  @default(0)
  avgScrollDepth  Float  @default(0)

  @@unique([date, path, posterId])
  @@index([date])
  @@index([posterId, date])
}
```

**Step 2: Run migration**

```bash
cd /home/dovek/dev-database/Github/pinterest-service
npx prisma migrate dev --name add_analytics_tables
```

Expected: Migration created, SQLite tables added.

**Step 3: Commit**

```bash
git add prisma/
git commit -m "feat: add AnalyticsEvent and DailyStats Prisma models"
```

---

### Task 2: Event Ingestion API — `/api/analytics/event`

**Files:**
- Create: `/home/dovek/dev-database/Github/pinterest-service/src/app/api/analytics/event/route.ts`

**Step 1: Create the event ingestion endpoint**

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

const VALID_EVENTS = new Set([
  'page_view', 'etsy_click', 'poster_view', 'gallery_interact',
  'size_select', 'scroll_depth', 'collection_click', 'time_on_page'
])

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const events = body.events
    if (!Array.isArray(events) || events.length === 0) {
      return NextResponse.json({ error: 'events array required' }, { status: 400 })
    }

    // Limit batch size
    const batch = events.slice(0, 50)

    const records = batch
      .filter((e: any) => VALID_EVENTS.has(e.type) && e.path && e.sessionId)
      .map((e: any) => ({
        eventType: e.type,
        path: String(e.path).slice(0, 500),
        posterId: e.posterId ? Number(e.posterId) : null,
        data: e.data ? JSON.stringify(e.data) : null,
        sessionId: String(e.sessionId).slice(0, 64),
        device: e.device ? String(e.device).slice(0, 20) : null,
        referrer: e.referrer ? String(e.referrer).slice(0, 500) : null,
      }))

    if (records.length > 0) {
      await prisma.$transaction(
        records.map(r => prisma.analyticsEvent.create({ data: r }))
      )
    }

    return NextResponse.json({ ok: true, count: records.length })
  } catch (e) {
    console.error('Analytics event error:', e)
    return NextResponse.json({ ok: true, count: 0 })
  }
}
```

**Step 2: Verify it works**

```bash
curl -X POST http://localhost:3000/api/analytics/event \
  -H "Content-Type: application/json" \
  -d '{"events":[{"type":"page_view","path":"/","sessionId":"test-123","device":"desktop","referrer":"google.com"}]}'
```

Expected: `{"ok":true,"count":1}`

**Step 3: Commit**

```bash
git add src/app/api/analytics/
git commit -m "feat: analytics event ingestion endpoint"
```

---

### Task 3: Summary API — `/api/analytics/summary`

**Files:**
- Create: `/home/dovek/dev-database/Github/pinterest-service/src/app/api/analytics/summary/route.ts`

**Step 1: Create the summary endpoint (API key protected)**

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { validateApiKey, unauthorizedResponse } from '@/lib/api-auth'
import { prisma } from '@/lib/prisma'

export async function GET(request: NextRequest) {
  if (!validateApiKey(request)) {
    return unauthorizedResponse()
  }

  const days = Math.min(Number(request.nextUrl.searchParams.get('days') || '7'), 90)
  const since = new Date()
  since.setDate(since.getDate() - days)

  const events = await prisma.analyticsEvent.findMany({
    where: { createdAt: { gte: since } },
    select: {
      eventType: true,
      path: true,
      posterId: true,
      data: true,
      sessionId: true,
      device: true,
      referrer: true,
      createdAt: true,
    },
  })

  // Totals
  const pageViews = events.filter(e => e.eventType === 'page_view').length
  const etsyClicks = events.filter(e => e.eventType === 'etsy_click').length
  const uniqueSessions = new Set(events.map(e => e.sessionId)).size
  const ctr = pageViews > 0 ? Math.round((etsyClicks / pageViews) * 10000) / 100 : 0

  // Avg time on page
  const timeEvents = events.filter(e => e.eventType === 'time_on_page')
  const avgTime = timeEvents.length > 0
    ? timeEvents.reduce((sum, e) => {
        const d = e.data ? JSON.parse(e.data) : {}
        return sum + (d.seconds || 0)
      }, 0) / timeEvents.length
    : 0

  // Daily breakdown
  const dailyMap = new Map<string, { pageViews: number; etsyClicks: number; uniqueVisitors: Set<string> }>()
  for (const e of events) {
    const date = e.createdAt.toISOString().slice(0, 10)
    if (!dailyMap.has(date)) dailyMap.set(date, { pageViews: 0, etsyClicks: 0, uniqueVisitors: new Set() })
    const d = dailyMap.get(date)!
    d.uniqueVisitors.add(e.sessionId)
    if (e.eventType === 'page_view') d.pageViews++
    if (e.eventType === 'etsy_click') d.etsyClicks++
  }
  const daily = Array.from(dailyMap.entries())
    .map(([date, d]) => ({ date, pageViews: d.pageViews, etsyClicks: d.etsyClicks, uniqueVisitors: d.uniqueVisitors.size }))
    .sort((a, b) => a.date.localeCompare(b.date))

  // Top posters
  const posterMap = new Map<number, { views: number; clicks: number }>()
  for (const e of events) {
    if (!e.posterId) continue
    if (!posterMap.has(e.posterId)) posterMap.set(e.posterId, { views: 0, clicks: 0 })
    const p = posterMap.get(e.posterId)!
    if (e.eventType === 'poster_view' || e.eventType === 'page_view') p.views++
    if (e.eventType === 'etsy_click') p.clicks++
  }
  const topPosters = Array.from(posterMap.entries())
    .map(([posterId, d]) => ({ posterId, views: d.views, etsyClicks: d.clicks, ctr: d.views > 0 ? Math.round((d.clicks / d.views) * 10000) / 100 : 0 }))
    .sort((a, b) => b.views - a.views)
    .slice(0, 20)

  // Enrich top posters with slug/name
  const posterIds = topPosters.map(p => p.posterId)
  const posters = posterIds.length > 0
    ? await prisma.poster.findMany({ where: { id: { in: posterIds } }, select: { id: true, slug: true, name: true } })
    : []
  const posterLookup = new Map(posters.map(p => [p.id, p]))
  const enrichedPosters = topPosters.map(p => ({
    ...p,
    slug: posterLookup.get(p.posterId)?.slug || '',
    name: posterLookup.get(p.posterId)?.name || '',
  }))

  // Referrers
  const refMap = new Map<string, number>()
  for (const e of events) {
    if (e.eventType !== 'page_view' || !e.referrer) continue
    let source = 'direct'
    const ref = e.referrer.toLowerCase()
    if (ref.includes('google')) source = 'google'
    else if (ref.includes('pinterest')) source = 'pinterest'
    else if (ref.includes('facebook') || ref.includes('fb.')) source = 'facebook'
    else if (ref.includes('instagram')) source = 'instagram'
    else if (ref.includes('etsy')) source = 'etsy'
    else if (ref) source = 'other'
    refMap.set(source, (refMap.get(source) || 0) + 1)
  }
  const topReferrers = Array.from(refMap.entries())
    .map(([source, visits]) => ({ source, visits }))
    .sort((a, b) => b.visits - a.visits)

  // Devices
  const devices = { mobile: 0, desktop: 0, tablet: 0 }
  const countedSessions = new Set<string>()
  for (const e of events) {
    if (countedSessions.has(e.sessionId)) continue
    countedSessions.add(e.sessionId)
    const d = (e.device || 'desktop').toLowerCase()
    if (d === 'mobile') devices.mobile++
    else if (d === 'tablet') devices.tablet++
    else devices.desktop++
  }
  const totalDevices = devices.mobile + devices.desktop + devices.tablet || 1
  const devicePct = {
    mobile: Math.round((devices.mobile / totalDevices) * 100),
    desktop: Math.round((devices.desktop / totalDevices) * 100),
    tablet: Math.round((devices.tablet / totalDevices) * 100),
  }

  // Scroll depth
  const scrollEvents = events.filter(e => e.eventType === 'scroll_depth')
  const scrollDepth: Record<string, number> = { '25': 0, '50': 0, '75': 0, '100': 0 }
  for (const e of scrollEvents) {
    const d = e.data ? JSON.parse(e.data) : {}
    const depth = String(d.depth)
    if (depth in scrollDepth) scrollDepth[depth]++
  }

  const endDate = new Date().toISOString().slice(0, 10)
  const startDate = since.toISOString().slice(0, 10)

  return NextResponse.json({
    period: `${startDate}/${endDate}`,
    totals: { pageViews, uniqueVisitors: uniqueSessions, etsyClicks, ctr, avgTimeOnPage: Math.round(avgTime * 10) / 10 },
    daily,
    topPosters: enrichedPosters,
    topReferrers,
    devices: devicePct,
    scrollDepth,
  })
}
```

**Step 2: Test**

```bash
curl -s "http://localhost:3000/api/analytics/summary?days=7" \
  -H "x-api-key: $DOVSHOP_API_KEY" | python3 -m json.tool
```

**Step 3: Commit**

```bash
git add src/app/api/analytics/summary/
git commit -m "feat: analytics summary API endpoint"
```

---

### Task 4: Per-Poster Analytics API

**Files:**
- Create: `/home/dovek/dev-database/Github/pinterest-service/src/app/api/analytics/poster/[id]/route.ts`

**Step 1: Create per-poster endpoint**

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { validateApiKey, unauthorizedResponse } from '@/lib/api-auth'
import { prisma } from '@/lib/prisma'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!validateApiKey(request)) {
    return unauthorizedResponse()
  }

  const { id } = await params
  const posterId = Number(id)
  if (isNaN(posterId)) {
    return NextResponse.json({ error: 'Invalid poster ID' }, { status: 400 })
  }

  const days = Math.min(Number(request.nextUrl.searchParams.get('days') || '30'), 90)
  const since = new Date()
  since.setDate(since.getDate() - days)

  const events = await prisma.analyticsEvent.findMany({
    where: { posterId, createdAt: { gte: since } },
    select: { eventType: true, data: true, createdAt: true, sessionId: true },
  })

  // Daily breakdown
  const dailyMap = new Map<string, { views: number; clicks: number; timeSum: number; timeCount: number; scrollSum: number; scrollCount: number; sizeSelects: Map<string, number> }>()

  for (const e of events) {
    const date = e.createdAt.toISOString().slice(0, 10)
    if (!dailyMap.has(date)) {
      dailyMap.set(date, { views: 0, clicks: 0, timeSum: 0, timeCount: 0, scrollSum: 0, scrollCount: 0, sizeSelects: new Map() })
    }
    const d = dailyMap.get(date)!
    const parsed = e.data ? JSON.parse(e.data) : {}

    switch (e.eventType) {
      case 'page_view':
      case 'poster_view':
        d.views++
        break
      case 'etsy_click':
        d.clicks++
        break
      case 'time_on_page':
        d.timeSum += parsed.seconds || 0
        d.timeCount++
        break
      case 'scroll_depth':
        d.scrollSum += parsed.depth || 0
        d.scrollCount++
        break
      case 'size_select':
        const size = parsed.size || 'unknown'
        d.sizeSelects.set(size, (d.sizeSelects.get(size) || 0) + 1)
        break
    }
  }

  const daily = Array.from(dailyMap.entries())
    .map(([date, d]) => ({
      date,
      views: d.views,
      etsyClicks: d.clicks,
      avgTimeOnPage: d.timeCount > 0 ? Math.round((d.timeSum / d.timeCount) * 10) / 10 : 0,
      avgScrollDepth: d.scrollCount > 0 ? Math.round(d.scrollSum / d.scrollCount) : 0,
      sizeSelects: Object.fromEntries(d.sizeSelects),
    }))
    .sort((a, b) => a.date.localeCompare(b.date))

  const totalViews = daily.reduce((s, d) => s + d.views, 0)
  const totalClicks = daily.reduce((s, d) => s + d.etsyClicks, 0)

  return NextResponse.json({
    posterId,
    days,
    totals: {
      views: totalViews,
      etsyClicks: totalClicks,
      ctr: totalViews > 0 ? Math.round((totalClicks / totalViews) * 10000) / 100 : 0,
    },
    daily,
  })
}
```

**Step 2: Commit**

```bash
git add src/app/api/analytics/poster/
git commit -m "feat: per-poster analytics API endpoint"
```

---

### Task 5: Frontend JS Tracker — `<Analytics />` Component

**Files:**
- Create: `/home/dovek/dev-database/Github/pinterest-service/src/components/Analytics.tsx`
- Modify: `/home/dovek/dev-database/Github/pinterest-service/src/app/layout.tsx`

**Step 1: Create the tracker component**

```typescript
'use client'

import { useEffect, useRef, useCallback } from 'react'
import { usePathname } from 'next/navigation'

function getSessionId(): string {
  if (typeof window === 'undefined') return ''
  let sid = document.cookie.match(/ds_sid=([^;]+)/)?.[1]
  if (!sid) {
    sid = crypto.randomUUID()
    document.cookie = `ds_sid=${sid};path=/;max-age=${30 * 60};SameSite=Lax`
  }
  return sid
}

function getDevice(): string {
  if (typeof window === 'undefined') return 'desktop'
  const w = window.innerWidth
  if (w < 768) return 'mobile'
  if (w < 1024) return 'tablet'
  return 'desktop'
}

function getReferrer(): string {
  if (typeof document === 'undefined') return ''
  const ref = document.referrer
  if (!ref || ref.includes(window.location.hostname)) return ''
  return ref
}

type AnalyticsEvent = {
  type: string
  path: string
  posterId?: number
  data?: Record<string, any>
  sessionId: string
  device: string
  referrer?: string
}

const queue: AnalyticsEvent[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

function flush() {
  if (queue.length === 0) return
  const batch = queue.splice(0, 50)
  const payload = JSON.stringify({ events: batch })
  if (navigator.sendBeacon) {
    navigator.sendBeacon('/api/analytics/event', new Blob([payload], { type: 'application/json' }))
  } else {
    fetch('/api/analytics/event', { method: 'POST', body: payload, headers: { 'Content-Type': 'application/json' }, keepalive: true }).catch(() => {})
  }
}

function scheduleFlush() {
  if (flushTimer) return
  flushTimer = setTimeout(() => {
    flushTimer = null
    flush()
  }, 5000)
}

export function trackEvent(type: string, extra?: { posterId?: number; data?: Record<string, any> }) {
  queue.push({
    type,
    path: typeof window !== 'undefined' ? window.location.pathname : '/',
    posterId: extra?.posterId,
    data: extra?.data,
    sessionId: getSessionId(),
    device: getDevice(),
    referrer: getReferrer(),
  })
  scheduleFlush()
}

export function Analytics() {
  const pathname = usePathname()
  const startTime = useRef(Date.now())
  const scrollTracked = useRef(new Set<number>())

  // Page view on route change
  useEffect(() => {
    startTime.current = Date.now()
    scrollTracked.current.clear()
    trackEvent('page_view')
  }, [pathname])

  // Scroll depth tracking
  useEffect(() => {
    const handleScroll = () => {
      const scrollPct = Math.round(
        ((window.scrollY + window.innerHeight) / document.documentElement.scrollHeight) * 100
      )
      for (const threshold of [25, 50, 75, 100]) {
        if (scrollPct >= threshold && !scrollTracked.current.has(threshold)) {
          scrollTracked.current.add(threshold)
          trackEvent('scroll_depth', { data: { depth: threshold } })
        }
      }
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [pathname])

  // Time on page + flush on leave
  useEffect(() => {
    const handleUnload = () => {
      const seconds = Math.round((Date.now() - startTime.current) / 1000)
      if (seconds > 1) {
        trackEvent('time_on_page', { data: { seconds } })
      }
      flush()
    }
    window.addEventListener('beforeunload', handleUnload)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') handleUnload()
    })
    return () => {
      window.removeEventListener('beforeunload', handleUnload)
    }
  }, [pathname])

  return null
}
```

**Step 2: Add `<Analytics />` to layout.tsx**

In `/home/dovek/dev-database/Github/pinterest-service/src/app/layout.tsx`, add import and component:

```typescript
import { Analytics } from '@/components/Analytics'
```

Add `<Analytics />` inside `<body>` after `<Footer />`:

```tsx
<Footer />
<Analytics />
```

**Step 3: Commit**

```bash
git add src/components/Analytics.tsx src/app/layout.tsx
git commit -m "feat: client-side analytics tracker with batched beacon"
```

---

### Task 6: Wire Tracking into Existing Components

**Files:**
- Modify: `/home/dovek/dev-database/Github/pinterest-service/src/components/BuyOnEtsy.tsx`
- Modify: `/home/dovek/dev-database/Github/pinterest-service/src/components/SizeSelector.tsx`
- Modify: `/home/dovek/dev-database/Github/pinterest-service/src/components/ImageGallery.tsx`
- Modify: `/home/dovek/dev-database/Github/pinterest-service/src/components/CollectionCard.tsx`

**Step 1: Add trackEvent import to each component**

In each file, add:
```typescript
import { trackEvent } from './Analytics'
```

**Step 2: BuyOnEtsy — track etsy_click**

In the existing `handleClick` function, add before the `window.open`:
```typescript
trackEvent('etsy_click', {
  posterId: posterId ? Number(posterId) : undefined,
  data: { source, selectedSize, price: selectedPrice }
})
```

**Step 3: SizeSelector — track size_select**

In the size button onClick handler, add:
```typescript
trackEvent('size_select', {
  posterId: posterId ? Number(posterId) : undefined,
  data: { size: sizeKey, price }
})
```

Note: `posterId` prop needs to be added to SizeSelector if not already present. Check the component and thread it through from ProductInfo.

**Step 4: ImageGallery — track gallery_interact**

In the thumbnail click handler and arrow navigation, add:
```typescript
trackEvent('gallery_interact', {
  data: { imageIndex: newIndex }
})
```

**Step 5: CollectionCard — track collection_click**

Wrap the Link's onClick:
```typescript
<Link
  href={`/collections/${collection.slug}`}
  onClick={() => trackEvent('collection_click', { data: { collectionId: collection.id } })}
  ...
>
```

Note: CollectionCard is currently a server component. Adding onClick requires converting to `'use client'` or wrapping the tracking in a client wrapper. Simplest: add `'use client'` directive since it already uses client-side PosterImage.

**Step 6: Commit**

```bash
git add src/components/BuyOnEtsy.tsx src/components/SizeSelector.tsx src/components/ImageGallery.tsx src/components/CollectionCard.tsx
git commit -m "feat: wire trackEvent into product interaction components"
```

---

### Task 7: Daily Aggregation Cron

**Files:**
- Create: `/home/dovek/dev-database/Github/pinterest-service/src/app/api/analytics/aggregate/route.ts`

**Step 1: Create aggregation endpoint (called by external cron or poster-generator)**

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { validateApiKey, unauthorizedResponse } from '@/lib/api-auth'
import { prisma } from '@/lib/prisma'

export async function POST(request: NextRequest) {
  if (!validateApiKey(request)) {
    return unauthorizedResponse()
  }

  // Aggregate yesterday's events into DailyStats
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  const dateStr = yesterday.toISOString().slice(0, 10)
  const dayStart = new Date(dateStr + 'T00:00:00Z')
  const dayEnd = new Date(dateStr + 'T23:59:59.999Z')

  const events = await prisma.analyticsEvent.findMany({
    where: { createdAt: { gte: dayStart, lte: dayEnd } },
  })

  // Group by path + posterId
  const groups = new Map<string, typeof events>()
  for (const e of events) {
    const key = `${e.path}|${e.posterId ?? ''}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(e)
  }

  let aggregated = 0
  for (const [key, groupEvents] of groups) {
    const [path, posterIdStr] = key.split('|')
    const posterId = posterIdStr ? Number(posterIdStr) : null

    const pageViews = groupEvents.filter(e => e.eventType === 'page_view').length
    const etsyClicks = groupEvents.filter(e => e.eventType === 'etsy_click').length
    const uniqueVisitors = new Set(groupEvents.map(e => e.sessionId)).size

    const timeEvents = groupEvents.filter(e => e.eventType === 'time_on_page')
    const avgTimeOnPage = timeEvents.length > 0
      ? timeEvents.reduce((s, e) => s + ((e.data ? JSON.parse(e.data).seconds : 0) || 0), 0) / timeEvents.length
      : 0

    const scrollEvents = groupEvents.filter(e => e.eventType === 'scroll_depth')
    const avgScrollDepth = scrollEvents.length > 0
      ? scrollEvents.reduce((s, e) => s + ((e.data ? JSON.parse(e.data).depth : 0) || 0), 0) / scrollEvents.length
      : 0

    await prisma.dailyStats.upsert({
      where: { date_path_posterId: { date: dateStr, path, posterId } },
      create: { date: dateStr, path, posterId, pageViews, etsyClicks, uniqueVisitors, avgTimeOnPage, avgScrollDepth },
      update: { pageViews, etsyClicks, uniqueVisitors, avgTimeOnPage, avgScrollDepth },
    })
    aggregated++
  }

  // Prune raw events older than 30 days
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
  const deleted = await prisma.analyticsEvent.deleteMany({
    where: { createdAt: { lt: thirtyDaysAgo } },
  })

  return NextResponse.json({ aggregated, pruned: deleted.count, date: dateStr })
}
```

**Step 2: Commit**

```bash
git add src/app/api/analytics/aggregate/
git commit -m "feat: daily analytics aggregation + event pruning endpoint"
```

---

### Task 8: Poster-Generator — DovShop Analytics Backend

**Files:**
- Create: `/home/dovek/dev-database/Github/poster-generator/backend/routes/dovshop_analytics.py`
- Modify: `/home/dovek/dev-database/Github/poster-generator/backend/main.py` (register router)

**Step 1: Create dovshop_analytics route**

```python
import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dovshop-analytics"])

DOVSHOP_URL = os.environ.get("DOVSHOP_API_URL", "http://localhost:3000/api").rstrip("/")
DOVSHOP_KEY = os.environ.get("DOVSHOP_API_KEY", "")
PROD_DOVSHOP_URL = os.environ.get("DOVSHOP_PROD_URL", "https://dovshop.org/api").rstrip("/")

# In-memory cache
_cache: dict = {}
_cache_time: Optional[datetime] = None
CACHE_TTL = 3600  # 1 hour


async def _fetch_dovshop_analytics(days: int = 7) -> dict:
    """Fetch analytics summary from DovShop production."""
    url = f"{PROD_DOVSHOP_URL}/analytics/summary?days={days}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"x-api-key": DOVSHOP_KEY})
        resp.raise_for_status()
        return resp.json()


@router.get("/dovshop/analytics")
async def get_dovshop_analytics(days: int = 7, force: bool = False):
    """Get cached DovShop analytics. Use force=true to refresh."""
    global _cache, _cache_time

    cache_key = f"summary_{days}"
    if not force and cache_key in _cache and _cache_time:
        age = (datetime.utcnow() - _cache_time).total_seconds()
        if age < CACHE_TTL:
            return _cache[cache_key]

    try:
        data = await _fetch_dovshop_analytics(days)
        _cache[cache_key] = data
        _cache_time = datetime.utcnow()
        return data
    except Exception as e:
        logger.error("Failed to fetch DovShop analytics: %s", e)
        if cache_key in _cache:
            return _cache[cache_key]
        raise HTTPException(status_code=502, detail=f"DovShop analytics unavailable: {e}")


@router.post("/dovshop/analytics/sync")
async def sync_dovshop_analytics():
    """Manually trigger analytics sync from DovShop."""
    global _cache, _cache_time
    try:
        data = await _fetch_dovshop_analytics(30)
        _cache["summary_30"] = data
        _cache_time = datetime.utcnow()

        # Also trigger aggregation on DovShop
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                f"{PROD_DOVSHOP_URL}/analytics/aggregate",
                headers={"x-api-key": DOVSHOP_KEY},
            )

        return {"status": "ok", "period": data.get("period"), "pageViews": data.get("totals", {}).get("pageViews")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/dovshop/analytics/poster/{printify_product_id}")
async def get_dovshop_poster_analytics(printify_product_id: str, days: int = 30):
    """Get per-poster DovShop analytics by Printify ID."""
    import database as db

    product = await db.get_product_by_printify_id(printify_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    dovshop_id = product.get("dovshop_product_id")
    if not dovshop_id:
        return {"posterId": None, "days": days, "totals": {"views": 0, "etsyClicks": 0, "ctr": 0}, "daily": []}

    try:
        url = f"{PROD_DOVSHOP_URL}/analytics/poster/{dovshop_id}?days={days}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"x-api-key": DOVSHOP_KEY})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Failed to fetch poster analytics: %s", e)
        return {"posterId": dovshop_id, "days": days, "totals": {"views": 0, "etsyClicks": 0, "ctr": 0}, "daily": []}
```

**Step 2: Register router in main.py**

In `/home/dovek/dev-database/Github/poster-generator/backend/main.py`, add:

```python
from routes.dovshop_analytics import router as dovshop_analytics_router
app.include_router(dovshop_analytics_router)
```

Follow the same pattern used for other routers (check `main.py` for exact import style).

**Step 3: Add DOVSHOP_PROD_URL to .env**

```
DOVSHOP_PROD_URL=https://dovshop.org/api
```

**Step 4: Commit**

```bash
git add backend/routes/dovshop_analytics.py backend/main.py .env
git commit -m "feat: DovShop analytics proxy routes for poster-generator"
```

---

### Task 9: Poster-Generator — DovShop Monitor Tab (Frontend)

**Files:**
- Create: `/home/dovek/dev-database/Github/poster-generator/frontend/app/monitor/dovshop/page.tsx`
- Modify: `/home/dovek/dev-database/Github/poster-generator/frontend/app/monitor/layout.tsx`

**Step 1: Add "DovShop" tab to monitor layout**

In the tabs array in `/home/dovek/dev-database/Github/poster-generator/frontend/app/monitor/layout.tsx`, add:

```typescript
{ href: '/monitor/dovshop', label: 'DovShop' },
```

**Step 2: Create the DovShop dashboard page**

Build the page with these sections following existing dashboard patterns (custom Tailwind charts, no libraries):

1. **Overview cards row**: Visitors, Etsy Clicks, CTR, Avg Time — using the same card style as `/dashboard`
2. **Line chart**: Daily views + clicks over 30 days — same bar/line pattern as ViewsChart
3. **Top posters table**: Sortable table — same pattern as analytics table
4. **Sources pie**: Simple horizontal stacked bar (referrer breakdown)
5. **Devices**: 3-column mobile/desktop/tablet percentages
6. **Funnel**: page_view → poster_view → size_select → etsy_click with conversion %

Data fetching: `useEffect` calling `GET /dovshop/analytics?days=30` on mount, with loading/error states.

The page should be a `'use client'` component with:
- `useState` for data, loading, error, selected period (7/30 days)
- Period toggle buttons (7d / 30d)
- Manual sync button calling `POST /dovshop/analytics/sync`

**Step 3: Commit**

```bash
git add frontend/app/monitor/dovshop/ frontend/app/monitor/layout.tsx
git commit -m "feat: DovShop analytics dashboard in /monitor/dovshop"
```

---

### Task 10: Build & Deploy

**Step 1: Build DovShop (pinterest-service)**

```bash
cd /home/dovek/dev-database/Github/pinterest-service
export PATH="/home/dovek/.nvm/versions/node/v22.20.0/bin:$PATH"
npx next build
```

Expected: All pages compile successfully.

**Step 2: Build poster-generator frontend**

```bash
cd /home/dovek/dev-database/Github/poster-generator/frontend
npm run build
```

**Step 3: Push both repos**

```bash
cd /home/dovek/dev-database/Github/pinterest-service && git push origin main
cd /home/dovek/dev-database/Github/poster-generator && git push origin main
```

**Step 4: Verify on production**

```bash
# Test event ingestion
curl -X POST "https://dovshop.org/api/analytics/event" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"type":"page_view","path":"/test","sessionId":"test-deploy","device":"desktop"}]}'

# Test summary
curl -s "https://dovshop.org/api/analytics/summary?days=1" \
  -H "x-api-key: $DOVSHOP_API_KEY"

# Test poster-generator proxy
curl -s "http://localhost:8001/dovshop/analytics?days=1"
```

**Step 5: Final commit if any fixes needed**
