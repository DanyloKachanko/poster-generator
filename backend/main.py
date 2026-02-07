import os
import io
import time
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx
from PIL import Image

from leonardo import LeonardoAI
from export import PosterExporter
from sizes import POSTER_SIZES, COMPOSITION_SUFFIX, PRINTIFY_SCALE, PRINTIFY_SCALE_DEFAULT
from listing_generator import ListingGenerator
from pricing import calculate_price, get_all_prices
from printify import PrintifyAPI, create_variants_from_prices, DesignGroup, PrintifyVariant
from dpi import analyze_sizes, get_size_groups
from upscaler import UpscaleService, fit_image_to_ratio
from etsy import EtsyAPI
from presets import get_all_presets, get_preset, get_presets_by_category, get_trending_presets, CATEGORIES
from pod_providers import get_all_providers, compare_providers, RECOMMENDATIONS
from prompt_library import library as prompt_library
from batch import BatchManager
from scheduler import PublishScheduler
from notifications import NotificationService
import database as db

# Load .env from root directory (parent of backend/)
root_env = Path(__file__).parent.parent / ".env"
load_dotenv(root_env)
load_dotenv()  # Also try local .env as fallback


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and scheduler on startup."""
    db.init_db()
    await publish_scheduler.start()
    yield
    await publish_scheduler.stop()


app = FastAPI(title="Poster Generator API", version="1.0.0", lifespan=lifespan)

# CORS configuration - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Leonardo AI client
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
if not LEONARDO_API_KEY:
    print("WARNING: LEONARDO_API_KEY not set. API calls will fail.")

leonardo = LeonardoAI(LEONARDO_API_KEY or "")
exporter = PosterExporter(leonardo, output_dir="./exports")

# Initialize listing generator
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
listing_gen = ListingGenerator(api_key=ANTHROPIC_API_KEY or "")

# Initialize Printify
printify = PrintifyAPI()

# Initialize Notifications & Scheduler
notifier = NotificationService()
publish_scheduler = PublishScheduler(printify, notifier)

# Initialize Etsy
etsy = EtsyAPI()

# Initialize Batch Manager
batch_manager = BatchManager(notifier=notifier)

# Initialize Upscale Service
upscale_service = UpscaleService()

# Default negative prompt for all generations
DEFAULT_NEGATIVE_PROMPT = "text, words, letters, watermark, signature, logo, blurry, low quality, distorted, deformed, ugly, poorly drawn, bad anatomy, extra limbs, disfigured, grain, noise"

# Available models for poster generation (V1 API)
MODELS = {
    "phoenix": {
        "id": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3",
        "name": "Phoenix 1.0",
        "description": "Best prompt adherence and text rendering",
    },
    "kino_xl": {
        "id": "aa77f04e-3eec-4034-9c07-d0f619684628",
        "name": "Kino XL",
        "description": "Cinematic style, great for dramatic scenes",
    },
    "lightning_xl": {
        "id": "b24e16ff-06e3-43eb-8d33-4416c2d75876",
        "name": "Lightning XL",
        "description": "Fast generation, good for iterations",
    },
    "vision_xl": {
        "id": "5c232a9e-9061-4777-980a-ddc8e65647c6",
        "name": "Vision XL",
        "description": "Excels at realism and photography",
    },
    "diffusion_xl": {
        "id": "1e60896f-3c26-4296-8ecc-53e2afecc132",
        "name": "Diffusion XL",
        "description": "Versatile, good for abstract art",
    },
    "anime_xl": {
        "id": "e71a1c2f-4f80-4800-934f-2c68979d8cc8",
        "name": "Anime XL",
        "description": "Anime and illustration style",
    },
}

DEFAULT_MODEL = "phoenix"

# Available poster sizes (dimensions must be multiples of 64 for Leonardo API)
SIZES = {
    "poster_2_3": {
        "name": "Poster 2:3 (Default)",
        "width": 1536,
        "height": 2304,
        "description": "All posters — base ratio, crop to 3:4 / 4:5",
    },
    "poster_4_5": {
        "name": "Poster 4:5",
        "width": 1536,
        "height": 1920,
        "description": "For 8×10, 16×20 inch prints",
    },
    "poster_3_4": {
        "name": "Poster 3:4",
        "width": 1536,
        "height": 2048,
        "description": "For 12×16, 18×24 inch prints",
    },
    "square_1_1": {
        "name": "Square 1:1",
        "width": 1024,
        "height": 1024,
        "description": "Instagram, Etsy thumbnails",
    },
    "landscape_16_9": {
        "name": "Landscape 16:9",
        "width": 1344,
        "height": 768,
        "description": "Widescreen, desktop wallpapers",
    },
}

DEFAULT_SIZE = "poster_2_3"

# Prompt suffix for consistent quality
PROMPT_SUFFIX = ", high resolution, print-ready art, professional quality, no text, no watermark"

# Style presets
STYLE_PRESETS = {
    "japanese": {
        "name": "Japanese",
        "presets": {
            "mountain": {
                "name": "Mountain Landscape",
                "prompt": f"Minimalist Japanese mountain landscape, Mount Fuji silhouette, soft gradient sky, muted earth tones, zen aesthetic, clean lines, modern poster design{PROMPT_SUFFIX}"
            },
            "wave": {
                "name": "Ocean Waves",
                "prompt": f"The Great Wave Japanese style, modern minimalist interpretation, navy blue and cream colors, clean geometric shapes, zen aesthetic, wall art poster{PROMPT_SUFFIX}"
            },
            "cherry": {
                "name": "Cherry Blossom",
                "prompt": f"Cherry blossom branch, minimalist Japanese art, soft pink gradient sky, clean design, zen aesthetic, wall art poster{PROMPT_SUFFIX}"
            },
            "zen": {
                "name": "Zen Garden",
                "prompt": f"Minimalist zen garden illustration, raked sand patterns, single stone, soft neutral colors, meditative aesthetic, modern Japanese poster art{PROMPT_SUFFIX}"
            },
            "torii": {
                "name": "Torii Gate",
                "prompt": f"Floating torii gate silhouette, calm water reflection, misty atmosphere, minimalist Japanese art, red and grey tones, serene aesthetic{PROMPT_SUFFIX}"
            },
            "bamboo": {
                "name": "Bamboo Forest",
                "prompt": f"Bamboo forest, morning mist, vertical composition, minimalist Japanese art, sage green tones, zen aesthetic, modern poster design{PROMPT_SUFFIX}"
            },
            "koi": {
                "name": "Koi Fish",
                "prompt": f"Single koi fish, ink wash style, circular composition, minimalist Japanese art, black and gold, zen aesthetic{PROMPT_SUFFIX}"
            }
        }
    },
    "botanical": {
        "name": "Botanical",
        "presets": {
            "leaves": {
                "name": "Single Leaf",
                "prompt": f"Minimalist botanical line art, single leaf illustration, sage green on cream background, modern poster design, clean aesthetic{PROMPT_SUFFIX}"
            },
            "fern": {
                "name": "Fern Fronds",
                "prompt": f"Delicate fern fronds, botanical illustration, minimalist style, muted green tones, wall art print{PROMPT_SUFFIX}"
            },
            "eucalyptus": {
                "name": "Eucalyptus",
                "prompt": f"Eucalyptus branch watercolor, soft muted colors, minimalist botanical art, modern poster design{PROMPT_SUFFIX}"
            },
            "monstera": {
                "name": "Monstera",
                "prompt": f"Single monstera leaf, deep green on cream background, botanical illustration, minimalist modern art, clean lines{PROMPT_SUFFIX}"
            },
            "wildflower": {
                "name": "Wildflower",
                "prompt": f"Dried pressed wildflower aesthetic, vintage botanical print, muted earth tones, delicate stems, minimalist composition{PROMPT_SUFFIX}"
            },
            "palm": {
                "name": "Palm Leaf",
                "prompt": f"Tropical palm leaf, bold shadow, black and cream contrast, minimalist botanical art, modern poster design{PROMPT_SUFFIX}"
            },
            "succulent": {
                "name": "Succulent",
                "prompt": f"Succulent plant overhead view, rosette pattern, sage and dusty pink tones, minimalist botanical illustration{PROMPT_SUFFIX}"
            },
            "olive": {
                "name": "Olive Branch",
                "prompt": f"Olive branch illustration, Mediterranean style, muted green and cream, minimalist botanical art, elegant composition{PROMPT_SUFFIX}"
            }
        }
    },
    "abstract": {
        "name": "Abstract",
        "presets": {
            "geometric": {
                "name": "Geometric Shapes",
                "prompt": f"Abstract geometric shapes, modern minimalist art, earth tones, clean lines, contemporary wall art poster{PROMPT_SUFFIX}"
            },
            "arch": {
                "name": "Arch Shapes",
                "prompt": f"Abstract arch shapes, terracotta and cream colors, mid-century modern style, minimalist poster art{PROMPT_SUFFIX}"
            },
            "circles": {
                "name": "Overlapping Circles",
                "prompt": f"Overlapping circles, soft gradient colors, abstract minimalist art, modern poster design{PROMPT_SUFFIX}"
            },
            "lines": {
                "name": "Flowing Lines",
                "prompt": f"Flowing parallel lines, wave pattern, smooth gradient, abstract minimalist art, modern poster design{PROMPT_SUFFIX}"
            },
            "blocks": {
                "name": "Color Blocks",
                "prompt": f"Abstract color blocks, Rothko inspired, soft edges, muted earth tones, contemplative minimalist art{PROMPT_SUFFIX}"
            },
            "marble": {
                "name": "Marble Texture",
                "prompt": f"Abstract marble texture, gold veins on white, luxurious minimalist art, elegant poster design{PROMPT_SUFFIX}"
            },
            "gradient": {
                "name": "Gradient Orb",
                "prompt": f"Smooth gradient orb, sunset colors, soft abstract art, modern minimalist poster, warm tones{PROMPT_SUFFIX}"
            }
        }
    },
    "celestial": {
        "name": "Celestial",
        "presets": {
            "moon": {
                "name": "Moon Phases",
                "prompt": f"Minimalist moon phases illustration, soft gradient sky, celestial wall art, cream and navy colors, modern poster design{PROMPT_SUFFIX}"
            },
            "stars": {
                "name": "Starry Night",
                "prompt": f"Abstract starry night, minimalist style, deep blue gradient, scattered stars, modern celestial poster art{PROMPT_SUFFIX}"
            },
            "sun": {
                "name": "Sun Rays",
                "prompt": f"Abstract sun rays, warm gradient colors, minimalist celestial art, modern poster design{PROMPT_SUFFIX}"
            },
            "constellation": {
                "name": "Constellation",
                "prompt": f"Single constellation diagram, fine lines connecting stars, navy blue background, astronomical minimalist art{PROMPT_SUFFIX}"
            },
            "eclipse": {
                "name": "Solar Eclipse",
                "prompt": f"Total solar eclipse, black and gold, corona rays, dramatic celestial art, minimalist poster design{PROMPT_SUFFIX}"
            },
            "nebula": {
                "name": "Nebula Cloud",
                "prompt": f"Watercolor nebula cloud, purple blue pink gradient, soft cosmic art, abstract celestial poster{PROMPT_SUFFIX}"
            },
            "planets": {
                "name": "Solar System",
                "prompt": f"Solar system planets in line, pastel colors, minimalist astronomical art, modern poster design{PROMPT_SUFFIX}"
            }
        }
    },
    "landscape": {
        "name": "Landscape",
        "presets": {
            "desert": {
                "name": "Desert Dunes",
                "prompt": f"Desert sand dunes, golden hour light, minimalist landscape art, warm earth tones, serene composition{PROMPT_SUFFIX}"
            },
            "ocean": {
                "name": "Ocean Horizon",
                "prompt": f"Calm ocean horizon, pastel sunrise colors, minimalist seascape, peaceful composition, soft gradients{PROMPT_SUFFIX}"
            },
            "forest": {
                "name": "Misty Forest",
                "prompt": f"Misty forest silhouette layers, minimalist landscape art, muted green and grey tones, atmospheric depth{PROMPT_SUFFIX}"
            },
            "mountain": {
                "name": "Mountain Range",
                "prompt": f"Mountain range silhouettes, sunset gradient sky, layered minimalist landscape, warm to cool tones{PROMPT_SUFFIX}"
            },
            "lake": {
                "name": "Still Lake",
                "prompt": f"Still lake with perfect reflection, minimalist landscape, soft blue and grey tones, peaceful symmetry{PROMPT_SUFFIX}"
            },
            "field": {
                "name": "Golden Field",
                "prompt": f"Single tree in golden wheat field, golden hour light, minimalist landscape art, warm earth tones{PROMPT_SUFFIX}"
            },
            "aurora": {
                "name": "Northern Lights",
                "prompt": f"Northern lights aurora borealis, snowy landscape silhouette, green and purple sky, minimalist art{PROMPT_SUFFIX}"
            }
        }
    }
}


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


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Poster Generator API is running"}


@app.get("/health")
async def health():
    """Health check with DB connectivity test (for container orchestration)."""
    import aiosqlite
    try:
        async with aiosqlite.connect(db.DB_PATH) as conn:
            await conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    status = "healthy" if db_status == "ok" else "unhealthy"
    code = 200 if db_status == "ok" else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=code,
        content={
            "status": status,
            "database": db_status,
            "scheduler": "running" if publish_scheduler.scheduler.running else "stopped",
        },
    )


@app.get("/styles")
async def get_styles():
    """Return all available style presets."""
    return STYLE_PRESETS


@app.get("/models")
async def get_models():
    """Return all available AI models."""
    return MODELS


@app.get("/sizes")
async def get_sizes():
    """Return all available poster sizes."""
    return SIZES


@app.get("/defaults")
async def get_defaults():
    """Return default values for generation."""
    return {
        "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
        "model": DEFAULT_MODEL,
        "size": DEFAULT_SIZE,
    }


@app.post("/generate", response_model=GenerateResponse)
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


@app.get("/generation/{generation_id}", response_model=GenerationStatusResponse)
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


@app.get("/credits")
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


@app.get("/history")
async def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    style: Optional[str] = Query(default=None, description="Filter by style"),
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
            model_id=model_id,
            archived=archived
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{generation_id}")
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


@app.post("/history/{generation_id}/archive")
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


@app.post("/history/{generation_id}/restore")
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


@app.get("/export/sizes")
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


@app.post("/export")
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


@app.get("/export/{generation_name}/status")
async def get_export_status(generation_name: str):
    """Check which sizes have been exported for a generation."""
    return exporter.get_export_status(generation_name)


@app.get("/export/{generation_name}/{size}")
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


# === LISTING GENERATION ENDPOINTS ===

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


@app.post("/generate-listing", response_model=ListingResponse)
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


@app.post("/regenerate-title")
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


@app.post("/regenerate-description")
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


@app.post("/regenerate-tags")
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


# === PRICING ENDPOINTS ===

@app.get("/pricing/{size}")
async def get_price_recommendation(
    size: str,
    strategy: str = "standard",
    free_shipping: bool = True,
):
    """Get recommended price for a poster size."""
    return calculate_price(size, strategy, free_shipping)


@app.get("/pricing")
async def get_all_price_recommendations(strategy: str = "standard"):
    """Get recommended prices for all sizes."""
    return get_all_prices(strategy)


# === PRINTIFY FULL AUTOMATION ===

class FullCreateRequest(BaseModel):
    style: str
    preset: str
    description: str
    image_url: str
    pricing_strategy: str = "standard"
    publish_to_etsy: bool = False
    preset_id: Optional[str] = None


@app.post("/create-full-product")
async def create_full_product(request: FullCreateRequest):
    """
    Full automation: Generate listing text + Create Printify product.

    1. Generate title, tags, description via Claude
    2. Calculate pricing
    3. Upload image to Printify
    4. Create product with all sizes and prices
    5. Optionally publish to Etsy
    """
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

    try:
        # Step 1: Generate listing text
        listing = await listing_gen.generate_listing(
            style=request.style,
            preset=request.preset,
            description=request.description,
        )

        # Step 2: Get pricing
        prices = get_all_prices(request.pricing_strategy)

        # Step 3: DPI-aware multi-design upload
        filename_prefix = f"{request.style}_{request.preset}_{int(time.time())}"
        design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
            image_url=request.image_url,
            filename_prefix=filename_prefix,
        )

        # Step 4: Create variants with DPI-aware enabled sizes
        variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)

        # Step 5: Create product with per-variant designs
        product = await printify.create_product_multidesign(
            title=listing.title,
            description=listing.description,
            tags=listing.tags,
            design_groups=design_groups,
            variants=variants,
        )

        # Notify: product created
        await notifier.notify_product_created(listing.title, product.id)

        # Step 6: Optionally schedule for Etsy publishing
        scheduled_publish_at = None
        if request.publish_to_etsy:
            schedule_result = await publish_scheduler.add_to_queue(
                printify_product_id=product.id,
                title=listing.title,
            )
            scheduled_publish_at = schedule_result["scheduled_publish_at"]

        # Track preset usage
        if request.preset_id:
            await db.mark_preset_used(request.preset_id, product.id, listing.title)

        return {
            "printify_product_id": product.id,
            "title": listing.title,
            "tags": listing.tags,
            "description": listing.description,
            "pricing": prices,
            "status": product.status,
            "scheduled_publish_at": scheduled_publish_at,
            "dpi_analysis": dpi_analysis,
            "enabled_sizes": sorted(enabled_sizes),
            "upscale_backend": upscale_service.backend_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/printify/status")
async def get_printify_status():
    """Check if Printify is configured and accessible."""
    if not printify.is_configured:
        return {"configured": False, "connected": False}

    try:
        shops = await printify.get_shops()
        return {
            "configured": True,
            "connected": True,
            "shops": [{"id": s["id"], "title": s["title"]} for s in shops],
        }
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}


@app.get("/printify/products")
async def list_printify_products(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List products in the Printify shop."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.list_products(page=page, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/printify/products/{product_id}")
async def get_printify_product(product_id: str):
    """Get a single Printify product."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        product = await printify.get_product(product_id)
        return product
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/printify/products/{product_id}/publish")
async def publish_printify_product(product_id: str):
    """Publish a product to the connected store (Etsy)."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.publish_product(product_id)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/printify/products/{product_id}/unpublish")
async def unpublish_printify_product(product_id: str):
    """Unpublish a product from the connected store."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.unpublish_product(product_id)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/printify/products/{product_id}")
async def delete_printify_product(product_id: str):
    """Delete a product from Printify."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        await printify.delete_product(product_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateProductRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    variants: Optional[List[dict]] = None


@app.put("/printify/products/{product_id}")
async def update_printify_product(product_id: str, request: UpdateProductRequest):
    """Update product details on Printify."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.update_product(
            product_id=product_id,
            title=request.title,
            description=request.description,
            tags=request.tags,
            variants=request.variants,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/printify/products/{product_id}/republish")
async def republish_printify_product(product_id: str):
    """Re-publish product to push updates to Etsy."""
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.publish_product(product_id)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === FIX EXISTING PRODUCTS ===

@app.post("/printify/fix-existing-products")
async def fix_existing_products(
    dry_run: bool = Query(default=True, description="Preview changes without applying"),
):
    """Disable blurry large-size variants on existing products.

    Disables 16x20, 18x24, 24x36 variants that were created before
    DPI-aware sizing was implemented.
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    large_variant_ids = [
        PrintifyAPI.SIZE_VARIANT_IDS["16x20"],  # 43141
        PrintifyAPI.SIZE_VARIANT_IDS["18x24"],  # 43144
        PrintifyAPI.SIZE_VARIANT_IDS["24x36"],  # 43150
    ]

    try:
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])

        fixed = []
        skipped = []

        for product in products:
            pid = product["id"]
            title = product.get("title", "Untitled")
            variants = product.get("variants", [])

            # Check if any large variants are currently enabled
            enabled_large = [
                v for v in variants
                if v["id"] in large_variant_ids and v.get("is_enabled", False)
            ]

            if not enabled_large:
                skipped.append({"id": pid, "title": title, "reason": "no large variants enabled"})
                continue

            if dry_run:
                fixed.append({
                    "id": pid,
                    "title": title,
                    "variants_to_disable": [v["id"] for v in enabled_large],
                    "action": "would_disable",
                })
            else:
                await printify.disable_variants(pid, large_variant_ids)

                # Re-publish to sync changes to Etsy
                external = product.get("external")
                if external and external.get("id"):
                    try:
                        await printify.publish_product(pid)
                    except Exception:
                        pass  # Non-fatal if republish fails

                fixed.append({
                    "id": pid,
                    "title": title,
                    "variants_disabled": [v["id"] for v in enabled_large],
                    "action": "disabled",
                })

        return {
            "dry_run": dry_run,
            "fixed": fixed,
            "skipped": skipped,
            "total_fixed": len(fixed),
            "total_skipped": len(skipped),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/printify/upgrade-product/{product_id}")
async def upgrade_product_with_upscale(product_id: str):
    """Upgrade an existing product with per-size cropped + upscaled images.

    Each poster size gets its own image cropped to the exact aspect ratio
    and resized to exact Printify target pixels. Eliminates white padding.
    Unknown variants (squares etc.) get the original unfitted image.
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        # Get current product
        product = await printify.get_product(product_id)
        title = product.get("title", "Untitled")

        # Find the original design image from print_areas (not mockups)
        source_url = None
        for pa in product.get("print_areas", []):
            for ph in pa.get("placeholders", []):
                for img in ph.get("images", []):
                    if img.get("src"):
                        source_url = img["src"]
                        break
                if source_url:
                    break
            if source_url:
                break

        if not source_url:
            raise HTTPException(status_code=400, detail="No design image found in print_areas")

        # Download source image
        async with httpx.AsyncClient() as client:
            resp = await client.get(source_url, timeout=60.0)
            resp.raise_for_status()
            source_bytes = resp.content

        # Get dimensions and analyze DPI
        img = Image.open(io.BytesIO(source_bytes))
        src_w, src_h = img.size
        analysis = analyze_sizes(src_w, src_h)
        _original_ok, _needs_upscale, skip = get_size_groups(analysis)

        sellable = [k for k, sa in analysis.items() if sa.is_sellable]
        if not sellable:
            raise HTTPException(
                status_code=400,
                detail=f"No sellable sizes for {src_w}x{src_h} image",
            )

        filename_prefix = f"upgrade_{product_id}_{int(time.time())}"

        # Collect ALL variant IDs from the product (Printify requires all in print_areas)
        all_product_variant_ids = [v["id"] for v in product.get("variants", [])]
        assigned_variant_ids = set()

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
                assigned_variant_ids.add(sa.variant_id)
            except Exception:
                pass  # Skip this size on failure

        # All remaining variant IDs (skipped sizes + unknown squares etc.)
        # go with original unfitted image
        remaining_vids = [
            vid for vid in all_product_variant_ids
            if vid not in assigned_variant_ids
        ]
        if remaining_vids:
            original_upload = await printify.upload_image(
                image_url=source_url,
                filename=f"{filename_prefix}_original.png",
            )
            design_groups.append(
                DesignGroup(image_id=original_upload["id"], variant_ids=remaining_vids)
            )

        # Build print_areas payload with per-size scale overrides
        vid_to_size = {vid: sk for sk, vid in PrintifyAPI.SIZE_VARIANT_IDS.items()}
        print_areas = []
        for group in design_groups:
            size_key = vid_to_size.get(group.variant_ids[0]) if len(group.variant_ids) == 1 else None
            scale = PRINTIFY_SCALE.get(size_key, PRINTIFY_SCALE_DEFAULT) if size_key else PRINTIFY_SCALE_DEFAULT
            print_areas.append({
                "variant_ids": group.variant_ids,
                "placeholders": [{
                    "position": "front",
                    "images": [{
                        "id": group.image_id,
                        "x": 0.5,
                        "y": 0.5,
                        "scale": scale,
                        "angle": 0,
                    }],
                }],
            })

        # Build updated variants with correct enabled state
        updated_variants = []
        for v in product.get("variants", []):
            vid = v["id"]
            size_key = None
            for sk, sv_id in PrintifyAPI.SIZE_VARIANT_IDS.items():
                if sv_id == vid:
                    size_key = sk
                    break
            if size_key:
                is_enabled = size_key in enabled_sizes
            else:
                is_enabled = v.get("is_enabled", False)
            updated_variants.append({
                "id": vid,
                "price": v["price"],
                "is_enabled": is_enabled,
            })

        # Update product with new print_areas and variants
        await printify.update_product(
            product_id=product_id,
            variants=updated_variants,
            print_areas=print_areas,
        )

        # Re-publish to Etsy if already published
        was_published = False
        external = product.get("external")
        if external and external.get("id"):
            try:
                await printify.publish_product(product_id)
                was_published = True
            except Exception:
                pass

        dpi_dict = {k: v.to_dict() for k, v in analysis.items()}
        return {
            "product_id": product_id,
            "title": title,
            "source_resolution": f"{src_w}x{src_h}",
            "enabled_sizes": sorted(enabled_sizes),
            "skipped_sizes": skip,
            "design_groups": len(design_groups),
            "upscale_backend": upscale_service.backend_name,
            "republished": was_published,
            "dpi_analysis": dpi_dict,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/printify/upgrade-all-products")
async def upgrade_all_products(
    dry_run: bool = Query(default=True, description="Preview changes without applying"),
):
    """Upgrade ALL existing products with DPI-aware upscaled images.

    For each product: downloads source image, upscales, updates print_areas,
    enables all sellable sizes, re-publishes.
    """
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])

        results = []
        for product in products:
            pid = product["id"]
            title = product.get("title", "Untitled")

            if dry_run:
                # Just analyze what would happen — get design from print_areas
                source_url = None
                for pa in product.get("print_areas", []):
                    for ph in pa.get("placeholders", []):
                        for img_pa in ph.get("images", []):
                            if img_pa.get("src"):
                                source_url = img_pa["src"]
                                break
                        if source_url:
                            break
                    if source_url:
                        break

                if not source_url:
                    results.append({"id": pid, "title": title, "action": "skip", "reason": "no image"})
                    continue

                # Download to check dimensions
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(source_url, timeout=30.0)
                        resp.raise_for_status()
                        img_obj = Image.open(io.BytesIO(resp.content))
                        src_w, src_h = img_obj.size

                    analysis = analyze_sizes(src_w, src_h)
                    ok, up, sk = get_size_groups(analysis)

                    # Check currently enabled variants
                    current_enabled = [
                        v["id"] for v in product.get("variants", [])
                        if v.get("is_enabled", False)
                    ]

                    results.append({
                        "id": pid,
                        "title": title,
                        "action": "would_upgrade",
                        "source_resolution": f"{src_w}x{src_h}",
                        "would_enable": sorted(ok + up),
                        "would_skip": sk,
                        "currently_enabled_count": len(current_enabled),
                    })
                except Exception as exc:
                    results.append({"id": pid, "title": title, "action": "skip", "reason": str(exc)})
            else:
                # Actually upgrade
                try:
                    upgrade_result = await upgrade_product_with_upscale(pid)
                    results.append({
                        "id": pid,
                        "title": title,
                        "action": "upgraded",
                        "enabled_sizes": upgrade_result.get("enabled_sizes", []),
                        "upscale_backend": upgrade_result.get("upscale_backend", ""),
                    })
                except Exception as exc:
                    results.append({"id": pid, "title": title, "action": "failed", "error": str(exc)})

        return {
            "dry_run": dry_run,
            "products": results,
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === PRESETS ENDPOINTS ===

@app.get("/presets")
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


@app.post("/presets/mark-used")
async def mark_presets_used(items: List[MarkUsedItem]):
    """Mark presets as used (link to Printify products)."""
    for item in items:
        await db.mark_preset_used(item.preset_id, item.printify_product_id, item.title)
    return {"marked": len(items)}


@app.get("/presets/trending")
async def trending_presets(limit: int = Query(default=10, le=30)):
    """Get top trending presets."""
    return {"presets": get_trending_presets(limit)}


@app.get("/presets/{preset_id}")
async def get_single_preset(preset_id: str):
    """Get a single preset by ID."""
    preset = get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@app.get("/presets/{preset_id}/products")
async def get_preset_products_endpoint(preset_id: str):
    """Get products created from a specific preset."""
    return await db.get_preset_products(preset_id)


@app.get("/categories")
async def list_categories():
    """Get all preset categories."""
    return CATEGORIES


# === POD PROVIDERS ENDPOINTS ===

@app.get("/providers")
async def list_providers():
    """Get all POD provider information."""
    return {
        "providers": get_all_providers(),
        "recommendations": RECOMMENDATIONS,
    }


@app.get("/providers/compare")
async def compare_pod_providers(size: str = Query(default="18x24")):
    """Compare providers for a specific poster size."""
    return {"size": size, "providers": compare_providers(size)}


# === DASHBOARD ENDPOINTS ===

@app.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get overall dashboard statistics."""
    try:
        gen_stats = await db.get_generation_stats()
        analytics = await db.get_analytics_summary()

        total_views = sum(a.get("total_views", 0) for a in analytics)
        total_favorites = sum(a.get("total_favorites", 0) for a in analytics)
        total_orders = sum(a.get("total_orders", 0) for a in analytics)
        total_revenue = sum(a.get("total_revenue_cents", 0) for a in analytics)

        # Count products on Printify
        products_count = 0
        published_count = 0
        if printify.is_configured:
            try:
                result = await printify.list_products(page=1, limit=50)
                products = result.get("data", [])
                products_count = len(products)
                published_count = sum(
                    1 for p in products
                    if p.get("external") and p["external"].get("id")
                )
            except Exception:
                pass

        return {
            "total_generated": gen_stats.get("total_generations", 0),
            "total_images": gen_stats.get("total_images", 0),
            "total_credits_used": gen_stats.get("total_credits_used", 0),
            "total_products": products_count,
            "total_published": published_count,
            "total_views": total_views,
            "total_favorites": total_favorites,
            "total_orders": total_orders,
            "total_revenue_cents": total_revenue,
            "by_status": gen_stats.get("by_status", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === ANALYTICS ENDPOINTS ===

class AnalyticsEntryRequest(BaseModel):
    printify_product_id: str
    date: str
    views: int = 0
    favorites: int = 0
    orders: int = 0
    revenue_cents: int = 0
    notes: Optional[str] = None


@app.get("/analytics")
async def get_analytics():
    """
    Get all products with aggregated analytics.
    Merges Printify product data with local SQLite analytics.
    """
    try:
        # Get analytics summary from SQLite
        analytics = await db.get_analytics_summary()
        analytics_map = {a["printify_product_id"]: a for a in analytics}

        # Get products from Printify
        products = []
        if printify.is_configured:
            try:
                result = await printify.list_products(page=1, limit=50)
                products = result.get("data", [])
            except Exception:
                pass

        # Merge: build list with product info + analytics
        merged = []
        for product in products:
            pid = product["id"]
            a = analytics_map.pop(pid, {})

            # Get thumbnail from images
            thumbnail = None
            for img in product.get("images", []):
                if img.get("is_default"):
                    thumbnail = img.get("src")
                    break
            if not thumbnail and product.get("images"):
                thumbnail = product["images"][0].get("src")

            # Get price range from enabled variants
            enabled_variants = [v for v in product.get("variants", []) if v.get("is_enabled")]
            prices = [v.get("price", 0) for v in enabled_variants]
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0

            # Etsy status
            external = product.get("external")
            etsy_url = None
            if external and external.get("handle"):
                handle = external["handle"]
                etsy_url = handle if handle.startswith("http") else f"https://{handle}"

            merged.append({
                "printify_product_id": pid,
                "title": product.get("title", "Untitled"),
                "thumbnail": thumbnail,
                "status": "on_etsy" if external and external.get("id") else "draft",
                "min_price": min_price,
                "max_price": max_price,
                "etsy_url": etsy_url,
                "total_views": a.get("total_views", 0),
                "total_favorites": a.get("total_favorites", 0),
                "total_orders": a.get("total_orders", 0),
                "total_revenue_cents": a.get("total_revenue_cents", 0),
                "latest_date": a.get("latest_date"),
            })

        # Include any analytics entries for products no longer on Printify
        for pid, a in analytics_map.items():
            merged.append({
                "printify_product_id": pid,
                "title": "Deleted Product",
                "thumbnail": None,
                "status": "deleted",
                "min_price": 0,
                "max_price": 0,
                "etsy_url": None,
                "total_views": a.get("total_views", 0),
                "total_favorites": a.get("total_favorites", 0),
                "total_orders": a.get("total_orders", 0),
                "total_revenue_cents": a.get("total_revenue_cents", 0),
                "latest_date": a.get("latest_date"),
            })

        # Summary totals
        totals = {
            "total_views": sum(p["total_views"] for p in merged),
            "total_favorites": sum(p["total_favorites"] for p in merged),
            "total_orders": sum(p["total_orders"] for p in merged),
            "total_revenue_cents": sum(p["total_revenue_cents"] for p in merged),
        }

        return {
            "products": merged,
            "totals": totals,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analytics")
async def save_analytics_entry(request: AnalyticsEntryRequest):
    """Upsert analytics entry for a product on a given date."""
    try:
        await db.save_analytics(
            printify_product_id=request.printify_product_id,
            date=request.date,
            views=request.views,
            favorites=request.favorites,
            orders=request.orders,
            revenue_cents=request.revenue_cents,
            notes=request.notes,
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/{product_id}/history")
async def get_product_analytics(product_id: str):
    """Get historical analytics entries for a single product."""
    try:
        entries = await db.get_product_analytics_history(product_id)
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === ETSY OAUTH + SYNC ENDPOINTS ===

# In-memory PKCE state (simple single-user approach)
_etsy_pkce_state: dict = {}


@app.get("/etsy/status")
async def get_etsy_status():
    """Check if Etsy is connected."""
    if not etsy.is_configured:
        return {"configured": False, "connected": False}

    tokens = await db.get_etsy_tokens()
    if not tokens:
        return {"configured": True, "connected": False}

    # Check if tokens are expired and try refresh
    if tokens["expires_at"] < int(time.time()):
        try:
            new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
            await db.save_etsy_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
            )
            return {"configured": True, "connected": True, "shop_id": tokens.get("shop_id")}
        except Exception:
            return {"configured": True, "connected": False, "error": "Token expired, re-connect needed"}

    return {"configured": True, "connected": True, "shop_id": tokens.get("shop_id")}


@app.get("/etsy/auth-url")
async def get_etsy_auth_url():
    """Generate Etsy OAuth authorization URL."""
    global _etsy_pkce_state

    if not etsy.is_configured:
        raise HTTPException(status_code=400, detail="ETSY_API_KEY not configured in .env")

    auth_data = etsy.get_auth_url()
    _etsy_pkce_state = {
        "state": auth_data["state"],
        "code_verifier": auth_data["code_verifier"],
    }

    return {"url": auth_data["url"]}


@app.get("/etsy/callback")
async def etsy_oauth_callback(code: str, state: str):
    """OAuth callback — exchanges code for tokens."""
    global _etsy_pkce_state

    if not _etsy_pkce_state or _etsy_pkce_state.get("state") != state:
        return {"error": "Invalid state. Please try connecting again."}

    try:
        tokens = await etsy.exchange_code(code, _etsy_pkce_state["code_verifier"])
        _etsy_pkce_state = {}

        # Get user info to find shop_id
        user_info = await etsy.get_me(tokens.access_token)
        etsy_user_id = str(user_info.get("user_id", ""))
        shop_id = str(user_info.get("shop_id", ""))

        await db.save_etsy_tokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.expires_at,
            etsy_user_id=etsy_user_id,
            shop_id=shop_id,
        )

        # Return an HTML page that closes itself and notifies opener
        return HTMLResponse("""
            <html><body>
            <h2>Etsy connected successfully!</h2>
            <p>You can close this window.</p>
            <script>
                if (window.opener) {
                    window.opener.postMessage('etsy-connected', '*');
                }
                setTimeout(() => window.close(), 1500);
            </script>
            </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"""
            <html><body>
            <h2>Connection failed</h2>
            <p>{str(e)}</p>
            <p>Please close this window and try again.</p>
            </body></html>
        """)


@app.post("/etsy/disconnect")
async def disconnect_etsy():
    """Remove stored Etsy tokens."""
    await db.delete_etsy_tokens()
    return {"ok": True}


@app.post("/etsy/sync")
async def sync_etsy_analytics():
    """
    Fetch views/favorites from Etsy for all Printify products.
    Saves lifetime totals as today's snapshot.
    """
    tokens = await db.get_etsy_tokens()
    if not tokens:
        raise HTTPException(status_code=400, detail="Etsy not connected")

    # Auto-refresh if expired
    access_token = tokens["access_token"]
    if tokens["expires_at"] < int(time.time()):
        try:
            new_tokens = await etsy.refresh_access_token(tokens["refresh_token"])
            await db.save_etsy_tokens(
                access_token=new_tokens.access_token,
                refresh_token=new_tokens.refresh_token,
                expires_at=new_tokens.expires_at,
            )
            access_token = new_tokens.access_token
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token refresh failed: {e}")

    # Get Printify products to find Etsy listing IDs
    if not printify.is_configured:
        raise HTTPException(status_code=400, detail="Printify not configured")

    try:
        result = await printify.list_products(page=1, limit=50)
        products = result.get("data", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Printify products: {e}")

    today = time.strftime("%Y-%m-%d")
    synced = []

    for product in products:
        external = product.get("external")
        if not external or not external.get("id"):
            continue

        etsy_listing_id = external["id"]
        printify_product_id = product["id"]

        try:
            listing = await etsy.get_listing(access_token, etsy_listing_id)
            views = listing.get("views", 0) or 0
            favorites = listing.get("num_favorers", 0) or 0

            await db.save_analytics(
                printify_product_id=printify_product_id,
                date=today,
                views=views,
                favorites=favorites,
                notes="etsy_sync",
            )

            synced.append({
                "printify_product_id": printify_product_id,
                "etsy_listing_id": etsy_listing_id,
                "title": product.get("title", ""),
                "views": views,
                "favorites": favorites,
            })
        except Exception as e:
            synced.append({
                "printify_product_id": printify_product_id,
                "etsy_listing_id": etsy_listing_id,
                "error": str(e),
            })

    return {"synced": len(synced), "products": synced, "date": today}


# === DPI ANALYSIS ENDPOINTS ===

@app.get("/dpi/analyze")
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


# === PROMPT LIBRARY ENDPOINTS ===

@app.get("/library/categories")
async def get_library_categories():
    """Get all prompt library categories."""
    return {"categories": prompt_library.get_categories()}


@app.get("/library/prompts")
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


@app.get("/library/prompts/{prompt_id}")
async def get_library_prompt(prompt_id: str):
    """Get a single prompt from the library."""
    prompt = prompt_library.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


# === BATCH GENERATION ENDPOINTS ===

class BatchGenerateRequest(BaseModel):
    prompt_ids: List[str]
    model_id: str = "phoenix"
    size_id: str = "poster_2_3"
    num_images_per_prompt: int = Field(default=1, ge=1, le=2)
    use_variations: bool = False
    variation_index: Optional[int] = None
    delay_between: float = Field(default=3.0, ge=1.0, le=30.0)


@app.post("/batch/generate")
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


@app.get("/batch")
async def list_batches():
    """List all batch jobs."""
    return {"batches": batch_manager.list_batches()}


@app.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get detailed batch status with per-item progress."""
    job = batch_manager.get_batch(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    return job.to_dict(include_items=True)


@app.post("/batch/{batch_id}/cancel")
async def cancel_batch(batch_id: str):
    """Cancel a running batch."""
    success = batch_manager.cancel_batch(batch_id)
    if not success:
        raise HTTPException(status_code=400, detail="Batch not found or not running")
    return {"ok": True}


# === PIPELINE AUTO-PRODUCT ENDPOINT ===

class AutoProductRequest(BaseModel):
    prompt_id: str
    model_id: str = "phoenix"
    size_id: str = "poster_2_3"
    pricing_strategy: str = "standard"
    publish_to_etsy: bool = False
    custom_title: Optional[str] = None
    custom_tags: Optional[List[str]] = None
    preset_id: Optional[str] = None


@app.post("/pipeline/auto-product")
async def auto_create_product(request: AutoProductRequest):
    """
    Full automation: Library prompt -> Generate -> Listing -> Printify -> Etsy.

    1. Get prompt from library
    2. Generate image via Leonardo + poll
    3. Generate listing text via Claude (with library tags)
    4. Upload to Printify + create product
    5. Optionally publish to Etsy
    """
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")
    if not printify.is_configured:
        raise HTTPException(status_code=500, detail="Printify not configured")

    # Get prompt from library
    lib_prompt = prompt_library.get_prompt(request.prompt_id)
    if not lib_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found in library")

    lib_prompt_obj = prompt_library.get_prompt_obj(request.prompt_id)
    category = prompt_library.get_category(lib_prompt["category"])

    # Validate model and size
    model_info = MODELS.get(request.model_id)
    if not model_info:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model_id}")
    size_info = SIZES.get(request.size_id)
    if not size_info:
        raise HTTPException(status_code=400, detail=f"Unknown size: {request.size_id}")

    try:
        # Step 1: Generate image (add composition suffix for crop safety)
        auto_prompt = lib_prompt["prompt"] + COMPOSITION_SUFFIX
        gen_result = await leonardo.create_generation(
            prompt=auto_prompt,
            model_id=model_info["id"],
            num_images=1,
            negative_prompt=lib_prompt.get("negative_prompt", ""),
            width=size_info["width"],
            height=size_info["height"],
        )
        gen_id = gen_result["generation_id"]

        # Save to DB (store original prompt)
        await db.save_generation(
            generation_id=gen_id,
            prompt=lib_prompt["prompt"],
            negative_prompt=lib_prompt.get("negative_prompt", ""),
            model_id=model_info["id"],
            model_name=model_info["name"],
            style=lib_prompt["category"],
            preset=request.prompt_id,
            width=size_info["width"],
            height=size_info["height"],
            num_images=1,
        )

        # Step 2: Poll for completion
        completed = await leonardo.wait_for_generation(gen_id, poll_interval=3.0, timeout=120.0)
        if completed["status"] != "COMPLETE" or not completed.get("images"):
            raise HTTPException(status_code=500, detail="Image generation failed")

        await db.update_generation_status(gen_id, "COMPLETE", completed.get("api_credit_cost", 0))
        await db.save_generated_images(gen_id, completed["images"])

        image_url = completed["images"][0]["url"]

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

        # Step 4: DPI-aware multi-design upload
        prices = get_all_prices(request.pricing_strategy)
        filename_prefix = f"{request.prompt_id}_{int(time.time())}"
        design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
            image_url=image_url,
            filename_prefix=filename_prefix,
        )

        # Step 5: Create product with per-variant designs
        variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)
        product = await printify.create_product_multidesign(
            title=title,
            description=listing.description,
            tags=tags,
            design_groups=design_groups,
            variants=variants,
        )

        # Notify: product created
        await notifier.notify_product_created(title, product.id)

        # Step 6: Optionally schedule for Etsy publishing
        scheduled_publish_at = None
        if request.publish_to_etsy:
            schedule_result = await publish_scheduler.add_to_queue(
                printify_product_id=product.id,
                title=title,
            )
            scheduled_publish_at = schedule_result["scheduled_publish_at"]

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


# === Preset-based Product Pipeline ===


class PresetProductRequest(BaseModel):
    preset_id: str
    model_id: str = "phoenix"
    size_id: str = "poster_2_3"
    pricing_strategy: str = "standard"
    publish_to_etsy: bool = False
    seo_instruction: Optional[str] = None


@app.post("/pipeline/preset-product")
async def preset_create_product(request: PresetProductRequest):
    """
    Full automation from a preset: Preset -> Generate -> Listing -> Printify.

    1. Get preset from presets.py
    2. Generate image via Leonardo + poll
    3. Generate listing text via Claude (with preset tags + optional SEO instruction)
    4. Upload to Printify + create product (draft)
    5. Mark preset as used
    """
    if not LEONARDO_API_KEY:
        raise HTTPException(status_code=500, detail="Leonardo API key not configured")
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")
    if not printify.is_configured:
        raise HTTPException(status_code=500, detail="Printify not configured")

    preset = get_preset(request.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {request.preset_id}")

    model_info = MODELS.get(request.model_id)
    if not model_info:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model_id}")
    size_info = SIZES.get(request.size_id)
    if not size_info:
        raise HTTPException(status_code=400, detail=f"Unknown size: {request.size_id}")

    try:
        # Step 1: Generate image (cap dimensions to Leonardo max of 1536)
        gen_prompt = preset["prompt"] + COMPOSITION_SUFFIX
        gen_width = min(size_info["width"], 1536)
        gen_height = min(size_info["height"], 1536)
        gen_result = await leonardo.create_generation(
            prompt=gen_prompt,
            model_id=model_info["id"],
            num_images=1,
            negative_prompt=preset.get("negative_prompt", ""),
            width=gen_width,
            height=gen_height,
        )
        gen_id = gen_result["generation_id"]

        await db.save_generation(
            generation_id=gen_id,
            prompt=preset["prompt"],
            negative_prompt=preset.get("negative_prompt", ""),
            model_id=model_info["id"],
            model_name=model_info["name"],
            style=preset["category"],
            preset=request.preset_id,
            width=size_info["width"],
            height=size_info["height"],
            num_images=1,
        )

        # Step 2: Poll for completion
        completed = await leonardo.wait_for_generation(gen_id, poll_interval=3.0, timeout=120.0)
        if completed["status"] != "COMPLETE" or not completed.get("images"):
            raise HTTPException(status_code=500, detail="Image generation failed")

        await db.update_generation_status(gen_id, "COMPLETE", completed.get("api_credit_cost", 0))
        await db.save_generated_images(gen_id, completed["images"])
        image_url = completed["images"][0]["url"]

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

        # Step 4: DPI-aware multi-design upload
        prices = get_all_prices(request.pricing_strategy)
        filename_prefix = f"{request.preset_id}_{int(time.time())}"
        design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
            image_url=image_url,
            filename_prefix=filename_prefix,
        )

        variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)
        product = await printify.create_product_multidesign(
            title=title,
            description=listing.description,
            tags=tags,
            design_groups=design_groups,
            variants=variants,
        )

        # Notify: product created
        await notifier.notify_product_created(title, product.id)

        # Step 5: Mark preset as used
        await db.mark_preset_used(request.preset_id, product.id, title)

        # Optionally schedule for publishing
        scheduled_publish_at = None
        if request.publish_to_etsy:
            schedule_result = await publish_scheduler.add_to_queue(
                printify_product_id=product.id,
                title=title,
            )
            scheduled_publish_at = schedule_result["scheduled_publish_at"]

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
            "preset_id": request.preset_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Scheduled Publishing ===


class ScheduleAddRequest(BaseModel):
    printify_product_id: str
    title: str
    scheduled_publish_at: Optional[str] = None  # ISO format UTC — override auto slot


@app.post("/schedule/add")
async def schedule_add(request: ScheduleAddRequest):
    """Add a Printify product to the publish schedule.
    If scheduled_publish_at is provided, use that exact time. Otherwise auto-calculate."""
    try:
        if request.scheduled_publish_at:
            result = await db.add_to_schedule(
                printify_product_id=request.printify_product_id,
                title=request.title,
                scheduled_publish_at=request.scheduled_publish_at,
            )
        else:
            result = await publish_scheduler.add_to_queue(
                printify_product_id=request.printify_product_id,
                title=request.title,
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schedule/queue")
async def schedule_queue(status: Optional[str] = None):
    """Get the publish queue. Optional ?status=pending|published|failed."""
    return await db.get_schedule_queue(status=status)


@app.post("/schedule/publish-now/{product_id}")
async def schedule_publish_now(product_id: str):
    """Immediately publish a product, bypassing the schedule."""
    try:
        result = await publish_scheduler.publish_now(product_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/schedule/{product_id}")
async def schedule_remove(product_id: str):
    """Remove a product from the publish queue."""
    removed = await db.remove_from_schedule(product_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Product not found in schedule")
    return {"removed": product_id}


@app.get("/schedule/stats")
async def schedule_stats():
    """Get scheduling statistics."""
    return await db.get_schedule_stats()


# === Schedule Settings ===


class ScheduleSettingsRequest(BaseModel):
    publish_times: List[str]  # e.g. ["10:00", "14:00", "18:00"]
    timezone: str = "US/Eastern"
    enabled: bool = True


@app.get("/schedule/settings")
async def get_schedule_settings():
    """Get current schedule configuration."""
    return await db.get_schedule_settings()


@app.put("/schedule/settings")
async def update_schedule_settings(request: ScheduleSettingsRequest):
    """Update publish schedule configuration. Changes take effect immediately."""
    from datetime import datetime as _dt

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
    )
    await publish_scheduler.reload_settings()
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
