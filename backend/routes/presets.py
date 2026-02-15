from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from presets import get_all_presets, get_preset, get_presets_by_category, get_trending_presets, CATEGORIES
from pod_providers import get_all_providers, compare_providers, RECOMMENDATIONS
import database as db

router = APIRouter(tags=["presets"])


@router.get("/presets")
async def list_presets(category: Optional[str] = None):
    """Get all poster presets, optionally filtered by category."""
    if category:
        presets = get_presets_by_category(category)
    else:
        presets = get_all_presets()
    used_ids = await db.get_used_preset_ids()
    return {"presets": presets, "categories": CATEGORIES, "used_preset_ids": used_ids}


class MarkUsedItem(BaseModel):
    preset_id: str
    printify_product_id: str
    title: Optional[str] = None


@router.post("/presets/mark-used")
async def mark_presets_used(items: List[MarkUsedItem]):
    """Mark presets as used (link to Printify products)."""
    for item in items:
        await db.mark_preset_used(item.preset_id, item.printify_product_id, item.title)
    return {"marked": len(items)}


@router.get("/presets/trending")
async def trending_presets(limit: int = Query(default=10, le=30)):
    """Get top trending presets."""
    return {"presets": get_trending_presets(limit)}


@router.get("/presets/{preset_id}")
async def get_single_preset(preset_id: str):
    """Get a single preset by ID."""
    preset = get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@router.get("/presets/{preset_id}/products")
async def get_preset_products_endpoint(preset_id: str):
    """Get products created from a specific preset."""
    return await db.get_preset_products(preset_id)


@router.get("/categories")
async def list_categories():
    """Get all preset categories."""
    return CATEGORIES


@router.get("/providers")
async def list_providers():
    """Get all POD provider information."""
    return {
        "providers": get_all_providers(),
        "recommendations": RECOMMENDATIONS,
    }


@router.get("/providers/compare")
async def compare_pod_providers(size: str = Query(default="18x24")):
    """Compare providers for a specific poster size."""
    return {"size": size, "providers": compare_providers(size)}
