from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sizes import POSTER_SIZES
from deps import exporter, LEONARDO_API_KEY

router = APIRouter(tags=["export"])


@router.get("/export/sizes")
async def get_export_sizes():
    """Get available poster sizes for Printify export."""
    return {
        key: {
            "label": size.label,
            "width": size.width,
            "height": size.height,
            "ratio": size.ratio,
            "priority": size.priority,
            "needs_upscale": size.needs_upscale,
        }
        for key, size in POSTER_SIZES.items()
    }


class ExportRequest(BaseModel):
    generated_image_id: str
    generation_name: str
    sizes: Optional[List[str]] = None  # None = all sizes


@router.post("/export")
async def export_poster(request: ExportRequest):
    """
    Export generated poster to all Printify sizes.

    Pipeline:
    1. Leonardo Universal Upscaler 2x
    2. Optional Real-ESRGAN 2x for large sizes
    3. Pillow LANCZOS resize to each target size
    """
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")

    # Validate sizes
    if request.sizes:
        for s in request.sizes:
            if s not in POSTER_SIZES:
                raise HTTPException(status_code=400, detail=f"Invalid size: {s}")

    try:
        files = await exporter.export_all_sizes(
            generated_image_id=request.generated_image_id,
            generation_name=request.generation_name,
            sizes=request.sizes,
        )

        return {
            "status": "complete",
            "files": files,
            "count": len(files),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{generation_name}/status")
async def get_export_status(generation_name: str):
    """Check which sizes have been exported for a generation."""
    return exporter.get_export_status(generation_name)


@router.get("/export/{generation_name}/{size}")
async def download_exported_file(generation_name: str, size: str):
    """Download a specific exported size as PNG."""
    if size not in POSTER_SIZES:
        raise HTTPException(status_code=400, detail=f"Invalid size: {size}")

    filepath = exporter.get_export_file(generation_name, size)
    if not filepath:
        raise HTTPException(status_code=404, detail="File not found. Export first.")

    return FileResponse(
        filepath,
        media_type="image/png",
        filename=f"{generation_name}_{size}.png",
    )
