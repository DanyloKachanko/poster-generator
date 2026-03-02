# SEO System Audit Report — Etsy Keywords 101 Compliance
Date: 2026-03-02

## Executive Summary

Our SEO system is **~70% compliant** with Etsy's updated Keywords 101 (March 2026) guidelines. The biggest gap is our assumption that **descriptions are NOT indexed** — Etsy now indexes them for search ranking. Our current system weights descriptions at only 15/100 points and tells Claude to write descriptions "for humans only." Additionally, we don't deduplicate tags against Etsy categories/attributes, wasting tag slots, and **zero listings use "size" tags** despite Etsy recommending them. Tag diversity is moderate but several listings over-index on descriptive tags at the expense of occasion, material, and style tags.

## Current Scoring Weights vs Etsy Guidelines

| Component | Current Weight | Etsy 2026 Emphasis | Gap |
|-----------|---------------|-------------------|-----|
| Title | 35 pts | Medium-High (holistic, not dominant) | Slightly over-weighted; Etsy now emphasizes holistic ranking over title-heavy |
| Tags | 35 pts | High (primary search matching) | Correct weight, but tag diversity rules need updating |
| Description | 15 pts | **Medium (NOW INDEXED for search)** | **Under-weighted by ~10 pts. Currently told NOT indexed — WRONG** |
| Metadata/Attributes | 5 pts | Medium (attributes act as free tags) | Under-weighted; attributes are essentially bonus tag slots |
| Market Fit | 10 pts | N/A (our addition) | Good addition for validation |

### Recommended Weight Changes

```
Title:       30 pts  (reduce from 35 — Etsy moved to holistic ranking)
Tags:        30 pts  (reduce from 35 — quality over quantity)
Description: 20 pts  (increase from 15 — NOW INDEXED)
Attributes:  10 pts  (increase from 5 — act as tags, free keyword slots)
Market Fit:  10 pts  (keep — our competitive advantage)
```

## Tag Diversity Analysis (15 sample listings)

| ID | Descriptive | Material | Who | Occasion | Solution | Style | Size | Title |
|----|:-----------:|:--------:|:---:|:--------:|:--------:|:-----:|:----:|-------|
| 79 | 4 | 3 | 2 | 1 | 1 | 2 | 0 | Peachy Botanical Leaves |
| 77 | 3 | 1 | 1 | 1 | 4 | 3 | 0 | Zen Rock Garden |
| 74 | 5 | 0 | 2 | 1 | 3 | 2 | 0 | Ocean Wave Art |
| 69 | 8 | 0 | 2 | 1 | 2 | 0 | 0 | Misty Mountain Forest |
| 65 | 4 | 1 | 2 | 1 | 3 | 2 | 0 | Olive Branch Art |
| 61 | 4 | 1 | 2 | 1 | 3 | 2 | 0 | Torii Gate Art |
| 53 | 5 | 0 | 1 | 1 | 3 | 3 | 0 | Marble Abstract Art |
| 44 | 6 | 0 | 2 | 1 | 2 | 2 | 0 | Zodiac Constellation Map |
| 40 | 4 | 1 | 2 | 1 | 3 | 2 | 0 | Monstera Leaf Art |
| 34 | 9 | 0 | 1 | 0 | 2 | 1 | 0 | Starry Night Sky |
| 21 | 8 | 0 | 2 | 0 | 2 | 1 | 0 | Fire Horse Art |
| 17 | 5 | 2 | 2 | 1 | 1 | 2 | 0 | Cherry Blossom Art |
| 12 | 11 | 0 | 1 | 0 | 1 | 0 | 0 | Night Sky Poster |
| 6 | 5 | 1 | 1 | 1 | 2 | 3 | 0 | Japanese Cat Poster |
| 1 | 1 | 3 | 2 | 2 | 3 | 2 | 0 | Koi Fish Zen Art |

### Tag Types Missing Across Shop

- **Size tags: 0/70 listings** — Zero listings have size-related tags like "large wall art", "small poster print". Etsy specifically recommends these.
- **Material tags: missing from 47% of sampled listings** — Tags like "matte paper print", "archival ink art" are underused.
- **Occasion tags: missing from 20% of sampled listings** — "housewarming gift", "birthday present" not present on all listings.
- **Style tags: missing from 13% of sampled listings** — Some listings rely entirely on descriptive tags.
- **Worst case: ID:12 (Night Sky)** has 11/13 descriptive tags and 0 material, 0 occasion, 0 style tags.

## Tag-Category Duplication

### Current Etsy Category

All DovShop listings are in Etsy taxonomy **1027 (Art & Collectibles > Prints > Digital Prints)** — assigned by Printify.

### Attribute Configuration

| Attribute | Current Value | Acts as Tag? |
|-----------|--------------|-------------|
| Materials | "Archival paper", "Ink" (hardcoded for all) | Partial — but very generic |
| Primary Color | Claude-generated (19 options) | Yes — Etsy uses for filtering |
| Secondary Color | Claude-generated | Yes |
| who_made | "someone_else" | No |
| when_made | "2020_2025" | No |
| Shop Section | Default (not per-listing) | Minimal |

### Duplication Issues

Since we set materials as "Archival paper" and "Ink" for ALL listings, and Etsy already indexes these as attributes, any tags containing these terms are partially wasted. However, the real issue is that **we're NOT leveraging attributes as tag-equivalents**:

- We could set more specific materials: "Museum quality matte paper", "Fade-resistant archival inks" — this gives us free keyword coverage
- Colors are set but not reflected in tags — if primary_color is "Green", having "green" in tags is redundant since Etsy already indexes the attribute

**Estimated wasted tag slots across shop: ~0.5 per listing** (low, because our tags are mostly specific enough to not duplicate category terms)

## Title Analysis

| Issue | Count | Listings |
|-------|-------|---------|
| Compliant (50-80ch, 2 pipes) | **57/70** | Most newer listings |
| Previously fixed (this session) | 13 | IDs 10-20, 29, 37, 38 |
| 1-pipe titles (older format) | 6 | IDs 2-7 |
| Average title length | 65 chars | Within ideal range |

### Title Format Assessment

**Strengths:**
- SK consistently front-loaded (first phrase before pipe)
- No filler adjectives detected across all 70 listings
- Clean pipe-separated structure

**Weaknesses:**
- Older listings (IDs 1-7) only have 1 pipe separator — could benefit from a third section for room/occasion context
- Some titles are very similar across niches (e.g., two "Cherry Blossom Art" titles: IDs 16 and 17)
- Etsy's 2026 guidance suggests shorter, more natural titles (like `Celestial Blue Moonstone Ring: 9k Solid Gold Band`) vs our structured pipe format

## Description Analysis

### Issues Found (17 listings)

| Issue | Count | Severity |
|-------|-------|----------|
| Banned phrases in first 160 chars | **15 listings** | Medium — "stunning" (10), "transform your space" (2), "elevate" (2), "captivating" (1), "breathtaking" (1) |
| SK missing from first 160 chars | **2 listings** (IDs 14, 60) | High — SK should be in Google snippet zone |
| Description < 500 chars | 0 | Good |
| Missing AVAILABLE SIZES section | ~5 older listings | Low |

### Critical Finding: "Descriptions NOT indexed" is WRONG

Our system prompt tells Claude:
> "Descriptions are NOT indexed for Etsy internal search"

**Etsy's March 2026 Keywords 101 update confirms descriptions ARE now indexed.** This means:
1. Description keywords contribute to search matching
2. We should weave more search terms naturally into descriptions
3. Description weight in scoring should increase

### Banned Phrase Usage (worst offenders)

| Listing | Banned Phrases Found |
|---------|---------------------|
| ID:17 Cherry Blossom | "Transform your space", "breathtaking" |
| ID:15 Tropical Palm Leaf | "Transform your space", "elevate" |
| ID:13 Valentine Heart | "Elevate", "stunning" |
| ID:19 Japanese Mountain | "stunning" |
| ID:22 Horse Cherry Blossom | "stunning" |
| ID:29 Tuscany Landscape | "stunning" |
| ID:40 Monstera Leaf | "stunning" |
| ID:44 Zodiac Constellation | "stunning" |
| ID:62 Succulent Plants | "stunning" |
| ID:63 Lunar Eclipse | "stunning" |

"Stunning" appears in 10/70 listing descriptions despite being on the banned list. These were likely generated before the ban was added to prompts.

## Root Word Repetition

| ID | Title | Over-repeated Word | Count | Impact |
|----|-------|-------------------|-------|--------|
| 6 | Japanese Cat Poster | "cat" | 6x | High — 6 of 13 tags contain "cat" |
| 23 | Chinese horse art | "horse" | 6x | High — heavy keyword stuffing |
| 22 | Horse Cherry Blossom | "horse" | 5x | High |
| 7 | Black Cat Cherry Blossoms | "cat" | 4x | Medium |
| 21 | Fire Horse Art | "horse" | 4x | Medium |
| 13 | Valentine Heart Art | "heart" | 4x | Medium |
| 77 | Zen Rock Garden | "zen" | 4x | Medium |
| 24 | Abstract Circle Art | "abstract" | 4x | Medium |

**8 listings have root word repetition > 3 tags** (our own rule says max 3). These are mostly older listings that pre-date the V2 prompt rules.

## Claude Prompt Review

### Current Title Instructions
- 50-80 chars ideal, max 140
- SK must be FIRST phrase
- Max 2 pipe separators
- No filler adjectives (10 banned words)
- Front-load primary keyword

**Gap vs Etsy 2026:** Etsy now suggests more natural, readable titles rather than pipe-separated keyword blocks. Consider allowing colon separators too (e.g., "Japanese Mountain Art: Mount Fuji Poster for Japandi Bedroom").

### Current Tag Instructions
- Exactly 13 tags, max 20 chars each
- 6 buyer-intent categories (core, buyer_intent, style, room, occasion, niche)
- No root word in >3 tags
- No standalone generic terms

**Gaps vs Etsy 2026:**
- [ ] No "size" tag category (e.g., "large wall art", "small print")
- [ ] No "material/technique" tag category explicitly encouraged
- [ ] No guidance to avoid duplicating category/attribute terms
- [ ] Tag priority tiers could emphasize occasion/gift tags more (Etsy data shows high conversion)

### Current Description Instructions
- Min 500 chars
- SK in first sentence, within 160 chars
- Weave 5-8 tag keywords
- Structured sections (PERFECT FOR, PRINT DETAILS, AVAILABLE SIZES)
- Banned phrases list

**Gaps vs Etsy 2026:**
- [x] ~~Description told NOT indexed~~ — **CRITICAL: Now IS indexed, prompt needs update**
- [ ] Should encourage more keyword-rich natural language (not just for Google, now for Etsy too)
- [ ] "stunning" still appears in 10 descriptions despite being banned — older listings need description refresh
- [ ] Should include room-specific and occasion-specific keywords more deliberately

## Priority Fixes (Ranked)

### Critical (High Impact)
1. **Update description guidance: descriptions ARE now indexed by Etsy** — Change system prompt, scoring weights, and generation instructions. This is the single biggest SEO gap.
2. **Add "size" tag category** — Zero listings have size tags. Add 1 size tag per listing (e.g., "large wall art", "small poster"). Free traffic from size-specific searches.
3. **Fix 8 listings with root word repetition >3** — IDs 6, 7, 13, 21, 22, 23, 24, 77. Replace repeated-root tags with diverse alternatives.

### Important (Medium Impact)
4. **Refresh 15 descriptions with banned phrases** — Especially the 10 with "stunning" and 2 with "transform your space". Regenerate using current prompt rules.
5. **Fix 2 listings missing SK in description** — IDs 14 (Valentine) and 60 (Solar System).
6. **Leverage attributes as free keywords** — Set more specific materials ("Museum quality 264gsm matte paper", "Fade-resistant archival inks") instead of generic "Archival paper", "Ink".
7. **Add material/technique tags** — 47% of sampled listings have zero material tags. Add "watercolor print", "ink art", "matte paper poster" etc.

### Nice to Have (Low Impact)
8. **Update older titles (IDs 1-7)** — Add second pipe section for room/occasion context.
9. **Differentiate duplicate-similar titles** — IDs 16 and 17 both start with "Cherry Blossom Art"; IDs 11 and 19 both target Mount Fuji.
10. **Explore colon-style titles** — Etsy's 2026 examples use colons, not just pipes. Test on a few listings.

## Scoring System V3 Recommendations

```
Current V2:                    Proposed V3:
Title:       35 pts            Title:       30 pts (-5, holistic ranking)
Tags:        35 pts            Tags:        30 pts (-5, quality > quantity)
Description: 15 pts            Description: 20 pts (+5, NOW INDEXED)
Metadata:     5 pts            Attributes:  10 pts (+5, act as free tags)
Market Fit:  10 pts            Market Fit:  10 pts (keep)
                               Total:       100 pts

New checks to add:
- Description: keyword density score (natural, not stuffed)
- Tags: size tag present (+2 pts)
- Tags: material/technique tag present (+2 pts)
- Tags: no duplication with category/attributes (-2 pts per dup)
- Attributes: materials specificity score
```

## Raw Data: 15 Sample Listings

### ID:1 — Koi Fish Zen Art | Japanese Garden Poster | Indigo Gold Wall Decor
Tags: koi fish zen art, japanese garden art, zen wall decor, gold koi print, indigo wall art, meditation room art, zen home poster, gift for him, housewarming gift, gift for friend, japandi style art, watercolor koi art, ink koi poster

### ID:6 — Japanese Cat Poster | Gold Eyes Woodblock Art
Tags: japanese cat poster, cat wall art, ukiyo-e cat print, woodblock cat art, japanese home decor, cat lover gift, bedroom cat poster, gift for cat lover, cat person gift, vintage cat print, cat art decor, gold eyes cat art, asian cat wall art

### ID:12 — Night Sky Poster | Celestial Constellation Print | Astronomy Wall Art
Tags: night sky poster, constellation print, celestial wall art, astronomy poster, star map art, bedroom decor art, space lover gift, cosmic wall decor, stargazer gift, moon stars poster, abstract sky art, zodiac wall decor, minimal star art

### ID:17 — Cherry Blossom Art | Japanese Sakura Poster | Pink Zen Wall Decor
Tags: cherry blossom art, sakura poster, japanese wall art, pink floral print, zen bedroom decor, spring flower art, japandi wall decor, gift for her, housewarming gift, nature lover gift, botanical pink art, sakura branch print, minimalist floral

### ID:21 — Fire Horse Art | Flaming Stallion Poster | Modern Fantasy Wall Decor
Tags: fire horse art, flaming horse poster, horse wall art, stallion print, fantasy wall decor, modern horse art, bedroom horse poster, horse lover gift, equestrian gift, dark horse art, wild horse print, horse owner gift, fiery stallion art

### ID:34 — Starry Night Sky | Abstract Galaxy Poster | Blue Space Wall Art
Tags: starry night sky, galaxy wall art, abstract space art, blue cosmic poster, star wall decor, bedroom space art, astronomy lover gift, cosmic blue print, nebula wall art, space poster art, dark sky print, celestial poster, midnight sky art

### ID:40 — Monstera Leaf Art | Tropical Botanical Poster | Green Plant Decor
Tags: monstera leaf art, tropical botanical, green plant poster, monstera wall decor, living room wall art, plant lover gift, housewarming gift, botanical monstera, modern plant art, watercolor monstera, jungle leaf print, green leaf decor, boho plant poster

### ID:44 — Zodiac Constellation Map | Astrology Poster | Gold Star Art
Tags: zodiac constellation, astrology poster, star chart art, gold zodiac print, celestial map decor, bedroom wall poster, astrology gift, star map poster, gift for astrologer, constellation print, zodiac wall decor, mystical star art, horoscope poster

### ID:53 — Marble Abstract Art | Luxury Slate Blue Poster | Modern Home Decor
Tags: marble abstract art, slate blue poster, luxury wall art, modern abstract print, living room poster, office decor gift, housewarming gift, contemporary art, marble texture art, blue gray poster, sophisticated art, elegant wall decor, minimalist marble

### ID:61 — Torii Gate Art | Japanese Temple Poster | Zen Meditation Decor
Tags: torii gate art, japanese temple, zen poster print, shrine wall art, japan travel poster, meditation room art, gift for traveler, housewarming gift, japandi wall decor, watercolor torii, asian temple art, peaceful zen decor, japanese culture

### ID:65 — Olive Branch Art | Mediterranean Botanical Poster | Sage Green Decor
Tags: olive branch art, botanical poster, mediterranean decor, sage green print, kitchen wall art, olive leaf print, gift for her, housewarming gift, watercolor olive, farmhouse botanical, tuscan wall art, minimalist branch, herb garden art

### ID:69 — Misty Mountain Forest | Dramatic Nature Poster | Moody Landscape Art
Tags: misty mountain art, forest poster, moody landscape, mountain wall decor, nature wall art, pine forest print, gift for hiker, nature lover gift, dark forest art, fog mountain print, dramatic nature, wilderness poster, outdoor lover gift

### ID:74 — Ocean Wave Art | Japanese Woodblock Poster | Coastal Decor
Tags: ocean wave art, japanese wave poster, ukiyo-e wall art, coastal wall decor, beach house art, blue wave print, gift for surfer, housewarming gift, japanese home decor, seascape poster, nautical wall art, ocean lover gift, hokusai inspired

### ID:77 — Zen Rock Garden | Minimalist Japanese Poster | Meditation Art
Tags: zen rock garden, japanese zen art, minimalist zen decor, meditation wall art, zen bathroom art, calm zen poster, gift for yogi, housewarming gift, japanese garden art, zen home decor, mindfulness art, serene zen print, tranquil zen art

### ID:79 — Peachy Botanical Leaves | Romantic Nature Poster | Cottage Art
Tags: peachy botanical, romantic nature art, cottage wall art, watercolor leaves, pink leaf poster, bedroom wall decor, gift for her, housewarming gift, nature lover gift, cottagecore decor, pastel botanical, soft pink art, farmhouse wall art
