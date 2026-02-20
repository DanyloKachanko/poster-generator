# Strategy Page — Content Planning & Execution

## Overview

A hybrid content planner where AI analyzes existing data (generations, products, presets) and proposes a generation plan. The user edits/approves the plan, then executes it end-to-end: image generation → product creation → publish queue.

## Data Model

### `strategy_plans`

| Column     | Type      | Description                          |
|------------|-----------|--------------------------------------|
| id         | SERIAL PK |                                      |
| name       | TEXT      | "February Collection", "Cat Series"  |
| status     | TEXT      | draft / executing / completed        |
| created_at | TIMESTAMP |                                      |
| updated_at | TIMESTAMP |                                      |

### `strategy_items`

| Column              | Type      | Description                                   |
|---------------------|-----------|-----------------------------------------------|
| id                  | SERIAL PK |                                               |
| plan_id             | FK → plans| Parent plan                                   |
| prompt              | TEXT      | Full Leonardo prompt                          |
| description         | TEXT      | AI rationale — why this poster                |
| style               | TEXT      | japanese, botanical, abstract, etc.           |
| preset              | TEXT      | cherry, fern, geometric, etc.                 |
| model_id            | TEXT      | phoenix_1_0, kino_xl, etc.                    |
| size_id             | TEXT      | poster_4_5 (default)                          |
| title_hint          | TEXT      | Suggested product title                       |
| status              | TEXT      | planned / generating / generated / product_created / skipped |
| generation_id       | TEXT      | Filled after Leonardo generation              |
| printify_product_id | TEXT      | Filled after product creation                 |
| sort_order          | INTEGER   | Display/execution order                       |
| created_at          | TIMESTAMP |                                               |

## API Endpoints

### Plan Management
- `GET /strategy/plans` — list all plans
- `POST /strategy/plans` — create empty plan
- `GET /strategy/plans/{id}` — plan with all items
- `DELETE /strategy/plans/{id}` — delete plan

### AI Generation
- `POST /strategy/generate-plan` — AI analyzes DB and generates plan with items
  - Input: `{ name: str, count: int (10-20) }`
  - Process: Collects existing generations + products + presets from DB, sends to Claude
  - Claude returns: array of `{ prompt, description, style, preset, title_hint }`
  - Saves as new plan with items

### Item CRUD
- `POST /strategy/items` — add item manually
- `PUT /strategy/items/{id}` — edit item (prompt, style, order, etc.)
- `DELETE /strategy/items/{id}` — remove item
- `PUT /strategy/items/{id}/skip` — mark as skipped

### Execution
- `POST /strategy/plans/{id}/execute` — execute all planned items
  - Returns task_id for polling (background task pattern)
  - For each planned item: generate image → create product → schedule
  - Updates item status in real-time
- `GET /strategy/plans/{id}/execute/status` — poll execution progress

## AI Plan Generation

Claude receives:
1. Available styles and presets from `config.STYLE_PRESETS`
2. Existing generations (style + preset + prompt) — to avoid duplicates
3. Existing products (title, style) — to know what's already selling

Claude generates for each poster:
- **prompt**: Full Leonardo generation prompt
- **description**: Why this poster is worth creating (market gap, complements existing catalog)
- **style** + **preset**: Category classification
- **title_hint**: Suggested Etsy product title

## Execution Pipeline

When "Execute All Planned" is triggered:
1. Collect all items with status=planned, ordered by sort_order
2. For each item sequentially:
   a. Generate image via Leonardo API (prompt, model_id, size_id)
   b. Wait for generation to complete (poll)
   c. Create product via existing create-full-product flow (with title_hint)
   d. Add to publish schedule
   e. Update item status at each step
3. Errors on one item don't stop others
4. Frontend polls for progress updates

## UI Layout

Page: `/strategy`

```
┌─────────────────────────────────────────────────────────┐
│  Strategy Plans                    [+ New Plan] [AI ✨] │
├─────────────────────────────────────────────────────────┤
│  Plan: "February Collection"  (12 items, 3 done)        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ 🟢 Japanese  │ │ 🟡 Botanical │ │ ⚪ Abstract  │     │
│  │ Cat Moon     │ │ Monstera     │ │ Neon Arches  │     │
│  │ "Black cat   │ │ "Tropical    │ │ "Geometric   │     │
│  │  on roof..." │ │  monstera.." │ │  arches..."  │     │
│  │ ─────────    │ │ ─────────    │ │ ─────────    │     │
│  │ ✅ Product   │ │ ⏳ Generating│ │ [Run] [Edit] │     │
│  │    created   │ │              │ │ [Delete]     │     │
│  └──────────────┘ └──────────────┘ └──────────────┘     │
│                                                         │
│  [Execute All Planned ▶]              Coverage: 45/120  │
└─────────────────────────────────────────────────────────┘
```

Card statuses:
- `planned` (gray) → `generating` (yellow) → `generated` (blue) → `product_created` (green) → `skipped` (strikethrough)

Coverage metric: how many style×preset combinations have existing products vs total possible.
