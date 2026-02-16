# SEO Overhaul Design — 2026-02-16

## Problem
Current SEO prompts follow outdated 2024 rules (140-char stuffed titles, rigid tag formula, thin descriptions). Scoring gives grade A to mediocre listings because it only checks format, not quality.

## Solution
Rewrite Claude prompts to 2026 Etsy best practices + overhaul scoring rubric.

## Changes

### 1. prompts.py — SYSTEM_PROMPT
- Title target: 50-80 chars (was 80-140)
- Tags: "multi-word preferred" not "required", diverse buyer-intent categories
- Description: min 500 chars, integrate 5-8 tag keywords naturally
- Stricter ban on AI filler phrases

### 2. prompts.py — LISTING_PROMPT_TEMPLATE
- New tag strategy: 6 buyer-intent categories (core, buyer-intent, style, room, occasion, long-tail)
- Shorter title format: max 2 pipe sections
- Added paragraph 3 (story/artistic angle) to description
- Expanded STYLE_KEYWORDS with more styles

### 3. listing_generator.py — AI-fill vision prompt
- Align with same new rules (title length, tag categories, description depth)

### 4. frontend/lib/seo-score.ts — Scoring overhaul
New 100-point rubric:
- Title (30 pts): optimal length, SK position, structure, no repeats
- Tags (30 pts): count, format, category diversity (10 pts), keyword stuffing check, no dupes
- Description (25 pts): length, SK in first 160, tag keywords in text, structured sections
- Metadata (15 pts): materials, colors, alt texts

Key new check: tag category diversity (10 pts) — classifies tags into intent categories and penalizes if all tags serve the same intent.

## Files to modify
1. `backend/prompts.py`
2. `backend/listing_generator.py` (AI-fill prompt)
3. `frontend/lib/seo-score.ts`
