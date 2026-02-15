"""Etsy listing text generator using Claude API"""

import os
import json
import base64
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
    MODEL = "claude-haiku-4-5-20251001"

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

    async def regenerate_seo_from_existing(
        self,
        current_title: str,
        current_tags: list[str],
        current_description: str,
    ) -> EtsyListing:
        """Generate improved SEO for an existing listing based on its current content."""

        tags_str = ", ".join(current_tags) if current_tags else "none"

        prompt = f"""You are optimizing an existing Etsy wall art poster listing for better SEO.

CURRENT LISTING:
Title: "{current_title}"
Tags: {tags_str}
Description: "{current_description[:500]}"

Analyze this listing and generate an IMPROVED version following Etsy A10 SEO best practices:

1. Identify the "Superstar Keyword" (SK) — the main 2-3 word search query buyers use
2. SK must be FIRST in the title and FIRST in the description (within first 160 chars)
3. Title: max 140 chars, sections separated by " | ", no repeated words
4. Tags: exactly 13, each 2-3 words, max 20 chars, lowercase
5. Description: SK in first sentence, min 300 chars, keep the same product details sections (PERFECT FOR, PRINT DETAILS, AVAILABLE SIZES, gift angle, shop promo for DovShopDesign)
6. AVAILABLE SIZES: keep ONLY the sizes from the original description, do NOT add sizes that are not in the original

Keep the same product type and subject matter. Improve keyword placement and variety.

Respond with valid JSON only:
{{"title": "...", "tags": ["tag1", ..., "tag13"], "description": "...", "superstar_keyword": "..."}}"""

        payload = {
            "model": self.MODEL,
            "max_tokens": 2048,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
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
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        listing_data = json.loads(content, strict=False)

        title = listing_data["title"][:140]
        tags = [tag[:20].lower().strip() for tag in listing_data.get("tags", [])[:13]]
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

    async def generate_seo_from_image(
        self,
        image_url: str,
        current_title: str = "",
        niche: str = "",
        enabled_sizes: list = None,
    ) -> dict:
        """Generate full SEO content from a poster image using Claude vision."""

        # Download and encode image
        async with httpx.AsyncClient() as client:
            img_resp = await client.get(
                image_url, timeout=15.0, follow_redirects=True
            )
            img_resp.raise_for_status()
            content_type = (
                img_resp.headers.get("content-type", "image/jpeg")
                .split(";")[0]
                .strip()
            )
            img_b64 = base64.b64encode(img_resp.content).decode("ascii")

        niche_hint = f"\nNICHE/STYLE HINT: {niche}" if niche else ""
        current_hint = (
            f'\nCURRENT TITLE (for reference): "{current_title}"'
            if current_title
            else ""
        )

        # Build dynamic sizes from enabled_sizes or default all
        all_sizes_map = {
            "8x10": "8×10 inches (20×25 cm)",
            "11x14": "11×14 inches (28×36 cm)",
            "12x16": "12×16 inches (30×40 cm)",
            "16x20": "16×20 inches (40×50 cm)",
            "18x24": "18×24 inches (45×60 cm)",
            "24x36": "24×36 inches (60×90 cm)",
        }
        sizes_list = enabled_sizes if enabled_sizes else list(all_sizes_map.keys())
        sizes_short = ", ".join(sizes_list)
        sizes_block = "\n".join(
            f"- {all_sizes_map[s]}" for s in all_sizes_map if s in sizes_list
        )

        prompt = f"""Look at this wall art poster and generate optimized Etsy listing content.
{current_hint}{niche_hint}

STRICT RULES:
1. Title: Under 140 characters. Use " | " as separator. Superstar keyword FIRST.
2. Tags: EXACTLY 13 tags. Each max 20 characters. Each 2-3 words. No single-word tags.
3. Description: Superstar keyword in FIRST sentence within first 160 chars. Min 300 chars total.
4. Superstar keyword (SK): 2-3 words, under 20 characters, specific to this poster.

PRODUCT INFO:
- Type: Wall art poster print
- Paper: Museum-quality matte paper (250 gsm / 110 lb)
- Ink: Vibrant, fade-resistant archival inks
- Sizes: {sizes_short} inches
- Frame: Not included
- Brand: DovShopDesign

IMPORTANT: ONLY list the sizes shown above. Do NOT add any other sizes.

DESCRIPTION FORMAT (follow exactly):
[SK] — [emotional hook about what the poster depicts, 1-2 sentences].

[Second paragraph: repeat SK naturally, describe who it's for and what interiors it complements].

♥ PERFECT FOR:
- [specific use case 1]
- [specific use case 2 — gift angle]
- [specific use case 3 — room/style]
- [specific use case 4 — occasion]

🖼 PRINT DETAILS:
- Museum-quality matte paper (250 gsm / 110 lb)
- Vibrant, fade-resistant archival inks
- Available in multiple sizes to fit your space
- Shipped in sturdy protective packaging
- Frame not included

📐 AVAILABLE SIZES:
{sizes_block}

⚠️ PLEASE NOTE:
- This listing is for the POSTER PRINT ONLY — frame is not included
- Please double-check the size you are ordering before purchase
- Need a custom size? Message us and we'll work it out together

🎁 [Gift angle — who to gift it to and why].

[Relevant emoji] More designs at DovShopDesign — where thoughtful design meets everyday spaces.

TAG STRUCTURE (follow this order):
1. superstar keyword
2. gift keyword (gift for her/him/mom)
3. product type variation
4. style + product
5. room + decor
6. occasion keyword
7. synonym of SK
8. adjective + product
9. different room variation
10. trend keyword
11. niche keyword
12. alternative name
13. broad category

5. Primary color: The DOMINANT color in the poster. Must be exactly one of: Beige, Black, Blue, Bronze, Brown, Clear, Copper, Gold, Gray, Green, Orange, Pink, Purple, Rainbow, Red, Rose gold, Silver, White, Yellow
6. Secondary color: The SECOND most prominent color. Same allowed values as above. Must be DIFFERENT from primary color.
7. Alt texts: Generate exactly 5 DIFFERENT alt text descriptions for listing images (max 250 chars each):
   - alt_text_1: Describe the poster artwork itself (what it depicts, colors, style)
   - alt_text_2: "[Subject] wall art poster print displayed in a modern living room"
   - alt_text_3: "[Subject] framed art print mockup in a cozy bedroom setting"
   - alt_text_4: "[Subject] poster detail close-up showing print quality and colors"
   - alt_text_5: "[Subject] minimalist wall art in a contemporary home interior"

OUTPUT FORMAT (respond ONLY with this JSON, no other text):
{{"superstar_keyword": "...", "title": "...", "tags": ["tag1", ..., "tag13"], "description": "...", "materials": ["material1", "material2"], "primary_color": "...", "secondary_color": "...", "alt_texts": ["alt1", "alt2", "alt3", "alt4", "alt5"]}}

VALIDATE BEFORE RESPONDING:
- Title < 140 chars
- Each tag <= 20 chars
- Exactly 13 tags
- No single-word tags
- SK in title and first 160 chars of description
- primary_color and secondary_color are from the allowed list and different from each other
- Each alt_text <= 250 chars, exactly 5 alt texts"""

        payload = {
            "model": self.MODEL,
            "max_tokens": 3000,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=90.0,
            )
            response.raise_for_status()
            data = response.json()

        content = data["content"][0]["text"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content, strict=False)

        # Enforce basic limits
        result["title"] = result.get("title", "")[:140]
        result["tags"] = [
            tag[:20].lower().strip() for tag in result.get("tags", [])[:13]
        ]
        while len(result["tags"]) < 13:
            result["tags"].append(f"wall art print {len(result['tags'])}"[:20])
        result["description"] = result.get("description", "")
        result["superstar_keyword"] = result.get("superstar_keyword", "")
        result["materials"] = result.get("materials", ["Archival paper", "Ink"])

        # Validate colors
        VALID_COLORS = {"Beige", "Black", "Blue", "Bronze", "Brown", "Clear", "Copper",
                        "Gold", "Gray", "Green", "Orange", "Pink", "Purple", "Rainbow",
                        "Red", "Rose gold", "Silver", "White", "Yellow"}
        result["primary_color"] = result.get("primary_color", "") if result.get("primary_color") in VALID_COLORS else ""
        result["secondary_color"] = result.get("secondary_color", "") if result.get("secondary_color") in VALID_COLORS else ""
        alt_texts = result.get("alt_texts", [])
        if not isinstance(alt_texts, list):
            alt_texts = []
        result["alt_texts"] = [str(a)[:250] for a in alt_texts[:5]]
        # Pad to 5 if fewer
        while len(result["alt_texts"]) < 5:
            result["alt_texts"].append(result.get("title", "Wall art poster print")[:250])

        return result

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
- 📐 AVAILABLE SIZES: keep only sizes from the original description, do NOT add new sizes
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
