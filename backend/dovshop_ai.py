"""AI-driven enrichment for DovShop products using Claude API."""

import json
import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude response, stripping markdown fences if present."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text, strict=False)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"


async def enrich_product(
    title: str,
    tags: list[str],
    style: str | None,
    description: str,
    image_url: str,
    existing_collections: list[dict],
    existing_categories: list[dict],
) -> dict:
    """Ask Claude to determine best placement for a poster on DovShop.

    Returns dict with:
        categories: list[str]  — category slugs
        collection_name: str | None — existing collection name or new one to create
        seo_description: str — unique SEO description for dovshop.org
        featured: bool — whether to feature this poster
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY, falling back to basic categorization")
        from categorizer import categorize_product
        return {
            "categories": categorize_product(tags, style),
            "collection_name": None,
            "seo_description": description,
            "featured": False,
        }

    coll_names = [c.get("name", "") for c in existing_collections]
    cat_slugs = [c.get("slug", "") for c in existing_categories]

    prompt = f"""You are an SEO specialist for an art poster e-commerce site (dovshop.org).

A new poster is being added. Decide its placement and write an SEO description.

POSTER INFO:
- Title: {title}
- Style: {style or 'unknown'}
- Tags: {', '.join(tags[:20]) if tags else 'none'}
- Current description: {description[:300] if description else 'none'}

EXISTING COLLECTIONS on the site: {', '.join(coll_names) if coll_names else 'none yet'}
EXISTING CATEGORIES: {', '.join(cat_slugs) if cat_slugs else 'none yet'}

Return JSON only:
{{
  "categories": ["slug1", "slug2"],
  "collection_name": "name" or null,
  "seo_description": "...",
  "featured": false
}}

Category slugs to choose from: japanese, botanical, abstract, celestial, landscape, living-room, bedroom, office, bathroom, nursery, kitchen, hallway, gift-ideas, meditation-space
Pick 1-4 categories. For collection_name, pick from existing or suggest a short thematic name, or null.
SEO description: 2-3 sentences, unique (NOT a copy of Etsy listing), include relevant keywords naturally.
Featured: true only for exceptional/unique pieces."""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                ANTHROPIC_URL,
                headers=headers,
                json={
                    "model": MODEL,
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            result = _extract_json(text)
            result.setdefault("categories", [])
            result.setdefault("collection_name", None)
            result.setdefault("seo_description", description)
            result.setdefault("featured", False)
            return result
    except Exception as e:
        logger.error("AI enrichment failed: %s", e)
        from categorizer import categorize_product
        return {
            "categories": categorize_product(tags, style),
            "collection_name": None,
            "seo_description": description,
            "featured": False,
        }


async def analyze_catalog_strategy(
    products: list[dict],
    collections: list[dict],
    categories: list[dict],
) -> dict:
    """Ask Claude to analyze the full DovShop catalog and suggest improvements.

    Returns dict with:
        new_collections: list[{name, description, poster_ids}]
        feature_recommendations: list[{id, title, reason}]
        category_gaps: list[{slug, suggestion}]
        seo_improvements: list[{id, title, suggested_desc}]
        summary: str
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    product_summaries = []
    for p in products[:100]:
        product_summaries.append({
            "id": p.get("id"),
            "name": p.get("name") or p.get("title", ""),
            "style": p.get("style") or "",
            "tags": (p.get("tags") or [])[:5],
            "categories": [c.get("slug", "") for c in (p.get("categories") or [])],
            "collection": (p.get("collection") or {}).get("name"),
            "featured": p.get("featured", False),
            "has_description": bool(p.get("description")),
        })

    coll_summaries = [{"name": c.get("name"), "poster_count": (c.get("_count") or {}).get("posters", 0)} for c in collections]
    cat_summaries = [{"slug": c.get("slug"), "type": c.get("type")} for c in categories]

    prompt = f"""You are an SEO strategist for dovshop.org (art poster e-commerce).

Analyze this catalog and provide specific, actionable recommendations.

CATALOG ({len(products)} products):
{json.dumps(product_summaries, indent=1)}

COLLECTIONS: {json.dumps(coll_summaries)}
CATEGORIES: {json.dumps(cat_summaries)}

Return JSON:
{{
  "new_collections": [
    {{"name": "Collection Name", "description": "SEO desc", "poster_ids": [1, 2, 3]}}
  ],
  "feature_recommendations": [
    {{"id": 1, "title": "Poster Name", "reason": "Why feature it"}}
  ],
  "category_gaps": [
    {{"slug": "botanical", "suggestion": "Generate more botanical posters to fill this category"}}
  ],
  "seo_improvements": [
    {{"id": 1, "title": "Poster Name", "suggested_desc": "Better SEO description"}}
  ],
  "summary": "2-3 sentence overall assessment and top priority actions"
}}

Be specific. Reference actual poster IDs and names. Limit to top 5 recommendations per section."""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                ANTHROPIC_URL,
                headers=headers,
                json={
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            logger.info("AI strategy raw response length: %d", len(text))
            return _extract_json(text)
    except Exception as e:
        logger.error("AI strategy analysis failed: %s", e, exc_info=True)
        return {"error": str(e)}
