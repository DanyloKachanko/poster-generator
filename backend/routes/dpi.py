import io
from fastapi import APIRouter, HTTPException, Query
import httpx
from PIL import Image
from dpi import analyze_sizes, get_size_groups
from upscaler import fit_image_to_ratio
from printify import DesignGroup
from deps import printify, upscale_service

router = APIRouter(tags=["dpi"])


@router.get("/dpi/analyze")
async def dpi_analyze(
    width: int = Query(..., ge=256, le=16384),
    height: int = Query(..., ge=256, le=16384),
):
    """Analyze DPI quality for all poster sizes given a source image resolution."""
    analysis = analyze_sizes(width, height)
    original_ok, needs_upscale, skip = get_size_groups(analysis)
    return {
        "source": {"width": width, "height": height},
        "sizes": {k: v.to_dict() for k, v in analysis.items()},
        "groups": {
            "original_ok": original_ok,
            "upscale_needed": needs_upscale,
            "skip": skip,
        },
        "upscale_backend": upscale_service.backend_name,
    }


async def prepare_multidesign_images(
    image_url: str,
    filename_prefix: str,
) -> tuple:
    """Download image, analyze DPI, create per-size cropped+upscaled images.

    Each poster size gets its own image cropped to the EXACT aspect ratio
    and resized to the EXACT Printify target pixels. This eliminates white
    padding that Printify adds when the image ratio doesn't match the variant.

    Returns:
        (design_groups, enabled_sizes, dpi_analysis_dict)
    """
    # Download source image
    async with httpx.AsyncClient() as client:
        resp = await client.get(image_url, timeout=60.0)
        resp.raise_for_status()
        source_bytes = resp.content

    # Get dimensions
    img = Image.open(io.BytesIO(source_bytes))
    src_w, src_h = img.size

    # Analyze DPI for all sizes
    analysis = analyze_sizes(src_w, src_h)
    _original_ok, _needs_upscale, skip = get_size_groups(analysis)

    sellable = [k for k, sa in analysis.items() if sa.is_sellable]
    if not sellable:
        raise ValueError(f"No sellable sizes for {src_w}x{src_h} image")

    design_groups = []
    enabled_sizes = set()

    # Per-size: crop to exact ratio, resize to exact target pixels
    for size_key in sellable:
        sa = analysis[size_key]
        target_ratio = sa.target_width / sa.target_height

        try:
            cropped = fit_image_to_ratio(source_bytes, target_ratio)
            resized = upscale_service.upscale_to_target(
                cropped, sa.target_width, sa.target_height,
            )
            upload = await printify.upload_image_base64(
                image_bytes=resized,
                filename=f"{filename_prefix}_{size_key}.jpg",
            )
            design_groups.append(
                DesignGroup(image_id=upload["id"], variant_ids=[sa.variant_id])
            )
            enabled_sizes.add(size_key)
        except Exception:
            pass  # Skip this size on failure

    # Skipped sizes still need a design group (use original, unfitted)
    skip_vids = [analysis[s].variant_id for s in skip]
    if skip_vids:
        original_upload = await printify.upload_image(
            image_url=image_url,
            filename=f"{filename_prefix}_original.png",
        )
        design_groups.append(
            DesignGroup(image_id=original_upload["id"], variant_ids=skip_vids)
        )

    dpi_dict = {k: v.to_dict() for k, v in analysis.items()}
    return design_groups, enabled_sizes, dpi_dict
