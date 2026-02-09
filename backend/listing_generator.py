"""Etsy listing text generator using Claude API"""

import os
import json
import httpx
from typing import Optional
from dataclasses import dataclass

from prompts import SYSTEM_PROMPT, LISTING_PROMPT_TEMPLATE, get_style_context


@dataclass
class EtsyListing:
    title: str
    tags: list[str]
    description: str
    superstar_keyword: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "tags": self.tags,
            "description": self.description,
            "tags_string": ", ".join(self.tags),
            "superstar_keyword": self.superstar_keyword,
        }


class ListingGenerator:
    """Generate Etsy listing text using Claude API"""

    BASE_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-5-20250929"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    async def generate_listing(
        self,
        style: str,
        preset: str,
        description: str,
        custom_keywords: Optional[list[str]] = None,
    ) -> EtsyListing:
        """Generate complete Etsy listing"""

        style_context = get_style_context(style, preset)

        full_description = description
        if custom_keywords:
            full_description += f"\nAdditional keywords to consider: {', '.join(custom_keywords)}"

        prompt = LISTING_PROMPT_TEMPLATE.format(
            style=style,
            preset=preset,
            description=full_description + "\n" + style_context,
        )

        payload = {
            "model": self.MODEL,
            "max_tokens": 2048,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

        content = data["content"][0]["text"]

        # Clean up JSON if wrapped in markdown code block
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        listing_data = json.loads(content, strict=False)

        # Validate and enforce limits
        title = listing_data["title"][:140]
        tags = [tag[:20].lower().strip() for tag in listing_data.get("tags", [])[:13]]
        # Pad to 13 if model returned fewer
        while len(tags) < 13:
            tags.append(f"wall art print {len(tags)}"[:20])
        desc = listing_data.get("description", "")
        sk = listing_data.get("superstar_keyword", "")

        return EtsyListing(
            title=title,
            tags=tags,
            description=desc,
            superstar_keyword=sk,
        )

    async def regenerate_title(
        self,
        style: str,
        preset: str,
        current_title: str,
    ) -> str:
        """Generate alternative title"""

        prompt = f"""Current Etsy listing title: "{current_title}"
Style: {style}, Theme: {preset}

Generate 1 alternative title following these rules:
- Max 140 characters
- Start with the main keyword (superstar keyword)
- Separate sections with " | "
- No repeated words across the whole title
- Must read naturally, not spammy
- Include: what it is + style + who it's for/where it goes

Respond with ONLY the new title, no quotes, no explanation."""

        payload = {
            "model": self.MODEL,
            "max_tokens": 200,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return data["content"][0]["text"].strip()[:140]

    async def regenerate_tags(
        self,
        style: str,
        preset: str,
        current_tags: list[str],
        title: str = "",
    ) -> list[str]:
        """Generate alternative tags"""

        tags_str = ", ".join(current_tags) if current_tags else "none"
        title_context = f'\nProduct title: "{title}"' if title else ""

        prompt = f"""Current Etsy listing tags: {tags_str}{title_context}
Style: {style}, Theme: {preset}

Generate exactly 13 new Etsy tags following this structure:
1. superstar keyword (main search query)
2. gift keyword (gift for her/him/mom)
3. product type variation (poster/print/wall art synonym)
4. style + product
5. room + decor
6. occasion/season keyword
7. synonym of main keyword
8. adjective + product
9. different room variation
10. seasonal/trend keyword
11. niche keyword
12. alternative name for subject
13. broad category

RULES:
- Each tag: 2-3 words, max 20 characters, lowercase
- No single-word tags
- Don't repeat the same word in more than 2-3 tags
- Different from current tags where possible

Respond with ONLY a comma-separated list of 13 tags, no quotes, no explanation."""

        payload = {
            "model": self.MODEL,
            "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        text = data["content"][0]["text"].strip()
        tags = [tag[:20].lower().strip() for tag in text.split(",") if tag.strip()]
        return tags[:13]

    async def regenerate_description(
        self,
        style: str,
        preset: str,
        current_description: str,
        tone: str = "warm",
    ) -> str:
        """Generate alternative description with different tone"""

        prompt = f"""Rewrite this Etsy poster description with a {tone} tone:

"{current_description}"

Style: {style}, Theme: {preset}

Follow this structure:
- Paragraph 1: Superstar keyword in first sentence (first 160 chars critical for Google SEO). What this poster is, who it's for.
- Paragraph 2: Repeat keyword naturally. Expanded value — what interiors it complements.
- ♥ PERFECT FOR: 4 bullet points (use cases, gift ideas, rooms)
- 🖼 PRINT DETAILS: Museum-quality matte paper (250 gsm / 110 lb), fade-resistant archival inks, multiple sizes, sturdy packaging, frame not included
- 📐 AVAILABLE SIZES: 8×10 (20×25cm), 11×14 (28×36cm), 12×16 (30×40cm), 16×20 (40×50cm), 18×24 (45×60cm), 24×36 (60×90cm)
- 🎁 Gift angle paragraph
- Last line: shop promo for DovShopDesign

RULES:
- Min 300 characters total
- NO generic phrases like "Transform your space"
- Be specific about colors, subject, mood

Respond with ONLY the new description, no quotes."""

        payload = {
            "model": self.MODEL,
            "max_tokens": 1500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return data["content"][0]["text"].strip()
