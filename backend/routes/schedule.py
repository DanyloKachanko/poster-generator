from typing import Optional, List
from datetime import datetime as _dt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deps import printify, publish_scheduler
import database as db

router = APIRouter(tags=["schedule"])


class ScheduleAddRequest(BaseModel):
    printify_product_id: str
    title: str
    scheduled_publish_at: Optional[str] = None  # ISO format UTC — override auto slot


@router.post("/schedule/add")
async def schedule_add(request: ScheduleAddRequest):
    """Add a Printify product to the publish schedule.
    If scheduled_publish_at is provided, use that exact time. Otherwise auto-calculate.
    Auto-approves mockups with default pack if not already approved."""
    try:
        # Auto-approve mockups if product has a source image but no approved mockups
        local_product = await db.get_product_by_printify_id(request.printify_product_id)
        if local_product and local_product.get("source_image_id"):
            source_image_id = local_product["source_image_id"]
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT mockup_status FROM generated_images WHERE id = $1",
                    source_image_id,
                )
                # If mockup not approved, auto-approve with default pack
                if row and row["mockup_status"] != "approved":
                    try:
                        # Get default pack ID
                        default_pack_id = await db.get_setting("default_pack_id")
                        pack_id = int(default_pack_id) if default_pack_id else 2  # fallback to pack 2

                        # Import mockup approval logic
                        from routes.mockups import approve_poster, ApproveRequest

                        # Approve with default pack (will compose and save mockups)
                        await approve_poster(source_image_id, ApproveRequest(pack_id=pack_id))
                        logger.info("Auto-approved mockups for product %s before scheduling", request.printify_product_id)
                    except Exception as e:
                        logger.warning("Failed to auto-approve mockups for %s: %s", request.printify_product_id, e)

        # Fetch product image from Printify
        image_url = None
        if printify.is_configured:
            try:
                product = await printify.get_product(request.printify_product_id)
                images = product.get("images", [])
                if images:
                    image_url = images[0].get("src")
            except Exception:
                pass

        if request.scheduled_publish_at:
            result = await db.add_to_schedule(
                printify_product_id=request.printify_product_id,
                title=request.title,
                scheduled_publish_at=request.scheduled_publish_at,
                image_url=image_url,
            )
        else:
            result = await publish_scheduler.add_to_queue(
                printify_product_id=request.printify_product_id,
                title=request.title,
                image_url=image_url,
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule/queue")
async def schedule_queue(status: Optional[str] = None):
    """Get the publish queue. Optional ?status=pending|published|failed."""
    return await db.get_schedule_queue(status=status)


@router.post("/schedule/publish-now/{product_id}")
async def schedule_publish_now(product_id: str):
    """Immediately publish a product, bypassing the schedule."""
    try:
        result = await publish_scheduler.publish_now(product_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedule/{product_id}")
async def schedule_remove(product_id: str):
    """Remove a product from the publish queue."""
    removed = await db.remove_from_schedule(product_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Product not found in schedule")
    return {"removed": product_id}


@router.get("/schedule/stats")
async def schedule_stats():
    """Get scheduling statistics."""
    return await db.get_schedule_stats()


class ScheduleBatchRequest(BaseModel):
    product_ids: List[str]


@router.post("/schedule/add-batch")
async def schedule_add_batch(request: ScheduleBatchRequest):
    """Add multiple products to the schedule with auto-calculated sequential slots.
    Auto-approves mockups with default pack if not already approved."""
    if not request.product_ids:
        raise HTTPException(status_code=400, detail="product_ids is required")

    results = []
    for pid in request.product_ids:
        try:
            # Get title from local DB or Printify
            title = pid
            local = await db.get_product_by_printify_id(pid)
            if local:
                title = local.get("title", pid)

                # Auto-approve mockups if needed
                if local.get("source_image_id"):
                    source_image_id = local["source_image_id"]
                    pool = await db.get_pool()
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT mockup_status FROM generated_images WHERE id = $1",
                            source_image_id,
                        )
                        if row and row["mockup_status"] != "approved":
                            try:
                                default_pack_id = await db.get_setting("default_pack_id")
                                pack_id = int(default_pack_id) if default_pack_id else 2
                                from routes.mockups import approve_poster, ApproveRequest
                                await approve_poster(source_image_id, ApproveRequest(pack_id=pack_id))
                                logger.info("Auto-approved mockups for product %s before scheduling", pid)
                            except Exception as e:
                                logger.warning("Failed to auto-approve mockups for %s: %s", pid, e)

            elif printify.is_configured:
                try:
                    product = await printify.get_product(pid)
                    title = product.get("title", pid)
                except Exception:
                    pass

            result = await publish_scheduler.add_to_queue(
                printify_product_id=pid,
                title=title,
            )
            results.append({
                "printify_product_id": pid,
                "title": title,
                "scheduled_publish_at": result["scheduled_publish_at"],
            })
        except Exception as e:
            results.append({
                "printify_product_id": pid,
                "error": str(e),
            })

    return {
        "scheduled": len([r for r in results if "scheduled_publish_at" in r]),
        "failed": len([r for r in results if "error" in r]),
        "results": results,
    }


@router.post("/schedule/retry/{product_id}")
async def schedule_retry(product_id: str):
    """Retry a failed publish by resetting status to pending with a new slot."""
    queue = await db.get_schedule_queue(status="failed")
    item = next(
        (i for i in queue if i["printify_product_id"] == product_id),
        None,
    )
    if not item:
        raise HTTPException(status_code=404, detail="No failed item found for this product")

    # Reset to pending and reschedule
    next_slot = await publish_scheduler._calculate_next_slot()
    await db.update_schedule_status(product_id, "pending")
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE scheduled_products SET scheduled_publish_at = $1, error_message = NULL WHERE printify_product_id = $2",
            next_slot.isoformat(), product_id,
        )

    return {
        "printify_product_id": product_id,
        "status": "pending",
        "scheduled_publish_at": next_slot.isoformat(),
    }


class ScheduleSettingsRequest(BaseModel):
    publish_times: List[str]  # e.g. ["10:00", "14:00", "18:00"]
    timezone: str = "US/Eastern"
    enabled: bool = True
    preferred_primary_camera: str = ""
    default_shipping_profile_id: Optional[int] = None
    default_shop_section_id: Optional[int] = None


@router.get("/schedule/settings")
async def get_schedule_settings():
    """Get current schedule configuration."""
    return await db.get_schedule_settings()


@router.put("/schedule/settings")
async def update_schedule_settings(request: ScheduleSettingsRequest):
    """Update publish schedule configuration. Changes take effect immediately."""
    if not request.publish_times:
        raise HTTPException(status_code=400, detail="At least one publish time is required")

    for t in request.publish_times:
        try:
            _dt.strptime(t, "%H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid time format: {t}. Use HH:MM")

    result = await db.save_schedule_settings(
        publish_times=sorted(request.publish_times),
        timezone=request.timezone,
        enabled=request.enabled,
        preferred_primary_camera=request.preferred_primary_camera,
        default_shipping_profile_id=request.default_shipping_profile_id,
        default_shop_section_id=request.default_shop_section_id,
    )
    await publish_scheduler.reload_settings()
    return result
