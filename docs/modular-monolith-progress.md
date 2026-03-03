# Modular Monolith Restructure — Progress Report

**Branch:** `refactor/modular-monolith`
**Date:** 2026-03-03
**Status:** Phases 1–6 complete, Docker build passes, health check OK

---

## Completed Phases

### Phase 1 — Create `integrations/` structure, move clean modules

Moved 7 modules to `integrations/` with backward-compat shims at old locations:

| Old path | New path | LOC |
|---|---|---|
| `telegram_bot.py` | `integrations/telegram/bot.py` | 598 |
| `notifications.py` | `integrations/telegram/notifications.py` | 157 |
| `leonardo.py` | `integrations/leonardo/client.py` | 261 |
| `dovshop_client.py` | `integrations/dovshop/client.py` | 271 |
| `dovshop_ai.py` | `integrations/dovshop/ai.py` | 208 |
| `etsy_autocomplete.py` | `integrations/etsy/autocomplete.py` | 120 |
| `etsy_search_validator.py` | `integrations/etsy/search_validator.py` | 152 |

**Commit:** `b6cf0a5`

### Phase 2 — Extract business logic from routes to `core/`

Created two new core modules to break the `scheduler.py ← routes.*` coupling:

| New file | Functions | Source |
|---|---|---|
| `core/mockups/compose.py` (377 LOC) | `compose_all_templates`, `upload_multi_images_to_etsy`, + 6 helpers | `routes/mockup_utils.py` |
| `core/products_service.py` (35 LOC) | `import_printify_product` | `routes/products.py` |

**Impact:** `scheduler.py` had 4 late imports from `routes.*` → now has **zero**.

Updated backward-compat re-exports:
- `routes/mockup_utils.py` — re-exports from `core/mockups/compose`, keeps only Pydantic models
- `routes/products.py` — re-exports `_import_printify_product` from `core/products_service`

### Phase 3 — Move Etsy client + sync

| Old path | New path | LOC |
|---|---|---|
| `etsy.py` | `integrations/etsy/client.py` | 605 |
| `etsy_sync.py` | `integrations/etsy/sync.py` | 169 |

Cross-references fixed inside `integrations/etsy/sync.py`:
- `from etsy import EtsyAPI` → `from integrations.etsy.client import EtsyAPI`
- `from printify import PrintifyAPI` → `from integrations.printify.client import PrintifyAPI`

### Phase 4 — Move Printify client

| Old path | New path | LOC |
|---|---|---|
| `printify.py` | `integrations/printify/client.py` | 522 |

---

## Current File Structure

```
backend/
├── integrations/
│   ├── dovshop/       client.py, ai.py
│   ├── etsy/          client.py, sync.py, autocomplete.py, search_validator.py
│   ├── leonardo/      client.py
│   ├── printify/      client.py
│   ├── pinterest/     (empty, placeholder)
│   └── telegram/      bot.py, notifications.py
├── core/
│   ├── mockups/       compose.py
│   ├── products_service.py
│   └── seo/           prompts.py, generator.py, scheduler.py
├── routes/            (unchanged — 20 modules, Pydantic models stay here)
├── etsy.py            → shim → integrations/etsy/client
├── etsy_sync.py       → shim → integrations/etsy/sync
├── printify.py        → shim → integrations/printify/client
├── telegram_bot.py    → shim → integrations/telegram/bot
├── notifications.py   → shim → integrations/telegram/notifications
├── leonardo.py        → shim → integrations/leonardo/client
├── dovshop_client.py  → shim → integrations/dovshop/client
├── dovshop_ai.py      → shim → integrations/dovshop/ai
├── etsy_autocomplete.py → shim → integrations/etsy/autocomplete
├── etsy_search_validator.py → shim → integrations/etsy/search_validator
├── prompts.py           → shim → core/seo/prompts
├── listing_generator.py → shim → core/seo/generator
└── seo_scheduler.py     → shim → core/seo/scheduler
```

## Backward Compatibility

All 13 shim files follow the same pattern:
```python
# Backward compatibility — module moved to integrations/X/Y.py
from integrations.X.Y import *  # noqa: F401,F403
from integrations.X.Y import ClassName  # noqa: F401
```

Every existing import in the codebase continues to work. No route files were changed except `mockup_utils.py` and `products.py` (which now delegate to `core/`).

## Verification

- Docker build: **passes**
- Health check: `{"status": "healthy", "database": "ok"}`
- Products endpoint: **OK** (4 returned)
- Analytics sync-status: **OK**
- `scheduler.py` route imports: **0** (was 4)
- `deps.py` monkey-patching: **0** (was 3 lines)
- `subprocess.run` in business logic: **0** (was 2 calls)
- Backward-compat shims: **13** total
- No functionality changes — pure structural refactor

### Phase 5 — Move SEO modules to `core/seo/`

| Old path | New path | LOC |
|---|---|---|
| `prompts.py` | `core/seo/prompts.py` | 309 |
| `listing_generator.py` | `core/seo/generator.py` | 636 |
| `seo_scheduler.py` | `core/seo/scheduler.py` | 124 |

Fixed internal import: `core/seo/generator.py` → `from core.seo.prompts import ...`

### Phase 6 — Fix deps.py DI + async subprocess

**deps.py cleanup:**
- All imports now use `from integrations.*` and `from core.*` paths (8 clean imports)
- Reordered singleton creation: `etsy` and `etsy_sync` created before `publish_scheduler`
- Eliminated monkey-patching: `publish_scheduler = PublishScheduler(printify=..., notifier=..., etsy=..., listing_gen=..., etsy_sync=...)`

**upscaler.py async:**
- `upscale_with_realesrgan()`: `subprocess.run` → `asyncio.create_subprocess_exec` with timeout
- `UpscaleService.upscale_to_target()`: `def` → `async def`
- Updated 3 callers: `routes/dpi.py`, `routes/printify_routes.py`, `export.py` — added `await`
- `is_realesrgan_available()` remains sync (one-time startup check, acceptable)

## Remaining Phases

| Phase | Description | Status |
|---|---|---|
| 7 | Clean up old shim files (optional) | Pending |
