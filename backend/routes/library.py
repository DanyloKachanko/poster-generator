from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from prompt_library import library as prompt_library

router = APIRouter(tags=["library"])


@router.get("/library/categories")
async def get_library_categories():
    """Get all prompt library categories."""
    return {"categories": prompt_library.get_categories()}


@router.get("/library/prompts")
async def get_library_prompts(
    category: Optional[str] = Query(default=None),
    seasonality: Optional[str] = Query(default=None),
):
    """Get prompt library entries, optionally filtered by category or seasonality."""
    if seasonality:
        prompts = prompt_library.get_prompts_by_seasonality(seasonality)
    elif category:
        prompts = prompt_library.get_prompts(category)
    else:
        prompts = prompt_library.get_prompts()
    return {
        "prompts": prompts,
        "total": len(prompts),
    }


@router.get("/library/prompts/{prompt_id}")
async def get_library_prompt(prompt_id: str):
    """Get a single prompt from the library."""
    prompt = prompt_library.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt
