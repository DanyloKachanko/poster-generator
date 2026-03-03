# Architecture Analysis Report — DovShop Backend

Date: 2026-03-03

## Current Structure Overview

```
backend/
  auth.py                   (54 LOC)  — HMAC token auth, REQUIRE_AUTH flag
  batch.py                  (304)     — BatchManager for bulk Leonardo generations
  categorizer.py            (201)     — Auto-categorization for DovShop sync
  config.py                 (569)     — STYLE_PRESETS, SIZES, MODELS, MOCKUP_SCENES
  database.py               (3)       — Re-export shim → db/
  db/
    __init__.py             (17)      — Re-exports all db modules
    analytics.py            (283)     — product_analytics CRUD
    competitors.py          (205)     — competitors + competitor_listings
    connection.py           (459)     — Pool init, CREATE TABLE migrations
    generations.py          (267)     — generations + generated_images + credits
    mockups.py              (349)     — image_mockups, mockup_templates, packs
    products.py             (166)     — products table CRUD
    schedule.py             (322)     — scheduled_products, used_presets, settings
    seo.py                  (133)     — seo_refresh_log, autocomplete_cache
    settings.py             (85)      — etsy_tokens, app_settings
    strategy.py             (38)      — ai_strategy_history
    tasks.py                (99)      — background_tasks
  deps.py                   (50)      — Service singletons (all instantiated here)
  description_utils.py      (109)     — Description text helpers
  dovshop_ai.py             (208)     — Claude-powered product enrichment
  dovshop_client.py         (271)     — DovShop REST API client class
  dpi.py                    (201)     — DPI analysis + size recommendations
  etsy.py                   (605)     — EtsyAPI class (OAuth PKCE, all API calls)
  etsy_autocomplete.py      (120)     — Google autocomplete for Etsy keywords
  etsy_search_validator.py  (152)     — Validates tags via Etsy search
  etsy_sync.py              (169)     — EtsySyncService (views/favs/orders sync)
  export.py                 (125)     — PosterExporter (multi-size export)
  leonardo.py               (261)     — LeonardoAI class (generation, upscale)
  listing_generator.py      (636)     — ListingGenerator (Claude SEO text gen)
  main.py                   (128)     — FastAPI app, middleware, router registration
  notifications.py          (157)     — NotificationService (Telegram messages)
  pod_providers.py          (204)     — Print provider comparison data
  presets.py                (444)     — Preset resolution + trending logic
  presets_manager.py        (284)     — Custom preset uploads + generation
  pricing.py                (98)      — Price calculation per size
  printify.py               (522)     — PrintifyAPI class (products, images, publish)
  prompt_library.py         (158)     — Curated prompt collection
  prompts.py                (309)     — SEO prompt templates + STYLE_KEYWORDS
  scheduler.py              (1012)    — PublishScheduler (APScheduler, 6 jobs)
  seasonal_calendar.py      (421)     — Holiday/seasonal event calendar
  seo_scheduler.py          (124)     — SEO validation scheduler
  sizes.py                  (56)      — Print sizes + Printify scale factors
  telegram_bot.py           (598)     — TelegramBot (long-poll commands)
  upscaler.py               (158)     — Image upscaling (realesrgan / PIL)
  routes/
    analytics.py            (344)     — Dashboard stats, Etsy analytics
    auth_routes.py          (19)      — Login endpoint
    batch.py                (80)      — Batch generation
    calendar.py             (67)      — Seasonal calendar
    competitors.py          (241)     — Competitor tracking
    custom_presets.py       (105)     — Custom preset CRUD
    dovshop.py              (726)     — DovShop push, sync, AI enrich, collections
    dovshop_analytics.py    (169)     — DovShop analytics sync
    dpi.py                  (100)     — DPI analysis endpoints
    etsy_auth.py            (325)     — Etsy OAuth flow + token management
    etsy_listings.py        (668)     — Etsy listing CRUD, SEO tools, images
    etsy_routes.py          (5)       — Empty (deprecated)
    export.py               (88)      — Size export
    generation.py           (316)     — Image generation, history
    library.py              (38)      — Prompt library
    listings.py             (319)     — Full product creation pipeline
    mockup_compose.py       (248)     — Scene generation + poster composition
    mockup_templates.py     (427)     — Template/pack CRUD, color grades
    mockup_utils.py         (403)     — Composition engine, Etsy upload helpers
    mockup_workflow.py      (860)     — Approve/decline/reapply workflow
    mockups.py              (9)       — Empty redirect
    pipeline.py             (408)     — Auto-product + preset-product pipelines
    presets.py              (75)      — Preset listing + categories
    printify_routes.py      (913)     — Printify products, publish, upgrade, fix
    products.py             (564)     — Product CRUD, mockup management, SEO refresh
    schedule.py             (244)     — Publish queue management
    seo_routes.py           (310)     — SEO validation, autocomplete, bulk checks
    strategy.py             (640)     — Strategy plans, AI generation, execution
    sync_etsy.py            (90)      — Etsy sync trigger
    sync_ui.py              (211)     — Etsy ↔ Printify link/unlink UI
```

**Totals:** 75 Python files, ~20,146 LOC (excluding venv), 27 route modules, ~170 endpoints

---

## External Integrations Map

| Service | Files Involved | Auth Method | Async? | Client Class? | Rate Limit Handling? |
|---------|---------------|-------------|--------|---------------|---------------------|
| **Etsy API v3** | etsy.py, etsy_sync.py, etsy_auth routes, etsy_listings routes, scheduler.py, + 15 more | OAuth2 PKCE + token refresh | Yes (httpx) | `EtsyAPI` class | Manual `asyncio.sleep(0.5)` in loops |
| **Leonardo AI** | leonardo.py, batch.py, export.py, generation routes, mockup_compose routes, pipeline routes | API key (Bearer) | Yes (httpx) | `LeonardoAI` class | Polling with sleep for generation status |
| **Printify** | printify.py, scheduler.py, listings routes, printify_routes, pipeline routes, + 10 more | API token (Bearer) | Yes (httpx) | `PrintifyAPI` class | No explicit handling |
| **Anthropic/Claude** | listing_generator.py, dovshop_ai.py, etsy_listings routes, seo_routes | API key | Yes (httpx) | `ListingGenerator` class | `asyncio.sleep(2)` between calls |
| **Telegram Bot** | telegram_bot.py, notifications.py | Bot token | Yes (httpx) | `TelegramBot` + `NotificationService` | No explicit handling |
| **Google Autocomplete** | etsy_autocomplete.py, etsy_search_validator.py, seo_routes | None (public endpoint) | Yes (httpx) | `EtsyAutocompleteChecker` | Cache in DB (autocomplete_cache table) |
| **DovShop API** | dovshop_client.py, dovshop_ai.py, dovshop routes, scheduler.py | API key (Bearer) | Yes (httpx) | `DovShopClient` class | No explicit handling |

**Good news:** All HTTP calls use `httpx.AsyncClient` — zero blocking `requests.*` calls found.

---

## Dependency Graph

```
deps.py (singleton factory)
  ├── leonardo: LeonardoAI
  ├── exporter: PosterExporter ← leonardo
  ├── listing_gen: ListingGenerator ← anthropic key
  ├── printify: PrintifyAPI
  ├── notifier: NotificationService ← telegram key
  ├── publish_scheduler: PublishScheduler ← printify, notifier, etsy, listing_gen, etsy_sync
  ├── etsy: EtsyAPI
  ├── etsy_sync: EtsySyncService ← etsy, printify
  ├── batch_manager: BatchManager ← notifier
  ├── upscale_service: UpscaleService
  ├── presets_manager: PresetsManager
  ├── dovshop_client: DovShopClient
  └── telegram_bot: TelegramBot

main.py (lifespan)
  ├── db.init_db()
  ├── publish_scheduler.start()  ← starts APScheduler (6 cron/interval jobs)
  └── telegram_bot.start()       ← starts long-polling loop
```

### Tightly Coupled Endpoints (3+ external services)

| File | Services | LOC | Coupling Description |
|------|----------|-----|---------------------|
| **routes/pipeline.py** | Leonardo + Printify + Etsy + Claude + Notifier | 408 | Full product pipeline: generate → upscale → create Printify → schedule Etsy → notify |
| **routes/listings.py** | Printify + Etsy + Claude + Notifier | 319 | Product creation: generate listing → upload → create product → schedule |
| **routes/strategy.py** | Leonardo + Printify + Claude + Etsy | 640 | Strategy execution: plan → generate → create → schedule |
| **routes/dovshop.py** | DovShop + Etsy + Printify | 726 | DovShop sync pulls data from Printify + Etsy to push to DovShop |
| **routes/products.py** | Printify + Etsy + Claude | 564 | Product management crosses Printify/Etsy boundaries |
| **routes/mockup_workflow.py** | Etsy + Printify + DovShop | 860 | Mockup approval uploads to Etsy, updates DovShop |
| **scheduler.py** | Printify + Etsy + Claude + DovShop + Notifier | 1012 | **Highest coupling** — `_post_publish_etsy_setup` touches ALL services |

### Clean Boundaries (already modular, easy to extract)

| Module | Why it's clean |
|--------|---------------|
| `telegram_bot.py` + `notifications.py` | Only talks to Telegram API + DB. No imports from other services. |
| `leonardo.py` | Pure API client. No imports from other services. |
| `dovshop_client.py` | Pure API client. No cross-service imports. |
| `dovshop_ai.py` | Only uses Anthropic (httpx direct). No other service imports. |
| `etsy_autocomplete.py` + `etsy_search_validator.py` | Standalone Google/Etsy scraping. |
| `seasonal_calendar.py` | Pure data, no external calls. |
| `prompt_library.py` | Pure data/config. |
| `categorizer.py` | Pure logic (imports only `prompts.py`). |

---

## Database Table Ownership

| Table | DB Module | Used By Routes | Domain |
|-------|-----------|---------------|--------|
| `generations` | db/generations.py | generation, batch, pipeline | Core |
| `generated_images` | db/generations.py | generation, mockup_workflow, products | Core |
| `credit_usage` | db/generations.py | generation | Core |
| `products` | db/products.py | products, dovshop, pipeline, schedule, seo | Core |
| `product_analytics` | db/analytics.py | analytics, dovshop_analytics | Analytics |
| `scheduled_products` | db/schedule.py | schedule, scheduler | Scheduling |
| `used_presets` | db/schedule.py | schedule, strategy | Scheduling |
| `schedule_settings` | db/schedule.py | schedule | Scheduling |
| `calendar_event_products` | db/schedule.py | calendar | Scheduling |
| `etsy_tokens` | db/settings.py | etsy_auth | Etsy |
| `app_settings` | db/settings.py | mockup_templates, scheduler | Core |
| `seo_refresh_log` | db/seo.py | seo_routes, scheduler | SEO |
| `autocomplete_cache` | db/seo.py | seo_routes | SEO |
| `competitors` | db/competitors.py | competitors | Competitors |
| `competitor_listings` | db/competitors.py | competitors | Competitors |
| `competitor_listing_stats` | db/competitors.py | competitors | Competitors |
| `competitor_snapshots` | db/competitors.py | competitors | Competitors |
| `mockup_templates` | db/mockups.py | mockup_templates, mockup_compose | Mockups |
| `image_mockups` | db/mockups.py | mockup_workflow, scheduler | Mockups |
| `mockup_packs` | db/mockups.py | mockup_templates | Mockups |
| `mockup_pack_templates` | db/mockups.py | mockup_templates, scheduler | Mockups |
| `strategy_plans` | db/strategy.py (schema in connection.py) | strategy | Strategy |
| `strategy_items` | db/strategy.py (schema in connection.py) | strategy | Strategy |
| `background_tasks` | db/tasks.py | listings, strategy, mockup_workflow | Core |
| `ai_strategy_history` | db/strategy.py | dovshop | Strategy |

**25 tables** across 11 db modules. Schema migrations are all in `db/connection.py` (inline CREATE TABLE IF NOT EXISTS).

---

## Scheduler Analysis

| Job | Frequency | Services Used | Description |
|-----|-----------|--------------|-------------|
| `_check_and_publish` | Every 5 min | Printify, Etsy, DovShop, Claude, Notifier | Publish due items, post-publish Etsy setup, auto-push to DovShop |
| `_send_daily_summary` | Daily 9:00 EST | Notifier | Telegram morning digest |
| `_guard_descriptions` | Twice daily (6:00/18:00 UTC) | Etsy | Re-apply descriptions if Printify overwrote them |
| `_catchup_mockups` | Every 5 min | Printify, Etsy | Fill missing etsy_listing_ids, compose + upload mockups |
| `_auto_seo_refresh` | Weekly (Mon 11:00 UTC) | Etsy, Claude, Notifier | Regenerate SEO for low-view listings |
| `_auto_etsy_sync` | Every 6 hours | Etsy (via EtsySyncService) | Batch-fetch views/favorites/orders |

**Key concern:** The `PublishScheduler` class is 1012 LOC and is the **coupling nexus** — it directly uses Printify, Etsy, Claude, DovShop, and Notifier. It also imports from `routes.mockup_utils` and `routes.products` (circular-ish dependency).

---

## Async/Sync Issues

| File | Issue | Severity | Notes |
|------|-------|----------|-------|
| `upscaler.py:48,79` | `subprocess.run()` in async context | Medium | Calls realesrgan CLI. Wrapped in try/except with timeout, but blocks event loop. Should use `asyncio.create_subprocess_exec`. |
| `scheduler.py:510,550,719,796` | Late imports from `routes.mockup_utils` | Low | Functional but indicates architectural coupling (service layer importing from route layer). |
| `scheduler.py:719` | Late import from `routes.products` | Low | `_import_printify_product` function used in catchup — routes shouldn't be imported by services. |

**PIL/Image operations** in `listing_generator.py`, `printify.py`, `export.py`, `dpi.py`, `routes/mockup_compose.py`, `routes/mockup_utils.py`, `routes/printify_routes.py` — these are CPU-bound but typically operate on small images. Not a bottleneck at current scale.

---

## Proposed Modular Structure

```
backend/
  integrations/
    etsy/
      __init__.py
      client.py              — EtsyAPI class (from etsy.py)
      auth.py                — OAuth PKCE flow + token refresh (from routes/etsy_auth.py)
      sync.py                — EtsySyncService (from etsy_sync.py)
      listings.py            — Listing CRUD routes (from routes/etsy_listings.py)
      seo.py                 — SEO validation routes (from routes/seo_routes.py)
      autocomplete.py        — Google autocomplete (from etsy_autocomplete.py)
      search_validator.py    — Etsy search validation (from etsy_search_validator.py)
    pinterest/               — NEW
      __init__.py
      client.py              — Pinterest API v5 client
      generator.py           — AI pin content generation
      scheduler.py           — Posting queue
      routes.py              — /pinterest/* endpoints
    leonardo/
      __init__.py
      client.py              — LeonardoAI class (from leonardo.py)
      routes.py              — Generation endpoints (from routes/generation.py)
    printify/
      __init__.py
      client.py              — PrintifyAPI class (from printify.py)
      routes.py              — Printify endpoints (from routes/printify_routes.py)
    dovshop/
      __init__.py
      client.py              — DovShopClient (from dovshop_client.py)
      ai.py                  — AI enrichment (from dovshop_ai.py)
      routes.py              — DovShop endpoints (from routes/dovshop.py)
      analytics.py           — DovShop analytics (from routes/dovshop_analytics.py)
    telegram/
      __init__.py
      bot.py                 — TelegramBot (from telegram_bot.py)
      notifications.py       — NotificationService (from notifications.py)
  core/
    auth.py                  — HMAC token auth (from auth.py)
    deps.py                  — Service singletons (from deps.py)
    config.py                — All config (from config.py)
    scheduler.py             — PublishScheduler (from scheduler.py)
    seo/
      prompts.py             — SEO templates (from prompts.py)
      generator.py           — ListingGenerator (from listing_generator.py)
      scheduler.py           — SEO scheduler (from seo_scheduler.py)
    mockups/
      compose.py             — Composition engine (from routes/mockup_utils.py)
      workflow.py             — Approve/decline logic (from routes/mockup_workflow.py)
      templates.py           — Template CRUD (from routes/mockup_templates.py)
  db/                        — Keep as-is (already well-organized)
  routes/                    — Only thin route files that delegate to integrations/core
    products.py              — Product CRUD (stays — cross-cutting)
    pipeline.py              — Orchestration (stays — calls multiple services)
    strategy.py              — Strategy (stays — calls multiple services)
    listings.py              — Full product create (stays — orchestration)
    analytics.py             — Analytics (stays)
    schedule.py              — Queue management (stays)
    ...
```

---

## Migration Path

### Phase 1: Move clean modules (no refactoring needed)

These can be moved as-is with only import path changes:

| Current | Target | Effort |
|---------|--------|--------|
| `telegram_bot.py` | `integrations/telegram/bot.py` | Rename + update imports |
| `notifications.py` | `integrations/telegram/notifications.py` | Rename + update imports |
| `leonardo.py` | `integrations/leonardo/client.py` | Rename + update imports |
| `dovshop_client.py` | `integrations/dovshop/client.py` | Rename + update imports |
| `dovshop_ai.py` | `integrations/dovshop/ai.py` | Rename + update imports |
| `etsy_autocomplete.py` | `integrations/etsy/autocomplete.py` | Rename + update imports |
| `etsy_search_validator.py` | `integrations/etsy/search_validator.py` | Rename + update imports |

### Phase 2: Move with minor refactoring

| Current | Target | What needs fixing |
|---------|--------|-------------------|
| `etsy.py` | `integrations/etsy/client.py` | Move `ETSY_COLOR_*` constants with it |
| `printify.py` | `integrations/printify/client.py` | `DesignGroup` imported by `routes/dpi.py` — extract to shared models |
| `etsy_sync.py` | `integrations/etsy/sync.py` | Depends on both etsy + printify — inject via constructor |

### Phase 3: Extract route logic into service layer

The biggest problem: `routes/mockup_utils.py` contains business logic (`_compose_all_templates`, `_upload_multi_images_to_etsy`) that `scheduler.py` imports. This needs to be extracted to `core/mockups/compose.py` before the scheduler can be cleaned up.

| Current | Issue | Target |
|---------|-------|--------|
| `routes/mockup_utils.py` | Contains business logic imported by scheduler | Extract to `core/mockups/compose.py` |
| `routes/products.py:_import_printify_product` | Helper function imported by scheduler | Extract to `core/products.py` or `integrations/printify/sync.py` |
| `scheduler.py` | 1012 LOC god class — calls 5 services | Split into domain-specific schedulers or keep as orchestrator but inject clean interfaces |

### Phase 4: Add Pinterest module (new code, no migration)

Build `integrations/pinterest/` from scratch using the established patterns.

### What should stay in shared core

- `auth.py` — middleware used by all routes
- `deps.py` — singleton factory (but should be simplified)
- `config.py` — shared constants
- `db/` — database layer (already modular)
- `pricing.py`, `sizes.py` — shared product data
- `categorizer.py`, `prompts.py` — shared SEO logic

---

## Risks and Blockers

### 1. Scheduler reverse-imports from routes (HIGH)

`scheduler.py` imports from `routes.mockup_utils` and `routes.products`. This creates a circular dependency path: `main.py → routes → deps.py → scheduler.py → routes`. Currently works because imports are late (inside functions), but it's fragile.

**Fix:** Extract `_compose_all_templates`, `_upload_multi_images_to_etsy`, and `_import_printify_product` into service-layer modules.

### 2. `deps.py` monkey-patching (MEDIUM)

```python
publish_scheduler = PublishScheduler(printify, notifier)
publish_scheduler.etsy = etsy                    # ← monkey-patched after init
publish_scheduler.listing_gen = listing_gen       # ← monkey-patched after init
publish_scheduler.etsy_sync = etsy_sync           # ← monkey-patched after init
```

This is due to circular dependency at import time. Should be resolved with lazy initialization or dependency injection.

### 3. `ensure_etsy_token()` scattered everywhere (MEDIUM)

The `ensure_etsy_token()` function from `routes/etsy_auth.py` is called in 15+ route endpoints and even in `telegram_bot.py`. It handles token refresh + DB persistence. Should be a method on the EtsyAPI client itself.

### 4. `import database as db` used everywhere (LOW)

Every file imports the db module globally. This is fine for now but makes testing harder. Consider passing db functions via dependency injection for new modules.

### 5. No blocking sync calls (GOOD)

All HTTP is async via httpx. The only sync issue is `subprocess.run()` in `upscaler.py` (low frequency, acceptable).

---

## Estimated Effort

| Phase | What | Files Touched | Effort |
|-------|------|---------------|--------|
| 1 | Create `integrations/` structure, move clean modules (telegram, leonardo, dovshop, autocomplete) | ~15 files (moves + import updates) | Small — mechanical renames |
| 2 | Add Pinterest module (new code, no dependencies) | 4-5 new files | Medium — new integration |
| 3 | Extract business logic from routes to services (mockup_utils, products helper) | ~5 files | Medium — careful refactoring |
| 4 | Move Etsy + Printify clients to integrations/ | ~20 files (import updates) | Small — mechanical but many files |
| 5 | Refactor scheduler.py — clean up reverse imports, split or inject | 3-5 files | Medium-High — the scheduler is the coupling nexus |
| 6 | Clean up deps.py — proper DI, remove monkey-patching | 2-3 files | Small |

**Recommended order:** Phase 2 (Pinterest) can start immediately without any restructuring — just create `integrations/pinterest/` and wire it in. Phases 1/3-6 are the modular restructure and can be done incrementally.
