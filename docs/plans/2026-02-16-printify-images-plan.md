# Printify Image Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Skip Printify auto-mockups on publish when custom mockups are already composed, so buyers never see ugly placeholder images.

**Architecture:** Add a `sync_images` flag to the publish pipeline. Before publishing, check if the product has approved custom mockups. If yes, publish with `images: false` and upload our mockups directly to Etsy. If no, fall back to current behavior.

**Tech Stack:** Python/FastAPI, Printify API, Etsy API, asyncpg

---

### Task 1: Add `sync_images` parameter to `publish_product()`

**Files:**
- Modify: `backend/printify.py:196-214`

**Step 1: Update `publish_product()` signature and payload**

Change the method to accept `sync_images: bool = True` and use it in the payload:

```python
async def publish_product(self, product_id: str, sync_images: bool = True) -> dict:
    """Publish product to connected store (Etsy)."""
    payload = {
        "title": True,
        "description": True,
        "images": sync_images,
        "variants": True,
        "tags": True,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}/publish.json",
            headers=self.headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
```

**Step 2: Verify no other callers break**

Run: `grep -rn "publish_product" backend/`
All callers currently pass only `product_id`, so the default `sync_images=True` preserves existing behavior.

---

### Task 2: Add `_check_mockups_ready()` helper to scheduler

**Files:**
- Modify: `backend/scheduler.py` (add method to `PublishScheduler` class)

**Step 1: Add helper method after `_get_etsy_token()` (around line 310)**

```python
async def _check_mockups_ready(self, printify_product_id: str) -> bool:
    """Return True if product has approved, included mockups ready for Etsy."""
    try:
        product = await db.get_product_by_printify_id(printify_product_id)
        if not product or product.get("mockup_status") != "approved":
            return False
        source_image_id = product.get("source_image_id")
        if not source_image_id:
            return False
        mockups = await db.get_image_mockups(source_image_id)
        included = [m for m in mockups if m.get("is_included", True)]
        return len(included) > 0
    except Exception as e:
        logger.debug("Mockup readiness check failed for %s: %s", printify_product_id, e)
        return False
```

---

### Task 3: Update `publish_now()` to use `sync_images`

**Files:**
- Modify: `backend/scheduler.py:212-235`

**Step 1: Add mockup check before publish call**

Replace line 224 (`await self.printify.publish_product(printify_product_id)`) with:

```python
        # Skip Printify images if custom mockups are ready
        mockups_ready = await self._check_mockups_ready(printify_product_id)
        sync_images = not mockups_ready
        if not sync_images:
            logger.info("Mockups ready for %s — publishing without Printify images", printify_product_id)

        await self.printify.publish_product(printify_product_id, sync_images=sync_images)
```

**Step 2: Pass `sync_images` to post-publish task**

Replace line 233:
```python
        asyncio.create_task(self._post_publish_etsy_setup(printify_product_id, etsy_metadata))
```
with:
```python
        asyncio.create_task(self._post_publish_etsy_setup(printify_product_id, etsy_metadata, sync_images=sync_images))
```

---

### Task 4: Update `_check_and_publish()` to use `sync_images`

**Files:**
- Modify: `backend/scheduler.py:241-270`

**Step 1: Add mockup check inside the loop**

Replace lines 254-265 (inside the `for item in due_items` loop):

```python
            try:
                # Skip Printify images if custom mockups are ready
                mockups_ready = await self._check_mockups_ready(pid)
                sync_images = not mockups_ready
                if not sync_images:
                    logger.info("Mockups ready for %s — publishing without Printify images", pid)

                await self.printify.publish_product(pid, sync_images=sync_images)
                await db.update_schedule_status(pid, "published")
                logger.info("Published %s (%s)", pid, item["title"][:40])
                stats = await db.get_schedule_stats()
                await self.notifier.notify_published(
                    item["title"], stats["pending"], stats["next_publish_at"],
                    image_url=item.get("image_url"),
                )
                # Post-publish: fill Etsy metadata + set primary image
                etsy_metadata = item.get("etsy_metadata", {})
                asyncio.create_task(self._post_publish_etsy_setup(pid, etsy_metadata, sync_images=sync_images))
```

---

### Task 5: Update `_post_publish_etsy_setup()` to accept and forward `sync_images`

**Files:**
- Modify: `backend/scheduler.py:312` (signature)
- Modify: `backend/scheduler.py:450-453` and `501-503` (upload calls)

**Step 1: Update signature**

Change line 312:
```python
    async def _post_publish_etsy_setup(self, printify_product_id: str, etsy_metadata: dict = None):
```
to:
```python
    async def _post_publish_etsy_setup(self, printify_product_id: str, etsy_metadata: dict = None, sync_images: bool = True):
```

**Step 2: Pass flag to upload function (pre-composed mockups path, ~line 451)**

Change:
```python
                        upload_results = await _upload_multi_images_to_etsy(
                            access_token, shop_id, etsy_listing_id,
                            poster_url, mockup_entries,
                        )
```
to:
```python
                        upload_results = await _upload_multi_images_to_etsy(
                            access_token, shop_id, etsy_listing_id,
                            poster_url, mockup_entries,
                            has_existing_images=sync_images,
                        )
```

**Step 3: Pass flag to upload function (on-the-fly compose path, ~line 501)**

Change:
```python
                            upload_results = await _upload_multi_images_to_etsy(
                                access_token, shop_id, etsy_listing_id,
                                poster_url, mockup_entries,
                            )
```
to:
```python
                            upload_results = await _upload_multi_images_to_etsy(
                                access_token, shop_id, etsy_listing_id,
                                poster_url, mockup_entries,
                                has_existing_images=sync_images,
                            )
```

---

### Task 6: Update `_upload_multi_images_to_etsy()` to skip delete when no existing images

**Files:**
- Modify: `backend/routes/mockups.py:501-571`

**Step 1: Add parameter and conditional logic**

Update function signature and body:

```python
async def _upload_multi_images_to_etsy(
    access_token: str,
    shop_id: str,
    listing_id: str,
    original_poster_url: str,
    mockup_entries: List[Tuple[int, bytes]],
    has_existing_images: bool = True,
) -> List[dict]:
    """Upload only mockups to Etsy listing (no raw poster).

    When has_existing_images=True (default):
      1. Delete all old images except one (Etsy requires min 1)
      2. Upload mockups at rank=1..N (first mockup = Primary)
      3. Delete the kept old image

    When has_existing_images=False (published with images:false):
      Just upload mockups at rank=1..N (no old images to manage).

    Returns per-image results with etsy_image_id + etsy_cdn_url.
    """
    kept_image = None

    if has_existing_images:
        # Get existing images
        old_images = []
        try:
            images_resp = await etsy.get_listing_images(access_token, listing_id)
            old_images = [img["listing_image_id"] for img in images_resp.get("results", [])]
        except Exception as e:
            print(f"[mockup] Warning: could not list images for {listing_id}: {e}")

        # Delete all except last (Etsy needs at least 1)
        if old_images:
            kept_image = old_images[-1]
            to_delete = old_images[:-1]
            if to_delete:
                print(f"[mockup] Deleting {len(to_delete)} of {len(old_images)} old images from {listing_id}")
                for old_id in to_delete:
                    try:
                        await etsy.delete_listing_image(
                            access_token=access_token, shop_id=shop_id,
                            listing_id=listing_id, listing_image_id=str(old_id),
                        )
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"[mockup] Warning: failed to delete image {old_id}: {e}")

    upload_results = []
    rank = 1

    # Upload mockups FIRST (rank 1 = primary = first mockup)
    for mockup_db_id, mockup_bytes in mockup_entries:
        try:
            resp_data = await etsy.upload_listing_image(
                access_token=access_token, shop_id=shop_id,
                listing_id=listing_id, image_bytes=mockup_bytes,
                filename=f"mockup_{mockup_db_id}.png", rank=rank,
            )
            upload_results.append({
                "type": "mockup", "mockup_db_id": mockup_db_id, "rank": rank,
                "etsy_image_id": str(resp_data.get("listing_image_id", "")),
                "etsy_cdn_url": resp_data.get("url_fullxfull") or resp_data.get("url_570xN"),
            })
            rank += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[mockup] Failed to upload mockup {mockup_db_id}: {e}")

    # Delete the last kept old image (only when we had existing images)
    if kept_image:
        try:
            await etsy.delete_listing_image(
                access_token=access_token, shop_id=shop_id,
                listing_id=listing_id, listing_image_id=str(kept_image),
            )
        except Exception as e:
            print(f"[mockup] Warning: failed to delete last image {kept_image}: {e}")

    return upload_results
```

---

### Task 7: Update manual publish endpoint

**Files:**
- Modify: `backend/routes/printify_routes.py:146-156`

**Step 1: Add mockup readiness check to manual publish**

```python
@router.post("/printify/products/{product_id}/publish")
async def publish_printify_product(product_id: str):
    """Publish a product to the connected store (Etsy)."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        # Skip Printify images if custom mockups are ready
        sync_images = True
        try:
            product = await db.get_product_by_printify_id(product_id)
            if product and product.get("mockup_status") == "approved":
                source_image_id = product.get("source_image_id")
                if source_image_id:
                    mockups = await db.get_image_mockups(source_image_id)
                    included = [m for m in mockups if m.get("is_included", True)]
                    if included:
                        sync_images = False
        except Exception:
            pass  # Fallback to sync_images=True

        result = await printify.publish_product(product_id, sync_images=sync_images)
        return {"ok": True, "result": result, "sync_images": sync_images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Note: Need to add `from database import ... as db` import if not already present. Check existing imports at top of file.

---

### Task 8: Build and smoke-test

**Step 1: Rebuild backend**

Run: `docker-compose up --build -d backend`

**Step 2: Check logs for startup errors**

Run: `docker-compose logs --tail=20 backend`

**Step 3: Manual verification**

Test with an existing product that has approved mockups:
1. Check mockup readiness via DB
2. Trigger publish
3. Verify logs show "publishing without Printify images"
4. Verify Etsy listing gets our mockups directly

---

### Task 9: Commit

```bash
git add backend/printify.py backend/scheduler.py backend/routes/mockups.py backend/routes/printify_routes.py docs/plans/2026-02-16-printify-images-design.md docs/plans/2026-02-16-printify-images-plan.md
git commit -m "feat: skip Printify auto-mockups on publish when custom mockups ready"
```
