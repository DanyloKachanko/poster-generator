import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from etsy_autocomplete import EtsyAutocompleteChecker
from etsy_search_validator import EtsySearchValidator
from seo_scheduler import SEOScheduler
from deps import etsy, listing_gen
from routes.etsy_auth import ensure_etsy_token
import database as db

router = APIRouter(tags=["seo"])

# Shared instances (in-memory cache persists for app lifetime)
_google_checker = EtsyAutocompleteChecker()
_etsy_validator = EtsySearchValidator(etsy)
_seo_scheduler = SEOScheduler(etsy, _etsy_validator)


class ValidateTagsRequest(BaseModel):
    tags: List[str]


class RegenerateFlaggedRequest(BaseModel):
    listing_ids: Optional[List[int]] = None  # If None, auto-detect from scheduler
    min_score: float = 0.8  # Only regenerate listings below this Etsy score
    dry_run: bool = False  # If True, regenerate + validate but don't push to Etsy


# --- Google Autocomplete endpoints (existing) ---

@router.post("/seo/validate-tags")
async def validate_tags(request: ValidateTagsRequest):
    """Validate tags against Google autocomplete to check real search volume."""
    if not request.tags:
        raise HTTPException(status_code=400, detail="No tags provided")
    return await _google_checker.check_tags(request.tags)


@router.get("/seo/autocomplete")
async def autocomplete(q: str):
    """Get Google autocomplete suggestions for a query."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query too short")
    suggestions = await _google_checker.get_suggestions(q.strip())
    return {"query": q.strip(), "suggestions": suggestions}


# --- Etsy Search Volume endpoints (new) ---

@router.post("/seo/validate-tags-etsy")
async def validate_tags_etsy(request: ValidateTagsRequest):
    """Validate tags against Etsy search results count."""
    if not request.tags:
        raise HTTPException(status_code=400, detail="No tags provided")
    return await _etsy_validator.check_tags(request.tags)


@router.get("/seo/etsy-search")
async def etsy_search_volume(q: str):
    """Get Etsy search volume for a query."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query too short")
    result = await _etsy_validator.check_tag(q.strip())
    return result


# --- Bulk validation endpoints ---

@router.post("/seo/validate-all-listings")
async def validate_all_listings():
    """Validate tags for all Etsy listings with Google autocomplete."""
    try:
        access_token, shop_id = await ensure_etsy_token()
        listings = await etsy.get_all_listings(access_token, shop_id)

        results = []
        for listing in listings:
            tags = listing.get("tags", [])
            if not tags:
                continue
            validation = await _google_checker.check_tags(tags)
            results.append({
                "listing_id": listing.get("listing_id"),
                "title": listing.get("title", ""),
                "tags_total": len(tags),
                "tags_validated": validation["found"],
                "validation_score": validation["score"],
                "not_found_tags": [r["tag"] for r in validation["results"] if not r["found"]],
            })

        results.sort(key=lambda r: r["validation_score"])
        avg_score = sum(r["validation_score"] for r in results) / len(results) if results else 0

        return {
            "total_listings": len(results),
            "avg_validation_score": round(avg_score, 2),
            "listings": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Cache management endpoints ---

@router.get("/seo/cache/stats")
async def cache_stats():
    """Get autocomplete cache statistics."""
    try:
        stats = await db.get_cache_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seo/cache/clear-expired")
async def clear_expired_cache():
    """Delete expired cache entries."""
    try:
        result = await db.clear_expired_cache()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Scheduler endpoints ---

@router.post("/seo/scheduler/run")
async def run_seo_scheduler():
    """Manually trigger an SEO scheduler run."""
    try:
        result = await _seo_scheduler.run()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seo/validate-all-etsy")
async def validate_all_etsy():
    """Validate ALL listings' tags via Etsy search volume + Google autocomplete comparison."""
    try:
        access_token, shop_id = await ensure_etsy_token()
        listings = await etsy.get_all_listings(access_token, shop_id)

        results = []
        for listing in listings:
            tags = listing.get("tags", [])
            if not tags:
                continue

            # Run both validations
            google_val = await _google_checker.check_tags(tags)
            etsy_val = await _etsy_validator.check_tags(tags)

            # Merge per-tag results
            tag_details = []
            for g, e in zip(google_val["results"], etsy_val["results"]):
                tag_details.append({
                    "tag": g["tag"],
                    "google": g["found"],
                    "etsy": e["found"],
                    "etsy_results": e["total_results"],
                    "etsy_demand": e["demand"],
                })

            results.append({
                "listing_id": listing.get("listing_id"),
                "title": listing.get("title", ""),
                "tags_total": len(tags),
                "google_score": google_val["score"],
                "etsy_score": etsy_val["score"],
                "tags": tag_details,
                "google_not_found": [r["tag"] for r in google_val["results"] if not r["found"]],
                "etsy_not_found": [r["tag"] for r in etsy_val["results"] if not r["found"]],
            })

        results.sort(key=lambda r: r["etsy_score"])

        avg_google = sum(r["google_score"] for r in results) / len(results) if results else 0
        avg_etsy = sum(r["etsy_score"] for r in results) / len(results) if results else 0

        return {
            "total_listings": len(results),
            "avg_google_score": round(avg_google, 2),
            "avg_etsy_score": round(avg_etsy, 2),
            "listings": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Regenerate flagged listings ---

@router.post("/seo/regenerate-flagged")
async def regenerate_flagged(request: RegenerateFlaggedRequest):
    """Regenerate SEO for underperforming listings.

    Flow: identify flagged → regenerate tags via Claude → validate new tags → push if score ≥ threshold.
    """
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        access_token, shop_id = await ensure_etsy_token()

        # Step 1: Identify flagged listings
        if request.listing_ids:
            target_ids = set(request.listing_ids)
        else:
            # Auto-detect: run scheduler to find flagged listings
            scheduler_result = await _seo_scheduler.run()
            if scheduler_result.get("status") != "ok":
                return {"status": "error", "detail": "Scheduler failed", "scheduler": scheduler_result}
            flagged = scheduler_result.get("flagged_listings", [])
            target_ids = {item["listing_id"] for item in flagged}

        if not target_ids:
            return {"status": "ok", "message": "No flagged listings found", "results": []}

        # Step 2: Fetch listings and process each
        all_listings = await etsy.get_all_listings(access_token, shop_id)
        listings_map = {l["listing_id"]: l for l in all_listings}

        results = []
        for listing_id in target_ids:
            listing = listings_map.get(listing_id)
            if not listing:
                results.append({"listing_id": listing_id, "status": "not_found"})
                continue

            old_title = listing.get("title", "")
            old_tags = listing.get("tags", [])
            old_desc = listing.get("description", "")

            # Validate old tags
            old_validation = await _etsy_validator.check_tags(old_tags)
            old_score = old_validation["score"]

            # Skip if already above threshold
            if old_score >= request.min_score:
                results.append({
                    "listing_id": listing_id,
                    "title": old_title,
                    "status": "skipped",
                    "reason": f"Already at {old_score:.0%} (threshold: {request.min_score:.0%})",
                    "old_score": old_score,
                })
                continue

            # Regenerate SEO via Claude
            new_listing = await listing_gen.regenerate_seo_from_existing(
                current_title=old_title,
                current_tags=old_tags,
                current_description=old_desc,
            )

            # Validate new tags
            new_validation = await _etsy_validator.check_tags(new_listing.tags)
            new_score = new_validation["score"]

            old_dead = [r["tag"] for r in old_validation["results"] if not r["found"]]
            new_dead = [r["tag"] for r in new_validation["results"] if not r["found"]]

            entry = {
                "listing_id": listing_id,
                "title": old_title,
                "old_tags": old_tags,
                "old_score": old_score,
                "old_dead_tags": old_dead,
                "new_title": new_listing.title,
                "new_tags": new_listing.tags,
                "new_score": new_score,
                "new_dead_tags": new_dead,
                "score_change": f"{old_score:.0%} → {new_score:.0%}",
            }

            # Push to Etsy if new score meets threshold and not dry run
            if new_score >= request.min_score and not request.dry_run:
                update_data = {
                    "title": new_listing.title,
                    "tags": new_listing.tags,
                    "description": new_listing.description,
                }
                await etsy.update_listing(access_token, shop_id, str(listing_id), update_data)
                entry["status"] = "updated"
            elif request.dry_run:
                entry["status"] = "dry_run"
            else:
                entry["status"] = "not_improved"
                entry["reason"] = f"New score {new_score:.0%} still below {request.min_score:.0%}"

            results.append(entry)
            await asyncio.sleep(0.5)

        updated = sum(1 for r in results if r.get("status") == "updated")
        return {
            "status": "ok",
            "total_processed": len(results),
            "updated": updated,
            "dry_run": request.dry_run,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
