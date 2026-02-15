# Color Grading Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add post-compose color grading to mockup images, stored per-pack, applied during compose and approve flows.

**Architecture:** Color grade presets defined in `backend/config.py`. PIL-based processing function in `backend/routes/mockups.py` using `ImageEnhance` for brightness/contrast/saturation and pixel blend for warmth tint. Grade stored as `color_grade` column on `mockup_packs` table. Frontend adds grade selector to pack create/edit form and optional grade dropdown in compose preview.

**Tech Stack:** Python/PIL (ImageEnhance), PostgreSQL, FastAPI, Next.js 14

---

### Task 1: Add color grade presets to config

**Files:**
- Modify: `backend/config.py:297` (append after MOCKUP_STYLES)

**Step 1: Add presets dict**

Add at end of `backend/config.py`:

```python
# Color grade presets for post-compose processing
COLOR_GRADE_PRESETS = {
    "none": {
        "name": "None",
        "warmth": 0,
        "brightness": 1.0,
        "saturation": 1.0,
        "contrast": 1.0,
    },
    "warm_home": {
        "name": "Warm Home",
        "warmth": 30,
        "brightness": 1.02,
        "saturation": 0.92,
        "contrast": 1.03,
    },
    "moody_dark": {
        "name": "Moody Dark",
        "warmth": 15,
        "brightness": 0.95,
        "saturation": 0.85,
        "contrast": 1.08,
    },
    "clean_bright": {
        "name": "Clean Bright",
        "warmth": 10,
        "brightness": 1.05,
        "saturation": 0.95,
        "contrast": 1.0,
    },
    "golden_hour": {
        "name": "Golden Hour",
        "warmth": 45,
        "brightness": 1.05,
        "saturation": 0.9,
        "contrast": 1.02,
    },
}
```

**Step 2: Verify import works**

```bash
docker-compose exec backend python -c "from config import COLOR_GRADE_PRESETS; print(list(COLOR_GRADE_PRESETS.keys()))"
```

Expected: `['none', 'warm_home', 'moody_dark', 'clean_bright', 'golden_hour']`

---

### Task 2: Add PIL color grade function

**Files:**
- Modify: `backend/routes/mockups.py:334` (insert before `_compose_all_templates`)

**Step 1: Add `apply_color_grade` function**

Insert before line 334 (`async def _compose_all_templates`):

```python
from PIL import ImageEnhance
from config import COLOR_GRADE_PRESETS


def apply_color_grade(img: Image.Image, preset_name: str) -> Image.Image:
    """Apply color grade preset to a PIL Image. Returns graded image."""
    preset = COLOR_GRADE_PRESETS.get(preset_name)
    if not preset or preset_name == "none":
        return img

    result = img.copy()

    # Brightness
    if preset["brightness"] != 1.0:
        result = ImageEnhance.Brightness(result).enhance(preset["brightness"])

    # Saturation
    if preset["saturation"] != 1.0:
        result = ImageEnhance.Color(result).enhance(preset["saturation"])

    # Contrast
    if preset["contrast"] != 1.0:
        result = ImageEnhance.Contrast(result).enhance(preset["contrast"])

    # Warmth: blend with warm tint overlay
    warmth = preset.get("warmth", 0)
    if warmth > 0:
        # Create warm tint: reduce blue, slightly reduce green
        import numpy as np
        arr = np.array(result, dtype=np.float32)
        # Warm shift: boost red slightly, reduce blue
        factor = warmth / 100.0  # 0.0 - 1.0
        arr[:, :, 0] = np.clip(arr[:, :, 0] * (1 + factor * 0.05), 0, 255)  # R: slight boost
        arr[:, :, 2] = np.clip(arr[:, :, 2] * (1 - factor * 0.15), 0, 255)  # B: reduce
        result = Image.fromarray(arr.astype(np.uint8))

    return result
```

Note: `numpy` is already in requirements.txt. `ImageEnhance` is part of Pillow, already installed.

**Step 2: Verify the function loads**

```bash
docker-compose exec backend python -c "
from PIL import Image, ImageEnhance
import io
img = Image.new('RGB', (100, 100), (128, 128, 128))
from routes.mockups import apply_color_grade
result = apply_color_grade(img, 'warm_home')
print(f'Input: {img.size}, Output: {result.size}, Mode: {result.mode}')
"
```

Expected: `Input: (100, 100), Output: (100, 100), Mode: RGB`

---

### Task 3: Integrate color grade into compose pipeline

**Files:**
- Modify: `backend/routes/mockups.py:334-405` (`_compose_all_templates`)

**Step 1: Add `color_grade` parameter to `_compose_all_templates`**

Change the function signature (line 334):

```python
async def _compose_all_templates(
    poster_url: str,
    templates: List[dict],
    fill_mode: str = "fill",
    color_grade: str = "none",
) -> List[Tuple[int, bytes]]:
```

**Step 2: Apply color grade after compose, before PNG encoding**

Replace lines 400-403 (the `buf = io.BytesIO()` block):

```python
        result_rgb = result.convert("RGB")

        # Apply color grade as final step
        if color_grade and color_grade != "none":
            result_rgb = apply_color_grade(result_rgb, color_grade)

        buf = io.BytesIO()
        result_rgb.save(buf, format="PNG", quality=95)
        buf.seek(0)
        results.append((template["id"], buf.read()))
```

---

### Task 4: Add `color_grade` column to mockup_packs

**Files:**
- Modify: `backend/database.py` (init_db migrations section + DB helpers)

**Step 1: Add migration in `init_db`**

After the existing `ALTER TABLE image_mockups ADD COLUMN pack_id` migration, add:

```python
        # color_grade on mockup_packs
        try:
            await conn.execute(
                "ALTER TABLE mockup_packs ADD COLUMN color_grade TEXT DEFAULT 'none'"
            )
        except asyncpg.exceptions.DuplicateColumnError:
            pass
```

**Step 2: Update `create_mockup_pack` to accept color_grade**

```python
async def create_mockup_pack(name: str, color_grade: str = "none") -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO mockup_packs (name, color_grade) VALUES ($1, $2) RETURNING *",
            name, color_grade,
        )
        return dict(row)
```

**Step 3: Update `update_mockup_pack` to accept color_grade**

```python
async def update_mockup_pack(pack_id: int, name: str, color_grade: str = "none") -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE mockup_packs SET name = $1, color_grade = $2 WHERE id = $3 RETURNING *",
            name, color_grade, pack_id,
        )
        return dict(row) if row else None
```

---

### Task 5: Wire color grade through API endpoints

**Files:**
- Modify: `backend/routes/mockups.py` (request models + endpoints)

**Step 1: Add `color_grade` to request models**

`CreatePackRequest` (line 678):
```python
class CreatePackRequest(BaseModel):
    name: str
    template_ids: List[int] = []
    color_grade: str = "none"
```

`UpdatePackRequest` (line 683):
```python
class UpdatePackRequest(BaseModel):
    name: str
    template_ids: List[int]
    color_grade: str = "none"
```

`ComposeAllRequest` (line 647):
```python
class ComposeAllRequest(BaseModel):
    poster_url: str
    fill_mode: str = "fill"
    color_grade: str = "none"
```

**Step 2: Pass `color_grade` in pack CRUD endpoints**

In `create_pack` endpoint: pass `request.color_grade` to `db.create_mockup_pack(request.name, request.color_grade)`.

In `update_pack` endpoint: pass `request.color_grade` to `db.update_mockup_pack(pack_id, request.name, request.color_grade)`.

**Step 3: Pass `color_grade` in compose endpoints**

In `compose_all_mockups` (line 663): pass `color_grade=request.color_grade` to `_compose_all_templates()`.

In `compose_by_pack` (line 772): read pack's color_grade from DB and pass it:
```python
pack = await db.get_mockup_pack(request.pack_id)
color_grade = pack.get("color_grade", "none") if pack else "none"
# ... then ...
results = await _compose_all_templates(request.poster_url, templates, request.fill_mode, color_grade)
```

In `approve_poster` (line 847): read pack's color_grade when pack_id is set:
```python
color_grade = pack.get("color_grade", "none") if pack_id and pack else "none"
composed = await _compose_all_templates(image["url"], templates_to_compose, "fill", color_grade)
```

**Step 4: Add `/mockups/color-grades` endpoint for frontend**

```python
@router.get("/mockups/color-grades")
async def list_color_grades():
    """List available color grade presets."""
    from config import COLOR_GRADE_PRESETS
    grades = []
    for key, preset in COLOR_GRADE_PRESETS.items():
        grades.append({"id": key, "name": preset["name"]})
    return {"grades": grades}
```

---

### Task 6: Frontend API functions

**Files:**
- Modify: `frontend/lib/api.ts:2114-2170` (MockupPack interface + API functions)

**Step 1: Add `color_grade` to MockupPack interface**

```typescript
export interface MockupPack {
  id: number;
  name: string;
  template_count: number;
  color_grade: string;
  templates?: MockupTemplate[];
  created_at: string;
}
```

**Step 2: Update `createMockupPack` signature**

```typescript
export async function createMockupPack(name: string, templateIds: number[] = [], colorGrade: string = 'none'): Promise<MockupPack> {
  // ... body: JSON.stringify({ name, template_ids: templateIds, color_grade: colorGrade })
```

**Step 3: Update `updateMockupPack` signature**

```typescript
export async function updateMockupPack(packId: number, name: string, templateIds: number[], colorGrade: string = 'none'): Promise<MockupPack> {
  // ... body: JSON.stringify({ name, template_ids: templateIds, color_grade: colorGrade })
```

**Step 4: Add `getColorGrades` function**

```typescript
export async function getColorGrades(): Promise<{ grades: { id: string; name: string }[] }> {
  const response = await fetch(`${getApiUrl()}/mockups/color-grades`);
  if (!response.ok) throw new Error('Failed to fetch color grades');
  return response.json();
}
```

---

### Task 7: Frontend — Pack form color grade selector

**Files:**
- Modify: `frontend/app/mockups/generate/page.tsx` (Packs tab)

**Step 1: Add state for color grades and pack's selected grade**

After existing pack state variables (line 115):
```typescript
const [colorGrades, setColorGrades] = useState<{ id: string; name: string }[]>([]);
const [packColorGrade, setPackColorGrade] = useState('none');
```

**Step 2: Load color grades on mount**

In the existing `useEffect` (line 103), add:
```typescript
getColorGrades().then((data) => setColorGrades(data.grades)).catch(() => {});
```

**Step 3: Add color grade dropdown to pack create/edit form**

Between the template picker and the save button (around line 1505), add:
```tsx
{/* Color Grade */}
<div>
  <label className="text-xs text-gray-500 mb-1 block">Color Grade</label>
  <div className="flex gap-2 flex-wrap">
    {colorGrades.map((g) => (
      <button
        key={g.id}
        onClick={() => setPackColorGrade(g.id)}
        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
          packColorGrade === g.id
            ? 'bg-accent text-dark-bg'
            : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200'
        }`}
      >
        {g.name}
      </button>
    ))}
  </div>
</div>
```

**Step 4: Wire color grade into pack save/edit**

In `handleSavePack`: pass `packColorGrade` to `createMockupPack(packName.trim(), ids, packColorGrade)` and `updateMockupPack(editingPack.id, packName.trim(), ids, packColorGrade)`.

In `startEditPack`: set `setPackColorGrade(data.color_grade || 'none')`.

Reset in cancel/save: `setPackColorGrade('none')`.

**Step 5: Show color grade on pack cards**

In the pack list, after template count badge, add:
```tsx
{pack.color_grade && pack.color_grade !== 'none' && (
  <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-400">
    {colorGrades.find(g => g.id === pack.color_grade)?.name || pack.color_grade}
  </span>
)}
```

---

### Task 8: Build, verify, test end-to-end

**Step 1:** `docker-compose up --build -d`

**Step 2:** Verify DB migration: `docker-compose exec db psql -U poster -d poster_generator -c "\d mockup_packs"`
Expected: `color_grade` column present with default `'none'`

**Step 3:** Test color grades endpoint: `curl http://localhost:8001/mockups/color-grades`
Expected: JSON with 5 presets

**Step 4:** Test pack creation with grade: `curl -X POST http://localhost:8001/mockups/packs -H "Content-Type: application/json" -d '{"name":"Test","template_ids":[],"color_grade":"warm_home"}'`
Expected: pack with `color_grade: "warm_home"`

**Step 5:** Verify pages load:
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/mockups/generate` → 200
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/mockups/workflow` → 200

**Step 6:** Clean up test pack: `curl -X DELETE http://localhost:8001/mockups/packs/<id>`
