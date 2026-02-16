# Printify Image Flow: Skip Auto-Mockups on Publish

**Date:** 2026-02-16
**Status:** Approved

## Problem

When a product is published via Printify, it sends ~15-20 auto-generated mockup images to Etsy. Our system then replaces them with custom-composed mockups 1-5 minutes later. During this window, buyers see low-quality Printify mockups.

## Solution

Publish with `"images": false` when custom mockups are already composed. Upload our mockups directly to Etsy after getting the listing ID — buyers never see Printify auto-mockups.

## Flow

```
1. Check if mockups ready (mockup_status == "approved" + is_included mockups exist)
2. If yes → publish_product(sync_images=False)
   If no  → publish_product(sync_images=True) [fallback to current behavior]
3. Poll for Etsy listing ID (same as before)
4. Fill metadata, fix description (same as before)
5. Upload our mockups directly to Etsy
   - When sync_images=False: no old images to delete, just upload
   - When sync_images=True: delete old → upload new (current behavior)
```

## Changes

### 1. `backend/printify.py` — `publish_product()`
- Add `sync_images: bool = True` parameter
- Pass `"images": sync_images` in payload

### 2. `backend/scheduler.py` — publish functions
- `publish_now()`: check mockup readiness → set `sync_images`
- `_check_and_publish()`: same logic
- `_post_publish_etsy_setup()`: accept `sync_images` flag, pass to upload function

### 3. `backend/routes/mockups.py` — `_upload_multi_images_to_etsy()`
- Add `has_existing_images: bool = True` parameter
- When `False`: skip get/delete old images, just upload new ones at rank 1..N

### 4. `backend/routes/printify_routes.py` — manual publish endpoint
- Same mockup readiness check → set `sync_images`

### Mockup readiness check (shared helper)
```python
async def check_mockups_ready(printify_product_id: str) -> bool:
    """Return True if product has approved, included mockups."""
    product = await db.get_product_by_printify_id(printify_product_id)
    if not product or product.get("mockup_status") != "approved":
        return False
    source_image_id = product.get("source_image_id")
    if not source_image_id:
        return False
    mockups = await db.get_image_mockups(source_image_id)
    included = [m for m in mockups if m.get("is_included", True)]
    return len(included) > 0
```

## Fallback

- If mockups not composed → `sync_images=True` (current behavior, safe)
- If Etsy rejects listing without images → retry with `sync_images=True`
