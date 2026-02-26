# Navigation Redesign — Pipeline Modules

## Goal

Reorganize navigation from 17 scattered links into 6 pipeline modules. Each module = one stage of the poster lifecycle. No dropdowns, just top-level tabs with sub-tabs inside each module.

## Pipeline

```
Strategy → Create → Products → Mockups → Publish → Monitor
```

## Module Mapping

### 1. Strategy (`/strategy`)
No changes. Already a single page.

### 2. Create (`/create`)
Combines: Generate (`/`) + Batch (`/batch`) + History (`/history`)

| Tab | Source | URL |
|-----|--------|-----|
| Generate | `frontend/app/page.tsx` | `/create` |
| Batch | `frontend/app/batch/page.tsx` | `/create/batch` |
| History | `frontend/app/history/page.tsx` | `/create/history` |

### 3. Products (`/products`)
Combines: Products + Shop + SEO + Sync Etsy

| Tab | Source | URL |
|-----|--------|-----|
| All Products | `frontend/app/products/page.tsx` | `/products` |
| SEO | `frontend/app/seo/page.tsx` | `/products/seo` |
| Sync | `frontend/app/sync-etsy/page.tsx` | `/products/sync` |

Detail pages: `/products/[id]` stays. `/shop/[id]` accessible but not in nav.

### 4. Mockups (`/mockups`)
Combines: Gallery + Generate + Workflow (already under /mockups)

| Tab | Source | URL |
|-----|--------|-----|
| Gallery | `frontend/app/mockups/page.tsx` | `/mockups` |
| Templates | `frontend/app/mockups/generate/page.tsx` | `/mockups/templates` |
| Workflow | `frontend/app/mockups/workflow/page.tsx` | `/mockups/workflow` |

### 5. Publish (`/publish`)
Combines: Schedule + Calendar + DovShop

| Tab | Source | URL |
|-----|--------|-----|
| Queue | `frontend/app/schedule/page.tsx` | `/publish` |
| Calendar | `frontend/app/calendar/page.tsx` | `/publish/calendar` |
| DovShop | `frontend/app/dovshop/page.tsx` | `/publish/dovshop` |

### 6. Monitor (`/monitor`)
Combines: Dashboard + Analytics + Competitors

| Tab | Source | URL |
|-----|--------|-----|
| Overview | `frontend/app/dashboard/page.tsx` | `/monitor` |
| Analytics | `frontend/app/analytics/page.tsx` | `/monitor/analytics` |
| Competitors | `frontend/app/competitors/page.tsx` | `/monitor/competitors` |

Competitors discover: `/monitor/competitors/discover`

## Hidden Pages (accessible by URL, not in nav)
- `/shop`, `/shop/[id]` — legacy, Products covers this
- `/providers` — reference page
- `/login` — auth only

## Implementation Approach

**Phase 1: Shared tab layout component**
Create a reusable `ModuleLayout` component with tab navigation.

**Phase 2: Move pages into module directories**
For each module, create a layout.tsx with tabs and move/re-export existing page components.

**Phase 3: Update Header**
Replace current nav (3 top links + 3 dropdowns) with 6 flat links.

**Phase 4: Redirects**
Add redirects from old URLs to new ones (e.g., `/batch` → `/create/batch`).

## Navigation Bar (new)

```
Strategy    Create    Products    Mockups    Publish    Monitor
```

No dropdowns. Active module highlighted. Sub-tabs shown inside the page content area.
