# Strategy Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Strategy page where AI generates a content plan with Leonardo prompts, the user edits/approves, then executes end-to-end (generate images → create products → schedule publishing).

**Architecture:** New `/strategy` frontend page + `backend/routes/strategy.py` route module + two new DB tables (`strategy_plans`, `strategy_items`). AI plan generation uses Claude API via `listing_generator.py` pattern. Execution reuses existing Leonardo + create-full-product pipeline with background tasks.

**Tech Stack:** FastAPI, asyncpg, Next.js 14 (TypeScript), Tailwind CSS, Claude API (Haiku), Leonardo API

---

### Task 1: Database Schema

**Files:**
- Modify: `backend/database.py` — add tables to SCHEMA constant

**Step 1: Add strategy tables to SCHEMA**

Add after the existing tables in the `SCHEMA` constant (around line 150, before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS strategy_plans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_items (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES strategy_plans(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    description TEXT,
    style TEXT,
    preset TEXT,
    model_id TEXT NOT NULL DEFAULT 'phoenix',
    size_id TEXT NOT NULL DEFAULT 'poster_4_5',
    title_hint TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    generation_id TEXT,
    printify_product_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_strategy_items_plan ON strategy_items(plan_id);
```

**Step 2: Verify locally**

Run: `docker-compose up --build -d backend && sleep 3 && docker-compose logs --tail=5 backend`
Expected: "Application startup complete" with no errors.

**Step 3: Commit**

```
git add backend/database.py
git commit -m "feat(strategy): add strategy_plans and strategy_items tables"
```

---

### Task 2: Backend Route — CRUD Endpoints

**Files:**
- Create: `backend/routes/strategy.py`
- Modify: `backend/main.py` — register the router

**Step 1: Create the route file with CRUD endpoints**

Create `backend/routes/strategy.py`:

```python
import asyncio
import json
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import database as db

router = APIRouter(tags=["strategy"])


# --- Models ---

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


# --- Plan CRUD ---

@router.get("/strategy/plans")
async def list_plans():
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM strategy_items WHERE plan_id = p.id) as total_items,
                      (SELECT COUNT(*) FROM strategy_items WHERE plan_id = p.id AND status = 'product_created') as done_items
               FROM strategy_plans p ORDER BY p.created_at DESC"""
        )
    return [dict(r) for r in rows]


@router.post("/strategy/plans")
async def create_plan(request: CreatePlanRequest):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO strategy_plans (name) VALUES ($1) RETURNING *",
            request.name,
        )
    return dict(row)


@router.get("/strategy/plans/{plan_id}")
async def get_plan(plan_id: int):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow("SELECT * FROM strategy_plans WHERE id = $1", plan_id)
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
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM strategy_plans WHERE id = $1 RETURNING id", plan_id
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"deleted": plan_id}


# --- Item CRUD ---

@router.post("/strategy/items")
async def create_item(request: CreateItemRequest):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO strategy_items (plan_id, prompt, description, style, preset, model_id, size_id, title_hint, sort_order)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *""",
            request.plan_id, request.prompt, request.description,
            request.style, request.preset, request.model_id, request.size_id,
            request.title_hint, request.sort_order,
        )
    return dict(row)


@router.put("/strategy/items/{item_id}")
async def update_item(item_id: int, request: UpdateItemRequest):
    pool = await db.get_pool()
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [item_id] + list(updates.values())

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE strategy_items SET {set_clause} WHERE id = $1 RETURNING *",
            *values,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return dict(row)


@router.delete("/strategy/items/{item_id}")
async def delete_item(item_id: int):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM strategy_items WHERE id = $1 RETURNING id", item_id
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"deleted": item_id}
```

**Step 2: Register the router in main.py**

Add import and include_router in `backend/main.py`:

```python
from routes.strategy import router as strategy_router
# ... at the bottom with other include_router calls:
app.include_router(strategy_router)
```

**Step 3: Build and verify**

Run: `docker-compose up --build -d backend && sleep 3 && curl -s http://localhost:8001/strategy/plans | python3 -m json.tool`
Expected: `[]` (empty array)

**Step 4: Commit**

```
git add backend/routes/strategy.py backend/main.py
git commit -m "feat(strategy): add CRUD endpoints for plans and items"
```

---

### Task 3: Backend — AI Plan Generation

**Files:**
- Modify: `backend/routes/strategy.py` — add generate-plan endpoint

**Step 1: Add the AI generate-plan endpoint**

Add to `backend/routes/strategy.py` after the imports:

```python
import httpx
from config import STYLE_PRESETS, MODELS, DEFAULT_SIZE
from deps import listing_gen
```

Then add the endpoint:

```python
class GeneratePlanRequest(BaseModel):
    name: str = "AI Plan"
    count: int = 15


@router.post("/strategy/generate-plan")
async def generate_plan(request: GeneratePlanRequest):
    """AI analyzes existing data and generates a content plan with Leonardo prompts."""
    if not listing_gen.api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    pool = await db.get_pool()

    # Collect existing data
    async with pool.acquire() as conn:
        existing_products = await conn.fetch(
            "SELECT title, tags FROM products WHERE status != 'failed' ORDER BY created_at DESC LIMIT 100"
        )
        existing_generations = await conn.fetch(
            "SELECT DISTINCT style, preset, prompt FROM generations WHERE status = 'COMPLETE' ORDER BY created_at DESC LIMIT 200"
        )

    # Build context for Claude
    presets_summary = []
    for cat_key, cat in STYLE_PRESETS.items():
        for preset_key, preset in cat.get("presets", {}).items():
            presets_summary.append(f"- {cat_key}/{preset_key}: {preset['name']}")

    existing_summary = []
    for g in existing_generations:
        existing_summary.append(f"- [{g['style']}/{g['preset']}] {g['prompt'][:80]}")

    products_summary = []
    for p in existing_products:
        products_summary.append(f"- {p['title']}")

    system_prompt = """You are a poster shop content strategist. You analyze an existing catalog and suggest new posters to create.
You MUST respond with valid JSON only — an array of objects. No markdown, no commentary."""

    user_prompt = f"""Our poster shop has these style categories and presets:
{chr(10).join(presets_summary)}

We have already generated these images:
{chr(10).join(existing_summary[:80]) if existing_summary else "None yet."}

Our existing products:
{chr(10).join(products_summary[:50]) if products_summary else "None yet."}

Generate exactly {request.count} NEW poster ideas that complement our catalog. For each, provide:
- "prompt": A detailed Leonardo AI image generation prompt (50-100 words, describe visual style, colors, composition)
- "description": Brief rationale why this poster is worth creating (1-2 sentences)
- "style": One of our style categories ({', '.join(STYLE_PRESETS.keys())})
- "preset": A preset name (can be existing or new)
- "title_hint": A catchy Etsy product title (under 140 chars)

Focus on:
1. Gaps in our catalog (styles/themes we haven't covered)
2. Variations of successful existing designs
3. Unique combinations that stand out

Respond with a JSON array:
[{{"prompt": "...", "description": "...", "style": "...", "preset": "...", "title_hint": "..."}}]"""

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
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    items_data = json.loads(content, strict=False)

    # Save plan + items
    async with pool.acquire() as conn:
        plan = await conn.fetchrow(
            "INSERT INTO strategy_plans (name) VALUES ($1) RETURNING *",
            request.name,
        )
        plan_id = plan["id"]

        saved_items = []
        for idx, item in enumerate(items_data):
            row = await conn.fetchrow(
                """INSERT INTO strategy_items (plan_id, prompt, description, style, preset, title_hint, sort_order)
                   VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *""",
                plan_id, item["prompt"], item.get("description", ""),
                item.get("style", ""), item.get("preset", ""),
                item.get("title_hint", ""), idx,
            )
            saved_items.append(dict(row))

    result = dict(plan)
    result["items"] = saved_items
    return result
```

**Step 2: Build and verify**

Run: `docker-compose up --build -d backend && sleep 3 && docker-compose logs --tail=5 backend`
Expected: "Application startup complete"

**Step 3: Commit**

```
git add backend/routes/strategy.py
git commit -m "feat(strategy): add AI plan generation via Claude"
```

---

### Task 4: Backend — Plan Execution

**Files:**
- Modify: `backend/routes/strategy.py` — add execute endpoint

**Step 1: Add execution task store and background worker**

Add to `backend/routes/strategy.py`:

```python
from deps import listing_gen, printify, notifier, publish_scheduler, upscale_service

# In-memory execution status
_execution_tasks: dict[str, dict] = {}


async def _execute_plan_items(task_id: str, plan_id: int, items: list):
    """Background worker: generate images + create products for each item."""
    from leonardo import LeonardoAPI
    from deps import leonardo
    from routes.dpi import prepare_multidesign_images
    from pricing import get_all_prices
    from printify import create_variants_from_prices
    from description_utils import clean_description
    from listing_generator import EtsyListing
    import time

    task = _execution_tasks[task_id]
    pool = await db.get_pool()

    for idx, item in enumerate(items):
        item_id = item["id"]
        task["current_item"] = idx + 1
        task["current_title"] = item.get("title_hint", item["prompt"][:40])

        try:
            # --- Step A: Generate image ---
            task["step"] = f"Generating image {idx+1}/{len(items)}..."
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE strategy_items SET status = 'generating' WHERE id = $1",
                    item_id,
                )

            gen_result = await leonardo.generate(
                prompt=item["prompt"],
                model_id=item.get("model_id") or "phoenix",
                size_id=item.get("size_id") or "poster_4_5",
                num_images=1,
            )
            generation_id = gen_result["generation_id"]

            # Poll for completion
            for _ in range(60):
                await asyncio.sleep(5)
                status = await leonardo.get_generation_status(generation_id)
                if status["status"] == "COMPLETE":
                    break
            else:
                raise Exception("Generation timed out")

            images = status.get("images", [])
            if not images:
                raise Exception("No images generated")
            image_url = images[0]["url"]

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE strategy_items SET status = 'generated', generation_id = $2 WHERE id = $1",
                    item_id, generation_id,
                )

            # --- Step B: Create product ---
            task["step"] = f"Creating product {idx+1}/{len(items)}..."

            # Use existing create-full-product logic inline
            listing = EtsyListing(
                title=(item.get("title_hint") or item["prompt"][:80])[:140],
                tags=[],
                description="",
            )

            # Generate proper listing via AI
            try:
                listing = await listing_gen.generate_listing(
                    style=item.get("style", "abstract"),
                    preset=item.get("preset", "general"),
                    description=item["prompt"],
                )
                if item.get("title_hint"):
                    listing.title = item["title_hint"][:140]
            except Exception:
                pass  # Use basic listing if AI fails

            prices = get_all_prices("standard")
            filename_prefix = f"strategy_{plan_id}_{int(time.time())}"
            design_groups, enabled_sizes, dpi_analysis = await prepare_multidesign_images(
                image_url=image_url, filename_prefix=filename_prefix,
            )
            variants = create_variants_from_prices(prices, enabled_sizes=enabled_sizes)
            clean_desc = clean_description(listing.description, list(enabled_sizes))

            product = await printify.create_product_multidesign(
                title=listing.title,
                description=clean_desc,
                tags=listing.tags,
                design_groups=design_groups,
                variants=variants,
            )

            # Save to DB
            source_image = await db.get_image_by_url(image_url)
            source_image_id = source_image["id"] if source_image else None
            await db.save_product(
                printify_product_id=product.id,
                title=listing.title,
                description=clean_desc,
                tags=listing.tags,
                image_url=image_url,
                pricing_strategy="standard",
                enabled_sizes=sorted(enabled_sizes),
                status="draft",
                source_image_id=source_image_id,
            )

            # Schedule for publishing
            await publish_scheduler.add_to_queue(
                printify_product_id=product.id,
                title=listing.title,
                etsy_metadata={
                    "materials": ["Archival paper", "Ink"],
                    "who_made": "someone_else",
                    "when_made": "2020_2025",
                    "is_supply": False,
                },
            )

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE strategy_items SET status = 'product_created', printify_product_id = $2 WHERE id = $1",
                    item_id, product.id,
                )
            task["completed"] += 1

        except Exception as e:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE strategy_items SET status = 'planned' WHERE id = $1",
                    item_id,
                )
            task["errors"].append({"item_id": item_id, "error": str(e)})

    # Mark plan as completed
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE strategy_plans SET status = 'completed', updated_at = NOW() WHERE id = $1",
            plan_id,
        )
    task["status"] = "completed"
    task["step"] = "Done"


@router.post("/strategy/plans/{plan_id}/execute")
async def execute_plan(plan_id: int):
    """Execute all planned items in a plan. Returns task_id for polling."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow("SELECT * FROM strategy_plans WHERE id = $1", plan_id)
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

    task_id = str(uuid.uuid4())[:8]
    _execution_tasks[task_id] = {
        "status": "running",
        "step": "Starting...",
        "total": len(items),
        "completed": 0,
        "current_item": 0,
        "current_title": "",
        "errors": [],
    }
    asyncio.create_task(_execute_plan_items(task_id, plan_id, [dict(i) for i in items]))
    return {"task_id": task_id, "total_items": len(items)}


@router.get("/strategy/execute/status/{task_id}")
async def get_execution_status(task_id: str):
    """Poll execution progress."""
    task = _execution_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    response = dict(task)
    if task["status"] == "completed":
        _execution_tasks.pop(task_id, None)
    return response
```

**Step 2: Build and verify**

Run: `docker-compose up --build -d backend && sleep 3 && docker-compose logs --tail=5 backend`
Expected: "Application startup complete"

**Step 3: Commit**

```
git add backend/routes/strategy.py
git commit -m "feat(strategy): add plan execution with background task"
```

---

### Task 5: Frontend — API Functions

**Files:**
- Modify: `frontend/lib/api.ts` — add strategy API functions

**Step 1: Add types and API functions**

Add at the end of `frontend/lib/api.ts`:

```typescript
// === Strategy ===

export interface StrategyPlan {
  id: number;
  name: string;
  status: 'draft' | 'executing' | 'completed';
  total_items: number;
  done_items: number;
  created_at: string;
  updated_at: string;
}

export interface StrategyItem {
  id: number;
  plan_id: number;
  prompt: string;
  description: string;
  style: string;
  preset: string;
  model_id: string;
  size_id: string;
  title_hint: string;
  status: 'planned' | 'generating' | 'generated' | 'product_created' | 'skipped';
  generation_id: string | null;
  printify_product_id: string | null;
  sort_order: number;
  created_at: string;
}

export interface StrategyPlanDetail extends StrategyPlan {
  items: StrategyItem[];
}

export async function getStrategyPlans(): Promise<StrategyPlan[]> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans`);
  if (!resp.ok) throw new Error('Failed to fetch plans');
  return resp.json();
}

export async function getStrategyPlan(planId: number): Promise<StrategyPlanDetail> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans/${planId}`);
  if (!resp.ok) throw new Error('Failed to fetch plan');
  return resp.json();
}

export async function createStrategyPlan(name: string): Promise<StrategyPlan> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!resp.ok) throw new Error('Failed to create plan');
  return resp.json();
}

export async function deleteStrategyPlan(planId: number): Promise<void> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans/${planId}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error('Failed to delete plan');
}

export async function generateStrategyPlan(
  name: string,
  count: number = 15,
  onStep?: (step: string) => void,
): Promise<StrategyPlanDetail> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/generate-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, count }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'AI generation failed' }));
    throw new Error(err.detail || 'AI generation failed');
  }
  return resp.json();
}

export async function updateStrategyItem(
  itemId: number,
  data: Partial<Pick<StrategyItem, 'prompt' | 'description' | 'style' | 'preset' | 'model_id' | 'size_id' | 'title_hint' | 'sort_order' | 'status'>>,
): Promise<StrategyItem> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/items/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error('Failed to update item');
  return resp.json();
}

export async function deleteStrategyItem(itemId: number): Promise<void> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/items/${itemId}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error('Failed to delete item');
}

export async function executeStrategyPlan(planId: number): Promise<{ task_id: string; total_items: number }> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans/${planId}/execute`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Execution failed' }));
    throw new Error(err.detail || 'Execution failed');
  }
  return resp.json();
}

export async function getExecutionStatus(taskId: string): Promise<{
  status: string;
  step: string;
  total: number;
  completed: number;
  current_item: number;
  current_title: string;
  errors: Array<{ item_id: number; error: string }>;
}> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/execute/status/${taskId}`);
  if (!resp.ok) throw new Error('Failed to check status');
  return resp.json();
}
```

**Step 2: Commit**

```
git add frontend/lib/api.ts
git commit -m "feat(strategy): add frontend API functions"
```

---

### Task 6: Frontend — Strategy Page

**Files:**
- Create: `frontend/app/strategy/page.tsx`
- Modify: `frontend/components/Header.tsx` — add nav link

**Step 1: Add nav link**

In `frontend/components/Header.tsx`, add `{ href: '/strategy', label: 'Strategy' }` to the 'Create' nav group, after the 'Presets' item.

**Step 2: Create the Strategy page**

Create `frontend/app/strategy/page.tsx` with:
- Plan list view (default) — shows all plans with name, status, item count
- Plan detail view (when a plan is selected) — shows cards for each item
- AI Generate button — calls `generateStrategyPlan()`
- Execute button — calls `executeStrategyPlan()` + polls status
- Edit/Delete on each card
- Coverage metric at bottom

This is a large file (~400 lines). Key sections:

1. **State**: `plans`, `selectedPlan`, `isGenerating`, `isExecuting`, `executionStatus`
2. **Plan list**: Cards showing plan name, progress bar, status badge
3. **Plan detail**: Grid of item cards with color-coded status borders
4. **Item card**: Style badge, title_hint, prompt preview (truncated), status indicator, action buttons
5. **AI dialog**: Input for plan name + count, "Generate" button with loading spinner
6. **Execute mode**: Progress bar, current item indicator, error list

The implementation should follow the same Tailwind dark theme as other pages (bg-dark-bg, bg-dark-card, border-dark-border, text-gray-* palette, accent color for primary actions).

**Step 3: Build and test locally**

Run: `docker-compose up --build -d frontend && sleep 5`
Then open `http://localhost:3001/strategy` in browser.

**Step 4: Commit**

```
git add frontend/app/strategy/page.tsx frontend/components/Header.tsx
git commit -m "feat(strategy): add Strategy page with AI plan generation and execution"
```

---

### Task 7: Coverage Metric

**Files:**
- Modify: `backend/routes/strategy.py` — add coverage endpoint

**Step 1: Add coverage endpoint**

```python
@router.get("/strategy/coverage")
async def get_coverage():
    """How many style×preset combinations have existing products."""
    from config import STYLE_PRESETS

    total_combos = sum(
        len(cat.get("presets", {})) for cat in STYLE_PRESETS.values()
    )

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        covered = await conn.fetchval(
            """SELECT COUNT(DISTINCT style || '/' || preset)
               FROM generations WHERE status = 'COMPLETE' AND style IS NOT NULL AND preset IS NOT NULL"""
        )
        products = await conn.fetchval(
            "SELECT COUNT(*) FROM products WHERE status != 'failed'"
        )

    return {
        "total_combinations": total_combos,
        "covered": covered or 0,
        "products": products or 0,
        "coverage_percent": round((covered or 0) / max(total_combos, 1) * 100, 1),
    }
```

**Step 2: Commit**

```
git add backend/routes/strategy.py
git commit -m "feat(strategy): add coverage metric endpoint"
```

---

### Task 8: Integration Test

**Step 1: Manual test flow**

1. Open `http://localhost:3001/strategy`
2. Click "AI Generate Plan" → enter name "Test Plan" → count 5
3. Verify 5 cards appear with prompts, styles, descriptions
4. Edit one card's prompt
5. Delete one card
6. Click "Execute All" (requires Leonardo API key in .env)
7. Watch progress update in real-time

**Step 2: Verify API directly**

```bash
# Create plan via AI
curl -s -X POST http://localhost:8001/strategy/generate-plan \
  -H 'Content-Type: application/json' \
  -d '{"name": "Test", "count": 3}' | python3 -m json.tool

# Check coverage
curl -s http://localhost:8001/strategy/coverage | python3 -m json.tool
```

**Step 3: Final commit with all changes**

```
git add -A
git commit -m "feat(strategy): complete strategy page with AI planning and execution"
```
