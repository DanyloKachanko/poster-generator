from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from prompt_library import library as prompt_library
from config import MODELS, SIZES
from deps import leonardo, batch_manager, LEONARDO_API_KEY
import database as db

router = APIRouter(tags=["batch"])


class BatchGenerateRequest(BaseModel):
    prompt_ids: List[str]
    model_id: str = "phoenix"
    size_id: str = "poster_4_5"
    num_images_per_prompt: int = Field(default=1, ge=1, le=2)
    use_variations: bool = False
    variation_index: Optional[int] = None
    delay_between: float = Field(default=3.0, ge=1.0, le=30.0)


@router.post("/batch/generate")
async def start_batch_generation(request: BatchGenerateRequest):
    """Start a batch generation job for multiple library prompts."""
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")

    if not request.prompt_ids:
        raise HTTPException(status_code=400, detail="No prompt IDs provided")

    # Validate all prompt IDs exist
    for pid in request.prompt_ids:
        if not prompt_library.get_prompt(pid):
            raise HTTPException(status_code=400, detail=f"Unknown prompt ID: {pid}")

    # Validate model and size
    if request.model_id not in MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model_id}")
    if request.size_id not in SIZES:
        raise HTTPException(status_code=400, detail=f"Unknown size: {request.size_id}")

    job = batch_manager.create_batch(
        prompt_ids=request.prompt_ids,
        model_id=request.model_id,
        size_id=request.size_id,
        num_images_per_prompt=request.num_images_per_prompt,
        use_variations=request.use_variations,
        variation_index=request.variation_index,
        delay_between=request.delay_between,
    )

    batch_manager.start_batch(
        job.batch_id, leonardo, db, prompt_library, MODELS, SIZES
    )

    return job.to_dict()


@router.get("/batch")
async def list_batches():
    """List all batch jobs."""
    return {"batches": batch_manager.list_batches()}


@router.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get detailed batch status with per-item progress."""
    job = batch_manager.get_batch(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    return job.to_dict(include_items=True)


@router.post("/batch/{batch_id}/cancel")
async def cancel_batch(batch_id: str):
    """Cancel a running batch."""
    success = batch_manager.cancel_batch(batch_id)
    if not success:
        raise HTTPException(status_code=400, detail="Batch not found or not running")
    return {"ok": True}
