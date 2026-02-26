import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from prompt_library import library as prompt_library
from presets import get_preset
from pricing import get_all_prices
from printify import create_variants_from_prices
from sizes import COMPOSITION_SUFFIX
from config import MODELS, SIZES
from deps import (
    LEONARDO_API_KEY, leonardo, listing_gen, printify,
    notifier, publish_scheduler, upscale_service,
)
from routes.dpi import prepare_multidesign_images
from description_utils import clean_description
import database as db

router = APIRouter(tags=["pipeline"])


class AutoProductRequest(BaseModel):
    prompt_id: str
    model_id: str = "phoenix"
    size_id: str = "poster_4_5"
    pricing_strategy: str = "standard"
    publish_to_etsy: bool = False
    custom_title: Optional[str] = None
    custom_tags: Optional[List[str]] = None
    preset_id: Optional[str] = None


class PresetProductRequest(BaseModel):
    preset_id: str
    model_id: str = "phoenix"
    size_id: str = "poster_4_5"
    pricing_strategy: str = "standard"
    publish_to_etsy: bool = False
    seo_instruction: Optional[str] = None


# ---------------------------------------------------------------------------
# Shared private helpers
# ---------------------------------------------------------------------------

def _validate_services():
    """Raise HTTPException if any required service is not configured."""
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")
    if not printify.is_configured:
        raise HTTPException(status_code=500, detail="Printify not configured")


def _validate_model_and_size(model_id: str, size_id: str):
    """Return (model_info, size_info) or raise HTTPException."""
    model_info = MODELS.get(model_id)
    if not model_info:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_id}")
    size_info = SIZES.get(size_id)
    if not size_info:
        raise HTTPException(status_code=400, detail=f"Unknown size: {size_id}")
    return model_info, size_info


async def _generate_image(
    prompt: str,
    negative_prompt: str,
    model_info: dict,
    size_info: dict,
    *,
    category: str,
    preset_key: str,
    clamp_to_leonardo_max: bool = False,
):
    """
    Generate an image via Leonardo, poll for completion, and persist to DB.

    Returns (gen_id, image_url, source_image_id).
    """
    gen_prompt = prompt + COMPOSITION_SUFFIX
    gen_width = size_info["width"]
    gen_height = size_info["height"]

    if clamp_to_leonardo_max and (gen_width > 1536 or gen_height > 1536):
        scale = 1536 / max(gen_width, gen_height)
        gen_width = int(gen_width * scale) // 8 * 8
        gen_height = int(gen_height * scale) // 8 * 8

    gen_result = await leonardo.create_generation(
        prompt=gen_prompt,
        model_id=model_info["id"],
        num_images=1,
        negative_prompt=negative_prompt,
        width=gen_width,
        height=gen_height,
    )
    gen_id = gen_result["generation_id"]

    # Save generation to DB (store original prompt, not the suffixed one)
    await db.save_generation(
        generation_id=gen_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        model_id=model_info["id"],
        model_name=model_info["name"],
        style=category,
        preset=preset_key,
        width=size_info["width"],
        height=size_info["height"],
        num_images=1,
    )

    # Poll for completion
    completed = await leonardo.wait_for_generation(gen_id, poll_interval=3.0, timeout=120.0)
    if completed["status"] != "COMPLETE" or not completed.get("images"):
        raise HTTPException(status_code=500, detail="Image generation failed")

    await db.update_generation_status(gen_id, "COMPLETE", completed.get("api_credit_cost", 0))
    await db.save_generated_images(gen_id, completed["images"])

    image_url = completed["images"][0]["url"]
    source_image = await db.get_image_by_url(image_url)
    source_image_id = source_image["id"] if source_image else None

    return gen_id, image_url, source_image_id


async def _create_printify_product(
    image_url: str,
    title: str,
    description: str,
    tags: list,
    pricing_strategy: str,
    filename_prefix: str,
):
    """
    Upload DPI-aware designs and create a Printify product.

    Returns (product, prices, enabled_sizes, dpi_analysis, clean_desc).
    """
    prices = get_all_prices(pricing_strategy)
    design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
        image_url=image_url,
        filename_prefix=filename_prefix,
    )

    clean_desc = clean_description(description, list(enabled_sizes))

    variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)
    product = await printify.create_product_multidesign(
        title=title,
        description=clean_desc,
        tags=tags,
        design_groups=design_groups,
        variants=variants,
    )

    await notifier.notify_product_created(title, product.id)

    # Filter prices to only enabled sizes
    prices = {k: v for k, v in prices.items() if k in enabled_sizes}

    return product, prices, enabled_sizes, dpi_analysis, clean_desc


async def _schedule_and_save_product(
    product_id: str,
    title: str,
    clean_desc: str,
    tags: list,
    image_url: str,
    pricing_strategy: str,
    enabled_sizes: set,
    source_image_id: Optional[int],
    publish_to_etsy: bool,
):
    """
    Optionally schedule Etsy publishing and save the product to the local DB.

    Returns (saved_product, scheduled_publish_at, product_status).
    """
    etsy_metadata = {
        "materials": ["Archival paper", "Ink"],
        "who_made": "someone_else",
        "when_made": "2020_2025",
        "is_supply": False,
    }

    scheduled_publish_at = None
    product_status = "draft"
    if publish_to_etsy:
        schedule_result = await publish_scheduler.add_to_queue(
            printify_product_id=product_id,
            title=title,
            etsy_metadata=etsy_metadata,
        )
        scheduled_publish_at = schedule_result["scheduled_publish_at"]
        product_status = "scheduled"

    saved_product = await db.save_product(
        printify_product_id=product_id,
        title=title,
        description=clean_desc,
        tags=tags,
        image_url=image_url,
        pricing_strategy=pricing_strategy,
        enabled_sizes=sorted(enabled_sizes),
        status=product_status,
        etsy_metadata=etsy_metadata,
        source_image_id=source_image_id,
    )

    if source_image_id:
        await db.link_image_to_product(source_image_id, saved_product["id"])

    return saved_product, scheduled_publish_at, product_status


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.post("/pipeline/auto-product")
async def auto_create_product(request: AutoProductRequest):
    """
    Full automation: Library prompt -> Generate -> Listing -> Printify -> Etsy.

    1. Get prompt from library
    2. Generate image via Leonardo + poll
    3. Generate listing text via Claude (with library tags)
    4. Upload to Printify + create product
    5. Optionally publish to Etsy
    """
    _validate_services()

    # Get prompt from library
    lib_prompt = prompt_library.get_prompt(request.prompt_id)
    if not lib_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found in library")

    lib_prompt_obj = prompt_library.get_prompt_obj(request.prompt_id)
    category = prompt_library.get_category(lib_prompt["category"])
    model_info, size_info = _validate_model_and_size(request.model_id, request.size_id)

    try:
        # Step 1-2: Generate image and poll for completion
        gen_id, image_url, source_image_id = await _generate_image(
            prompt=lib_prompt["prompt"],
            negative_prompt=lib_prompt.get("negative_prompt", ""),
            model_info=model_info,
            size_info=size_info,
            category=lib_prompt["category"],
            preset_key=request.prompt_id,
        )

        # Step 3: Generate listing text with library tags as keywords
        full_tags = lib_prompt.get("full_tags", [])
        custom_keywords = request.custom_tags or full_tags

        listing = await listing_gen.generate_listing(
            style=lib_prompt.get("category_display", lib_prompt["category"]),
            preset=lib_prompt["name"],
            description=lib_prompt["prompt"],
            custom_keywords=custom_keywords,
        )

        title = request.custom_title or listing.title
        tags = request.custom_tags or listing.tags

        # Step 4-5: DPI-aware upload + create Printify product
        filename_prefix = f"{request.prompt_id}_{int(time.time())}"
        product, prices, enabled_sizes, dpi_analysis, clean_desc = await _create_printify_product(
            image_url=image_url,
            title=title,
            description=listing.description,
            tags=tags,
            pricing_strategy=request.pricing_strategy,
            filename_prefix=filename_prefix,
        )

        # Step 6: Schedule publishing + save to DB
        saved_product, scheduled_publish_at, _ = await _schedule_and_save_product(
            product_id=product.id,
            title=title,
            clean_desc=clean_desc,
            tags=tags,
            image_url=image_url,
            pricing_strategy=request.pricing_strategy,
            enabled_sizes=enabled_sizes,
            source_image_id=source_image_id,
            publish_to_etsy=request.publish_to_etsy,
        )

        # Track preset usage
        if request.preset_id:
            await db.mark_preset_used(request.preset_id, product.id, title)

        return {
            "printify_product_id": product.id,
            "generation_id": gen_id,
            "title": title,
            "tags": tags,
            "description": listing.description,
            "image_url": image_url,
            "pricing": prices,
            "scheduled_publish_at": scheduled_publish_at,
            "dpi_analysis": dpi_analysis,
            "enabled_sizes": sorted(enabled_sizes),
            "upscale_backend": upscale_service.backend_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline/preset-product")
async def preset_create_product(request: PresetProductRequest):
    """
    Full automation from a preset: Preset -> Generate -> Listing -> Printify.

    1. Get preset from presets.py
    2. Generate image via Leonardo + poll
    3. Generate listing text via Claude (with preset tags + optional SEO instruction)
    4. Upload to Printify + create product (draft)
    5. Mark preset as used
    """
    _validate_services()

    preset = get_preset(request.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {request.preset_id}")

    model_info, size_info = _validate_model_and_size(request.model_id, request.size_id)

    try:
        # Step 1-2: Generate image and poll for completion
        gen_id, image_url, source_image_id = await _generate_image(
            prompt=preset["prompt"],
            negative_prompt=preset.get("negative_prompt", ""),
            model_info=model_info,
            size_info=size_info,
            category=preset["category"],
            preset_key=request.preset_id,
            clamp_to_leonardo_max=True,
        )

        # Step 3: Generate listing text
        description_for_claude = preset["prompt"]
        if request.seo_instruction:
            description_for_claude += f"\n\nIMPORTANT SEO: {request.seo_instruction}"

        listing = await listing_gen.generate_listing(
            style=preset["category"],
            preset=preset["name"],
            description=description_for_claude,
            custom_keywords=preset["tags"],
        )

        title = listing.title
        tags = listing.tags

        # Step 4: DPI-aware upload + create Printify product
        filename_prefix = f"{request.preset_id}_{int(time.time())}"
        product, prices, enabled_sizes, dpi_analysis, clean_desc = await _create_printify_product(
            image_url=image_url,
            title=title,
            description=listing.description,
            tags=tags,
            pricing_strategy=request.pricing_strategy,
            filename_prefix=filename_prefix,
        )

        # Step 5: Mark preset as used
        await db.mark_preset_used(request.preset_id, product.id, title)

        # Schedule publishing + save to DB
        saved_product, scheduled_publish_at, _ = await _schedule_and_save_product(
            product_id=product.id,
            title=title,
            clean_desc=clean_desc,
            tags=tags,
            image_url=image_url,
            pricing_strategy=request.pricing_strategy,
            enabled_sizes=enabled_sizes,
            source_image_id=source_image_id,
            publish_to_etsy=request.publish_to_etsy,
        )

        return {
            "printify_product_id": product.id,
            "generation_id": gen_id,
            "title": title,
            "tags": tags,
            "description": clean_desc,
            "image_url": image_url,
            "pricing": prices,
            "scheduled_publish_at": scheduled_publish_at,
            "dpi_analysis": dpi_analysis,
            "enabled_sizes": sorted(enabled_sizes),
            "preset_id": request.preset_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
