import asyncio
import json
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from config import STYLE_PRESETS, MODELS, SIZES
from deps import listing_gen, printify, publish_scheduler, leonardo
from pricing import get_all_prices
from printify import create_variants_from_prices
from routes.dpi import prepare_multidesign_images
from description_utils import clean_description
from sizes import COMPOSITION_SUFFIX
import database as db

router = APIRouter(tags=["strategy"])


# ── In-memory execution task store ──────────────────────────────────
_execution_tasks: dict[str, dict] = {}


# ── Pydantic models ────────────────────────────────────────────────

class CreatePlanRequest(BaseModel):
    name: str


class CreateItemRequest(BaseModel):
    plan_id: int
    prompt: str
    description: Optional[str] = None
    style: Optional[str] = None
    preset: Optional[str] = None
    model_id: str = "phoenix"
    size_id: str = "poster_4_5"
    title_hint: Optional[str] = None
    sort_order: int = 0


class UpdateItemRequest(BaseModel):
    prompt: Optional[str] = None
    description: Optional[str] = None
    style: Optional[str] = None
    preset: Optional[str] = None
    model_id: Optional[str] = None
    size_id: Optional[str] = None
    title_hint: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None


class GeneratePlanRequest(BaseModel):
    name: str = "AI Plan"
    count: int = 15


# ── CRUD Endpoints ──────────────────────────────────────────────────

@router.get("/strategy/plans")
async def list_plans():
    """List all strategy plans with item counts."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sp.*,
                   (SELECT COUNT(*) FROM strategy_items si WHERE si.plan_id = sp.id) AS total_items,
                   (SELECT COUNT(*) FROM strategy_items si WHERE si.plan_id = sp.id AND si.status = 'product_created') AS done_items
            FROM strategy_plans sp
            ORDER BY sp.created_at DESC
        """)
    return [dict(r) for r in rows]


@router.post("/strategy/plans")
async def create_plan(request: CreatePlanRequest):
    """Create a new empty strategy plan."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO strategy_plans (name) VALUES ($1) RETURNING *",
            request.name,
        )
    return dict(row)


@router.get("/strategy/plans/{plan_id}")
async def get_plan(plan_id: int):
    """Get a plan with all its items ordered by sort_order, id."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow(
            "SELECT * FROM strategy_plans WHERE id = $1", plan_id
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        items = await conn.fetch(
            "SELECT * FROM strategy_items WHERE plan_id = $1 ORDER BY sort_order, id",
            plan_id,
        )
    result = dict(plan)
    result["items"] = [dict(i) for i in items]
    return result


@router.delete("/strategy/plans/{plan_id}")
async def delete_plan(plan_id: int):
    """Delete a plan (CASCADE deletes items)."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM strategy_plans WHERE id = $1", plan_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"ok": True}


@router.post("/strategy/items")
async def create_item(request: CreateItemRequest):
    """Add an item to a plan."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        # Verify plan exists
        plan = await conn.fetchval(
            "SELECT id FROM strategy_plans WHERE id = $1", request.plan_id
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        row = await conn.fetchrow(
            """INSERT INTO strategy_items
               (plan_id, prompt, description, style, preset, model_id, size_id, title_hint, sort_order)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING *""",
            request.plan_id, request.prompt, request.description,
            request.style, request.preset, request.model_id,
            request.size_id, request.title_hint, request.sort_order,
        )
    return dict(row)


@router.put("/strategy/items/{item_id}")
async def update_item(item_id: int, request: UpdateItemRequest):
    """Update item fields dynamically (only non-None fields)."""
    fields = request.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_parts = []
    values = []
    idx = 2  # $1 is item_id
    for key, val in fields.items():
        set_parts.append(f"{key} = ${idx}")
        values.append(val)
        idx += 1

    sql = f"UPDATE strategy_items SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, item_id, *values)
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return dict(row)


@router.delete("/strategy/items/{item_id}")
async def delete_item(item_id: int):
    """Delete a strategy item."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM strategy_items WHERE id = $1", item_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


# ── AI Plan Generation ──────────────────────────────────────────────

@router.post("/strategy/generate-plan")
async def generate_plan(request: GeneratePlanRequest):
    """Use Claude to generate a content plan based on existing catalog."""
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        # Collect existing products for context
        products = await conn.fetch(
            "SELECT title, tags FROM products WHERE status != 'failed' ORDER BY created_at DESC LIMIT 100"
        )
        # Collect recent generations for context
        generations = await conn.fetch(
            "SELECT style, preset, prompt FROM generations WHERE status = 'COMPLETE' AND style IS NOT NULL ORDER BY created_at DESC LIMIT 50"
        )

    # Build context
    style_categories = []
    for cat_key, cat_data in STYLE_PRESETS.items():
        preset_names = list(cat_data["presets"].keys())
        style_categories.append(f"- {cat_key} ({cat_data['name']}): {', '.join(preset_names)}")
    styles_text = "\n".join(style_categories)

    existing_titles = [r["title"] for r in products][:50]
    titles_text = "\n".join(f"- {t}" for t in existing_titles) if existing_titles else "No products yet."

    recent_gens = []
    for g in generations[:30]:
        recent_gens.append(f"- style={g['style']}, preset={g['preset']}, prompt={g['prompt'][:80]}")
    gens_text = "\n".join(recent_gens) if recent_gens else "No recent generations."

    system_prompt = (
        "You are a poster shop content strategist. You analyze an existing catalog "
        "and suggest new posters to create. You MUST respond with valid JSON only — "
        "an array of objects. No markdown, no commentary."
    )

    user_prompt = f"""Analyze my poster shop catalog and suggest {request.count} new poster designs.

AVAILABLE STYLE CATEGORIES AND PRESETS:
{styles_text}

RECENT GENERATIONS (avoid duplicates):
{gens_text}

EXISTING PRODUCTS (titles):
{titles_text}

Generate exactly {request.count} items. Each item must have:
- "prompt": A detailed image generation prompt (50-100 words) suitable for Leonardo AI. Describe the visual scene, composition, colors, and mood.
- "description": 1-2 sentences explaining the rationale — why this poster would sell well.
- "style": One of the style category keys above (e.g. "japanese", "botanical", "abstract", "celestial", "landscape").
- "preset": One of the preset keys from within that style category (e.g. "mountain", "leaves", "geometric").
- "title_hint": A suggested Etsy listing title (under 140 characters).

IMPORTANT:
- Diversify across different style categories.
- Avoid duplicating existing products or recent generations.
- Focus on trending aesthetics and buyer demand.
- Each prompt should be specific enough for high-quality image generation.

Respond with a JSON array only."""

    payload = {
        "model": listing_gen.MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            listing_gen.BASE_URL,
            headers=listing_gen.headers,
            json=payload,
            timeout=90.0,
        )
        listing_gen._check_response(response)
        data = response.json()

    content = data["content"][0]["text"].strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    items_data = json.loads(content, strict=False)

    if not isinstance(items_data, list):
        raise HTTPException(status_code=500, detail="AI returned invalid format (expected array)")

    # Create plan and items in DB
    async with pool.acquire() as conn:
        plan_row = await conn.fetchrow(
            "INSERT INTO strategy_plans (name) VALUES ($1) RETURNING *",
            request.name,
        )
        plan_id = plan_row["id"]

        saved_items = []
        for idx, item in enumerate(items_data):
            row = await conn.fetchrow(
                """INSERT INTO strategy_items
                   (plan_id, prompt, description, style, preset, title_hint, sort_order)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING *""",
                plan_id,
                item.get("prompt", ""),
                item.get("description", ""),
                item.get("style", ""),
                item.get("preset", ""),
                item.get("title_hint", ""),
                idx,
            )
            saved_items.append(dict(row))

    result = dict(plan_row)
    result["items"] = saved_items
    return result


# ── Plan Execution ──────────────────────────────────────────────────

@router.post("/strategy/plans/{plan_id}/execute")
async def execute_plan(plan_id: int):
    """Start executing a strategy plan as a background task."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow(
            "SELECT * FROM strategy_plans WHERE id = $1", plan_id
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if plan["status"] == "executing":
            raise HTTPException(status_code=400, detail="Plan is already executing")

        items = await conn.fetch(
            "SELECT * FROM strategy_items WHERE plan_id = $1 AND status = 'planned' ORDER BY sort_order, id",
            plan_id,
        )
        if not items:
            raise HTTPException(status_code=400, detail="No planned items to execute")

        await conn.execute(
            "UPDATE strategy_plans SET status = 'executing', updated_at = NOW() WHERE id = $1",
            plan_id,
        )

    task_id = str(uuid.uuid4())
    items_list = [dict(i) for i in items]

    _execution_tasks[task_id] = {
        "status": "running",
        "step": 0,
        "total": len(items_list),
        "completed": 0,
        "current_item": None,
        "current_title": None,
        "errors": [],
    }

    asyncio.create_task(_execute_plan_items(task_id, plan_id, items_list))

    return {
        "task_id": task_id,
        "total_items": len(items_list),
    }


@router.get("/strategy/execute/status/{task_id}")
async def get_execution_status(task_id: str):
    """Poll execution progress."""
    task = _execution_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def _execute_plan_items(task_id: str, plan_id: int, items: list):
    """Background worker: execute each plan item sequentially."""
    task = _execution_tasks[task_id]

    for idx, item in enumerate(items):
        item_id = item["id"]
        task["step"] = idx + 1
        task["current_item"] = item_id
        task["current_title"] = item.get("title_hint", f"Item {item_id}")

        try:
            await _execute_single_plan_item(item)
            task["completed"] += 1
        except Exception as e:
            await _reset_item_on_error(item_id)
            task["errors"].append({
                "item_id": item_id,
                "error": str(e),
            })

    await _finalize_plan(plan_id)
    task["status"] = "completed"
    task["current_item"] = None
    task["current_title"] = None


async def _execute_single_plan_item(item: dict):
    """Execute a single plan item: generate image, create listing, build product."""
    item_id = item["id"]
    pool = await db.get_pool()

    # Mark item as generating
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE strategy_items SET status = 'generating' WHERE id = $1",
            item_id,
        )

    # Generate image and poll for completion
    generation_id, completed = await _generate_image(item)

    # Update item with generation result
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE strategy_items SET status = 'generated', generation_id = $1 WHERE id = $2",
            generation_id, item_id,
        )

    image_url = completed["images"][0]["url"]
    source_image = await db.get_image_by_url(image_url)
    source_image_id = source_image["id"] if source_image else None

    # Create listing, product, and schedule for publishing
    product = await _create_product(item, image_url, source_image_id)

    # Mark item as complete
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE strategy_items SET status = 'product_created', printify_product_id = $1 WHERE id = $2",
            product.id, item_id,
        )


async def _generate_image(item: dict) -> tuple:
    """Generate an image via Leonardo, poll for completion, and save to DB.

    Returns (generation_id, completed_result).
    """
    prompt = item["prompt"]
    model_id = item.get("model_id", "phoenix")
    size_id = item.get("size_id", "poster_4_5")

    model_info = MODELS.get(model_id, MODELS["phoenix"])
    size_info = SIZES.get(size_id, SIZES["poster_4_5"])

    gen_prompt = prompt + COMPOSITION_SUFFIX
    gen_width = size_info["width"]
    gen_height = size_info["height"]
    if gen_width > 1536 or gen_height > 1536:
        scale = 1536 / max(gen_width, gen_height)
        gen_width = int(gen_width * scale) // 8 * 8
        gen_height = int(gen_height * scale) // 8 * 8

    gen_result = await leonardo.create_generation(
        prompt=gen_prompt,
        model_id=model_info["id"],
        num_images=1,
        width=gen_width,
        height=gen_height,
    )
    generation_id = gen_result["generation_id"]

    await db.save_generation(
        generation_id=generation_id,
        prompt=prompt,
        negative_prompt="",
        model_id=model_info["id"],
        model_name=model_info["name"],
        style=item.get("style", ""),
        preset=item.get("preset", ""),
        width=size_info["width"],
        height=size_info["height"],
        num_images=1,
    )

    # Poll for completion (every 5s, up to 60 times = 5 min)
    completed = None
    for _ in range(60):
        result = await leonardo.get_generation(generation_id)
        if result["status"] == "COMPLETE":
            completed = result
            break
        elif result["status"] == "FAILED":
            raise Exception("Image generation failed")
        await asyncio.sleep(5)

    if not completed or not completed.get("images"):
        raise Exception("Image generation timed out or returned no images")

    await db.update_generation_status(
        generation_id, "COMPLETE", completed.get("api_credit_cost", 0)
    )
    await db.save_generated_images(generation_id, completed["images"])

    return generation_id, completed


async def _create_product(item: dict, image_url: str, source_image_id: int | None):
    """Generate listing, build Printify product, save to DB, and schedule publishing.

    Returns the Printify product object.
    """
    import time as time_mod

    item_id = item["id"]
    prompt = item["prompt"]
    style = item.get("style", "")
    preset = item.get("preset", "")
    title_hint = item.get("title_hint", "")

    # Generate listing via Claude
    listing = await listing_gen.generate_listing(
        style=style,
        preset=preset,
        description=prompt,
    )

    title = title_hint if title_hint else listing.title
    tags = listing.tags

    # Prepare multi-design images and variants
    prices = get_all_prices("standard")
    filename_prefix = f"strategy_{item_id}_{int(time_mod.time())}"
    design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
        image_url=image_url,
        filename_prefix=filename_prefix,
    )

    clean_desc = clean_description(listing.description, list(enabled_sizes))
    variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)

    # Create product via Printify
    product = await printify.create_product_multidesign(
        title=title,
        description=clean_desc,
        tags=tags,
        design_groups=design_groups,
        variants=variants,
    )

    # Save to DB
    etsy_metadata = {
        "materials": ["Archival paper", "Ink"],
        "who_made": "someone_else",
        "when_made": "2020_2025",
        "is_supply": False,
    }

    saved_product = await db.save_product(
        printify_product_id=product.id,
        title=title,
        description=clean_desc,
        tags=tags,
        image_url=image_url,
        pricing_strategy="standard",
        enabled_sizes=sorted(enabled_sizes),
        status="scheduled",
        etsy_metadata=etsy_metadata,
        source_image_id=source_image_id,
    )

    if source_image_id:
        await db.link_image_to_product(source_image_id, saved_product["id"])

    # Schedule for publishing
    await publish_scheduler.add_to_queue(
        printify_product_id=product.id,
        title=title,
        etsy_metadata=etsy_metadata,
    )

    return product


async def _reset_item_on_error(item_id: int):
    """Reset a strategy item back to 'planned' status after an error."""
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE strategy_items SET status = 'planned' WHERE id = $1",
                item_id,
            )
    except Exception:
        pass


async def _finalize_plan(plan_id: int):
    """Mark a strategy plan as completed."""
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE strategy_plans SET status = 'completed', updated_at = NOW() WHERE id = $1",
                plan_id,
            )
    except Exception:
        pass


# ── Coverage Metric ─────────────────────────────────────────────────

@router.get("/strategy/coverage")
async def get_coverage():
    """Get style x preset coverage metrics."""
    # Count total possible combinations from STYLE_PRESETS
    total_combinations = 0
    for cat_data in STYLE_PRESETS.values():
        total_combinations += len(cat_data["presets"])

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        covered = await conn.fetchval("""
            SELECT COUNT(DISTINCT style || '/' || preset)
            FROM generations
            WHERE status = 'COMPLETE'
              AND style IS NOT NULL
              AND preset IS NOT NULL
        """)
        products_count = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE status != 'failed'"
        )

    coverage_percent = round((covered / total_combinations) * 100, 1) if total_combinations > 0 else 0

    return {
        "total_combinations": total_combinations,
        "covered": covered,
        "products": products_count,
        "coverage_percent": coverage_percent,
    }
