from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import MODELS, SIZES, STYLE_PRESETS, DEFAULT_MODEL, DEFAULT_SIZE, DEFAULT_NEGATIVE_PROMPT
from deps import leonardo, LEONARDO_API_KEY, publish_scheduler
from sizes import COMPOSITION_SUFFIX
import database as db

router = APIRouter(tags=["generation"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: str | None = Field(default=None, description="Things to avoid in the image")
    width: int = Field(default=1200, ge=512, le=2400)
    height: int = Field(default=1500, ge=512, le=3000)
    num_images: int = Field(default=4, ge=1, le=4)
    model_id: str | None = Field(default=None, description="Model key from /models")
    size_id: str | None = Field(default=None, description="Size key from /sizes")
    style: str | None = Field(default=None, description="Style category")
    preset: str | None = Field(default=None, description="Preset within style")


class GenerateResponse(BaseModel):
    generation_id: str
    status: str


class ImageInfo(BaseModel):
    id: str
    url: str


class GenerationStatusResponse(BaseModel):
    generation_id: str
    status: str
    images: list[ImageInfo] = []


@router.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Poster Generator API is running"}


@router.get("/health")
async def health():
    """Health check with DB connectivity test (for container orchestration)."""
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    status = "healthy" if db_status == "ok" else "unhealthy"
    code = 200 if db_status == "ok" else 503

    return JSONResponse(
        status_code=code,
        content={
            "status": status,
            "database": db_status,
            "scheduler": "running" if publish_scheduler.scheduler.running else "stopped",
        },
    )


@router.get("/styles")
async def get_styles():
    """Return all available style presets."""
    return STYLE_PRESETS


@router.get("/models")
async def get_models():
    """Return all available AI models."""
    return MODELS


@router.get("/sizes")
async def get_sizes():
    """Return all available poster sizes."""
    return SIZES


@router.get("/defaults")
async def get_defaults():
    """Return default values for generation."""
    return {
        "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
        "model": DEFAULT_MODEL,
        "size": DEFAULT_SIZE,
    }


@router.post("/generate", response_model=GenerateResponse)
async def start_generation(request: GenerateRequest):
    """
    Start a new image generation.

    Returns the generation ID to poll for results.
    """
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")

    try:
        # Get model ID from key or use default
        model_key = request.model_id or DEFAULT_MODEL
        model_info = MODELS.get(model_key)
        if not model_info:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model_key}")

        # Get size from key or use defaults
        if request.size_id:
            size_info = SIZES.get(request.size_id)
            if not size_info:
                raise HTTPException(status_code=400, detail=f"Unknown size: {request.size_id}")
            width = size_info["width"]
            height = size_info["height"]
            # Scale down proportionally to fit within Leonardo max 1536
            if width > 1536 or height > 1536:
                scale = 1536 / max(width, height)
                width = int(width * scale) // 8 * 8   # must be multiple of 8
                height = int(height * scale) // 8 * 8
        else:
            width = request.width
            height = request.height

        # Use provided negative prompt or default
        negative_prompt = request.negative_prompt if request.negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT

        # Append composition suffix for poster sizes (ensures crop safety)
        generation_prompt = request.prompt
        if request.size_id and request.size_id.startswith("poster_"):
            generation_prompt = request.prompt + COMPOSITION_SUFFIX

        result = await leonardo.create_generation(
            prompt=generation_prompt,
            width=width,
            height=height,
            num_images=request.num_images,
            model_id=model_info["id"],
            negative_prompt=negative_prompt,
        )

        # Save to database (store original prompt, not with suffix)
        await db.save_generation(
            generation_id=result["generation_id"],
            prompt=request.prompt,
            negative_prompt=negative_prompt,
            model_id=model_info["id"],
            model_name=model_info["name"],
            style=request.style,
            preset=request.preset,
            width=width,
            height=height,
            num_images=request.num_images,
            status="PENDING"
        )

        return GenerateResponse(
            generation_id=result["generation_id"],
            status=result["status"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generation/{generation_id}", response_model=GenerationStatusResponse)
async def get_generation_status(generation_id: str):
    """
    Check the status of a generation.

    Returns the status and images (if complete).
    """
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")

    try:
        result = await leonardo.get_generation(generation_id)

        # Update database when status changes
        if result["status"] in ("COMPLETE", "FAILED"):
            api_credit_cost = result.get("api_credit_cost", 0)
            await db.update_generation_status(
                generation_id=generation_id,
                status=result["status"],
                api_credit_cost=api_credit_cost
            )

            # Save images if complete
            if result["status"] == "COMPLETE" and result["images"]:
                await db.save_generated_images(generation_id, result["images"])

                # Save credit usage
                if api_credit_cost > 0:
                    await db.save_credit_usage(generation_id, api_credit_cost)

        return GenerationStatusResponse(
            generation_id=result["generation_id"],
            status=result["status"],
            images=[ImageInfo(**img) for img in result["images"]],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/credits")
async def get_credits():
    """
    Get credit usage statistics and remaining Leonardo API token balance.
    """
    try:
        stats = await db.get_generation_stats()

        # Fetch real token balance from Leonardo API
        token_balance = None
        if LEONARDO_API_KEY:
            try:
                token_balance = await leonardo.get_user_info()
            except Exception:
                pass  # If API call fails, we still return local stats

        return {
            "total_credits_used": stats["total_credits_used"],
            "total_generations": stats["total_generations"],
            "total_images": stats["total_images"],
            "by_status": stats["by_status"],
            "balance": token_balance,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    style: Optional[str] = Query(default=None, description="Filter by style"),
    exclude_style: Optional[str] = Query(default=None, description="Exclude specific style"),
    model_id: Optional[str] = Query(default=None, description="Filter by model"),
    archived: bool = Query(default=False, description="Show archived items")
):
    """
    Get paginated generation history with optional filters.
    """
    try:
        result = await db.get_history(
            limit=limit,
            offset=offset,
            status=status,
            style=style,
            exclude_style=exclude_style,
            model_id=model_id,
            archived=archived
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{generation_id}")
async def get_history_item(generation_id: str):
    """
    Get a single generation from history with all details.
    """
    try:
        generation = await db.get_generation(generation_id)
        if not generation:
            raise HTTPException(status_code=404, detail="Generation not found")

        images = await db.get_generation_images(generation_id)
        generation["images"] = images
        return generation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/{generation_id}/archive")
async def archive_generation(generation_id: str):
    """Archive (soft-delete) a generation."""
    try:
        success = await db.archive_generation(generation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Generation not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/{generation_id}/restore")
async def restore_generation(generation_id: str):
    """Restore an archived generation."""
    try:
        success = await db.restore_generation(generation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Generation not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
