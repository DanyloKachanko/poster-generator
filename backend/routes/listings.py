import asyncio
import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from listing_generator import EtsyListing
from pricing import calculate_price, get_all_prices
from printify import create_variants_from_prices
from deps import listing_gen, printify, notifier, publish_scheduler, upscale_service
from routes.dpi import prepare_multidesign_images
from description_utils import clean_description
import database as db

router = APIRouter(tags=["listings"])


class ListingRequest(BaseModel):
    style: str
    preset: str
    description: str
    custom_keywords: Optional[List[str]] = None


class ListingResponse(BaseModel):
    title: str
    tags: List[str]
    tags_string: str
    description: str
    pricing: Optional[dict] = None


@router.post("/generate-listing", response_model=ListingResponse)
async def generate_etsy_listing(request: ListingRequest):
    """Generate complete Etsy listing text (title, tags, description)."""
    if not listing_gen.api_key:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API key not configured. Add ANTHROPIC_API_KEY to .env"
        )

    try:
        listing = await listing_gen.generate_listing(
            style=request.style,
            preset=request.preset,
            description=request.description,
            custom_keywords=request.custom_keywords,
        )

        pricing = get_all_prices("standard")

        return ListingResponse(
            title=listing.title,
            tags=listing.tags,
            tags_string=", ".join(listing.tags),
            description=listing.description,
            pricing=pricing,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegenerateTitleRequest(BaseModel):
    style: str
    preset: str
    current_title: str


@router.post("/regenerate-title")
async def regenerate_title(request: RegenerateTitleRequest):
    """Generate alternative title."""
    try:
        new_title = await listing_gen.regenerate_title(
            style=request.style,
            preset=request.preset,
            current_title=request.current_title,
        )
        return {"title": new_title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegenerateDescRequest(BaseModel):
    style: str
    preset: str
    current_description: str
    tone: str = "warm"


@router.post("/regenerate-description")
async def regenerate_description(request: RegenerateDescRequest):
    """Generate alternative description with different tone."""
    try:
        new_desc = await listing_gen.regenerate_description(
            style=request.style,
            preset=request.preset,
            current_description=request.current_description,
            tone=request.tone,
        )
        return {"description": new_desc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegenerateTagsRequest(BaseModel):
    style: str
    preset: str
    current_tags: List[str] = []
    title: str = ""


@router.post("/regenerate-tags")
async def regenerate_tags(request: RegenerateTagsRequest):
    """Generate alternative tags."""
    try:
        new_tags = await listing_gen.regenerate_tags(
            style=request.style,
            preset=request.preset,
            current_tags=request.current_tags,
            title=request.title,
        )
        return {"tags": new_tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pricing/{size}")
async def get_price_recommendation(
    size: str,
    strategy: str = "standard",
    free_shipping: bool = True,
):
    """Get recommended price for a poster size."""
    return calculate_price(size, strategy, free_shipping)


@router.get("/pricing")
async def get_all_price_recommendations(strategy: str = "standard"):
    """Get recommended prices for all sizes."""
    return get_all_prices(strategy)


class FullCreateRequest(BaseModel):
    style: str
    preset: str
    description: str
    image_url: str
    pricing_strategy: str = "standard"
    publish_to_etsy: bool = False
    preset_id: Optional[str] = None
    # Pre-generated listing data (skip AI generation if all three provided)
    listing_title: Optional[str] = None
    listing_tags: Optional[List[str]] = None
    listing_description: Optional[str] = None


# In-memory task store for background product creation
_product_tasks: dict[str, dict] = {}


async def _run_create_product(task_id: str, request: FullCreateRequest):
    """Background worker for product creation."""
    task = _product_tasks[task_id]
    try:
        # Step 1: Use pre-generated listing data or generate via AI
        task["step"] = "Generating listing..."
        if request.listing_title and request.listing_tags and request.listing_description:
            listing = EtsyListing(
                title=request.listing_title[:140],
                tags=[t[:20].strip() for t in request.listing_tags[:13]],
                description=request.listing_description,
            )
        else:
            listing = await listing_gen.generate_listing(
                style=request.style,
                preset=request.preset,
                description=request.description,
            )

        # Step 2: Get pricing
        prices = get_all_prices(request.pricing_strategy)

        # Step 3: DPI-aware multi-design upload
        task["step"] = "Uploading images..."
        filename_prefix = f"{request.style}_{request.preset}_{int(time.time())}"
        design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
            image_url=request.image_url,
            filename_prefix=filename_prefix,
        )

        # Step 4: Create variants with DPI-aware enabled sizes
        variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)

        # Step 5: Clean description — rebuild AVAILABLE SIZES for enabled sizes only
        clean_desc = clean_description(listing.description, list(enabled_sizes))

        # Step 6: Create product with per-variant designs
        task["step"] = "Creating Printify product..."
        product = await printify.create_product_multidesign(
            title=listing.title,
            description=clean_desc,
            tags=listing.tags,
            design_groups=design_groups,
            variants=variants,
        )

        # Notify: product created
        await notifier.notify_product_created(listing.title, product.id)

        # Step 7: Optionally schedule for Etsy publishing
        scheduled_publish_at = None
        etsy_metadata = {
            "materials": ["Archival paper", "Ink"],
            "who_made": "someone_else",
            "when_made": "2020_2025",
            "is_supply": False,
        }
        product_status = "draft"
        if request.publish_to_etsy:
            task["step"] = "Scheduling Etsy publish..."
            schedule_result = await publish_scheduler.add_to_queue(
                printify_product_id=product.id,
                title=listing.title,
                etsy_metadata=etsy_metadata,
            )
            scheduled_publish_at = schedule_result["scheduled_publish_at"]
            product_status = "scheduled"

        # Resolve source image for linking
        task["step"] = "Saving to database..."
        source_image = await db.get_image_by_url(request.image_url)
        source_image_id = source_image["id"] if source_image else None

        # Save product to local DB
        saved_product = await db.save_product(
            printify_product_id=product.id,
            title=listing.title,
            description=clean_desc,
            tags=listing.tags,
            image_url=request.image_url,
            pricing_strategy=request.pricing_strategy,
            enabled_sizes=sorted(enabled_sizes),
            status=product_status,
            etsy_metadata=etsy_metadata,
            source_image_id=source_image_id,
        )

        # Link generated image ↔ product (both directions)
        if source_image_id:
            await db.link_image_to_product(source_image_id, saved_product["id"])

        # Track preset usage
        if request.preset_id:
            await db.mark_preset_used(request.preset_id, product.id, listing.title)

        # Filter prices to only enabled sizes
        prices = {k: v for k, v in prices.items() if k in enabled_sizes}

        task["status"] = "completed"
        task["step"] = "Done"
        task["result"] = {
            "printify_product_id": product.id,
            "title": listing.title,
            "tags": listing.tags,
            "description": clean_desc,
            "pricing": prices,
            "status": product.status,
            "scheduled_publish_at": scheduled_publish_at,
            "dpi_analysis": dpi_analysis,
            "enabled_sizes": sorted(enabled_sizes),
            "upscale_backend": upscale_service.backend_name,
        }
    except Exception as e:
        task["status"] = "failed"
        task["step"] = "Failed"
        task["error"] = str(e)


@router.post("/create-full-product")
async def create_full_product(request: FullCreateRequest):
    """Start product creation in background. Returns task_id for polling."""
    if not listing_gen.api_key:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API key not configured"
        )

    if not printify.is_configured:
        raise HTTPException(
            status_code=500,
            detail="Printify not configured. Add PRINTIFY_API_TOKEN and PRINTIFY_SHOP_ID to .env"
        )

    task_id = str(uuid.uuid4())[:8]
    _product_tasks[task_id] = {
        "status": "running",
        "step": "Starting...",
        "result": None,
        "error": None,
    }
    asyncio.create_task(_run_create_product(task_id, request))
    return {"task_id": task_id}


@router.get("/create-full-product/status/{task_id}")
async def get_create_product_status(task_id: str):
    """Poll for product creation status."""
    task = _product_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    response = {
        "task_id": task_id,
        "status": task["status"],
        "step": task["step"],
    }

    if task["status"] == "completed":
        response["result"] = task["result"]
        # Clean up after successful retrieval
        _product_tasks.pop(task_id, None)
    elif task["status"] == "failed":
        response["error"] = task["error"]
        _product_tasks.pop(task_id, None)

    return response
