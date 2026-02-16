"""Etsy listing text generator using Claude API"""

import io
import os
import json
import base64
import httpx
from typing import Optional
from dataclasses import dataclass
from PIL import Image

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

    @staticmethod
    def _check_response(response: httpx.Response):
        """Raise with Anthropic error details instead of generic HTTP error."""
        if response.is_success:
            return
        try:
            body = response.json()
            msg = body.get("error", {}).get("message", response.text[:500])
        except Exception:
            msg = response.text[:500]
        raise Exception(f"Anthropic API error {response.status_code}: {msg}")

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
            self._check_response(response)
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

Generate an IMPROVED version following 2026 Etsy SEO best practices:

1. Identify the "Superstar Keyword" (SK) — the main 2-4 word search phrase buyers type
2. SK must be FIRST in the title and within the first 160 chars of description
3. Title: 50-80 chars ideal, max 2 pipe " | " sections, front-load SK, no repeated words
4. Tags: exactly 13, max 20 chars each, lowercase. Cover 6 buyer-intent categories:
   - CORE (2): SK + synonym
   - BUYER INTENT (3): gift angle, purchase motivation, buyer persona
   - STYLE/AESTHETIC (3): visual style, technique, trend
   - ROOM/SPACE (2): primary room, secondary room
   - OCCASION (2): seasonal, specific occasion
   - LONG-TAIL NICHE (1): ultra-specific search term
5. Description: SK in first sentence, min 500 chars. 3 keyword-rich paragraphs before structured sections. Keep PERFECT FOR, PRINT DETAILS, AVAILABLE SIZES, gift angle, shop promo for DovShopDesign.
6. AVAILABLE SIZES: keep ONLY the sizes from the original description, do NOT add new sizes
7. Do NOT waste tags on broad category terms (e.g., "wall art" or "poster" alone)
8. Do NOT repeat the same root word in more than 3 tags

Keep the same product type and subject matter. Improve keyword placement, diversity, and buyer-intent coverage.

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
            self._check_response(response)
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
            # Normalize content type — Anthropic only accepts image/jpeg|png|gif|webp
            allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
            if content_type not in allowed:
                # Detect from magic bytes
                header = img_resp.content[:8]
                if header[:8] == b"\x89PNG\r\n\x1a\n":
                    content_type = "image/png"
                elif header[:2] == b"\xff\xd8":
                    content_type = "image/jpeg"
                elif header[:4] == b"RIFF" and img_resp.content[8:12] == b"WEBP":
                    content_type = "image/webp"
                elif header[:6] in (b"GIF87a", b"GIF89a"):
                    content_type = "image/gif"
                else:
                    content_type = "image/jpeg"  # safe fallback

            # Anthropic limit: 5MB image, 8000px max dimension
            # Downscale large images (e.g. Ultra mode) to stay within limits
            img_data = img_resp.content
            MAX_BYTES = 4_500_000  # stay under 5MB with margin
            MAX_DIM = 8000
            img = Image.open(io.BytesIO(img_data))
            w, h = img.size
            needs_resize = len(img_data) > MAX_BYTES or max(w, h) > MAX_DIM
            if needs_resize:
                # Scale down to fit within limits
                scale = min(MAX_DIM / max(w, h), 1.0)
                if scale < 1.0:
                    img = img.resize(
                        (int(w * scale), int(h * scale)), Image.LANCZOS
                    )
                # Re-encode as JPEG (smaller than PNG)
                buf = io.BytesIO()
                rgb = img.convert("RGB") if img.mode != "RGB" else img
                quality = 85
                rgb.save(buf, format="JPEG", quality=quality)
                while buf.tell() > MAX_BYTES and quality > 40:
                    buf = io.BytesIO()
                    quality -= 10
                    rgb.save(buf, format="JPEG", quality=quality)
                img_data = buf.getvalue()
                content_type = "image/jpeg"

            img_b64 = base64.b64encode(img_data).decode("ascii")

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
1. Title: 50-80 characters ideal. Front-load the primary keyword. Use " | " as separator (max 2). SK must be FIRST.
2. Tags: EXACTLY 13 tags. Each max 20 characters. Multi-word preferred. Must cover diverse buyer intents — NOT all product-type synonyms.
3. Description: SK in FIRST sentence within first 160 chars. Min 500 chars total. Weave 5-8 tag keywords naturally.
4. Superstar keyword (SK): 2-4 words, under 20 characters, specific to this poster. Think like a buyer searching Etsy.

PRODUCT INFO:
- Type: Wall art poster print
- Paper: Museum-quality matte paper (250 gsm / 110 lb)
- Ink: Vibrant, fade-resistant archival inks
- Sizes: {sizes_short} inches
- Frame: Not included
- Brand: DovShopDesign

IMPORTANT: ONLY list the sizes shown above. Do NOT add any other sizes.

DESCRIPTION FORMAT (follow exactly):

Paragraph 1 — HOOK (SK in first sentence, first 160 chars):
Describe exactly what the poster depicts — subject, colors, composition, mood. Be vivid and specific. This is the Google snippet.

Paragraph 2 — VALUE:
Who this is for, what rooms and styles it complements. Naturally include 3-4 tag keywords.

Paragraph 3 — STORY:
The artistic angle — technique, inspiration, what makes this piece unique. Weave in 2-3 more tag keywords naturally.

♥ PERFECT FOR:
• [Specific room + style combo]
• [Gift scenario with recipient]
• [Mood/atmosphere goal]
• [Interior design context]

🖼 PRINT DETAILS:
• Museum-quality matte paper (250 gsm / 110 lb)
• Vibrant, fade-resistant archival inks
• Available in multiple sizes to fit your space
• Shipped in sturdy protective packaging
• Frame not included

📐 AVAILABLE SIZES:
{sizes_block}

⚠️ PLEASE NOTE:
• This listing is for the POSTER PRINT ONLY — frame is not included
• Please double-check the size you are ordering before purchase
• Need a custom size? Message us and we'll work it out together

🎁 [Gift paragraph — specific recipients and occasions, using tag keywords].

[Relevant emoji] More designs at DovShopDesign — where thoughtful design meets everyday spaces.

TAG STRATEGY — cover these 6 buyer-intent categories:

CORE (2 tags):
1. The SK itself
2. Close synonym or variation of SK

BUYER INTENT (3 tags):
3. Gift angle — "gift for him", "gift for mom", "new home gift"
4. Purchase motivation — "office decor idea", "bedroom makeover"
5. Buyer persona — "art lover gift", "nature lover print"

STYLE / AESTHETIC (3 tags):
6. Visual style — "minimalist japanese", "zen ink wash"
7. Technique or medium look — "watercolor print", "ink drawing art"
8. Aesthetic trend — "japandi decor", "cottagecore art"

ROOM / SPACE (2 tags):
9. Primary room — "bedroom wall decor", "living room art"
10. Secondary room — "office poster", "bathroom print"

OCCASION (2 tags):
11. Seasonal or event — "christmas gift idea", "housewarming present"
12. Specific occasion — "anniversary art", "birthday gift art"

LONG-TAIL NICHE (1 tag):
13. Ultra-specific search — exact subject of this poster

RULES:
- Do NOT repeat the same root word in more than 3 tags.
- Do NOT use tags that duplicate the Etsy category (e.g., "poster" or "wall art" alone).
- Each tag must bring NEW search reach.

ADDITIONAL FIELDS:
- Primary color: The DOMINANT color. Must be exactly one of: Beige, Black, Blue, Bronze, Brown, Clear, Copper, Gold, Gray, Green, Orange, Pink, Purple, Rainbow, Red, Rose gold, Silver, White, Yellow
- Secondary color: The SECOND most prominent. Same allowed values. Must be DIFFERENT from primary.
- Alt texts: Generate exactly 5 DIFFERENT alt text descriptions (max 250 chars each):
   - alt_text_1: Describe the poster artwork itself (what it depicts, colors, style)
   - alt_text_2: "[Subject] wall art poster print displayed in a modern living room"
   - alt_text_3: "[Subject] framed art print mockup in a cozy bedroom setting"
   - alt_text_4: "[Subject] poster detail close-up showing print quality and colors"
   - alt_text_5: "[Subject] minimalist wall art in a contemporary home interior"

OUTPUT FORMAT (respond ONLY with this JSON, no other text):
{{"superstar_keyword": "...", "title": "...", "tags": ["tag1", ..., "tag13"], "description": "...", "materials": ["material1", "material2"], "primary_color": "...", "secondary_color": "...", "alt_texts": ["alt1", "alt2", "alt3", "alt4", "alt5"]}}

VALIDATE BEFORE RESPONDING:
- Title 50-80 chars (max 100)
- Each tag <= 20 chars, exactly 13 tags
- SK in title and first 160 chars of description
- Tags cover at least 4 of the 6 buyer-intent categories
- No root word repeated in more than 3 tags
- primary_color and secondary_color from allowed list and different
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
            self._check_response(response)
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
- 50-80 characters ideal
- Start with the main keyword (superstar keyword)
- Max 2 pipe " | " separators (3 sections)
- No repeated words
- Every word must earn its place — no filler
- Format: [Primary Keyword Phrase] | [Secondary Angle] | [Buyer Context]

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
            self._check_response(response)
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

Generate exactly 13 new Etsy tags covering these 6 buyer-intent categories:

CORE (2): SK itself + close synonym
BUYER INTENT (3): gift angle, purchase motivation, buyer persona
STYLE/AESTHETIC (3): visual style, technique/medium, aesthetic trend
ROOM/SPACE (2): primary room, secondary room
OCCASION (2): seasonal event, specific occasion
LONG-TAIL NICHE (1): ultra-specific search for this exact poster

RULES:
- Each tag: max 20 characters, lowercase, multi-word preferred
- Do NOT repeat the same root word in more than 3 tags
- Do NOT use broad category terms alone (e.g., "poster", "wall art")
- Each tag must bring NEW search reach — no overlapping intents
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
            self._check_response(response)
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
- Paragraph 1 — HOOK: SK in first sentence (first 160 chars = Google snippet). Describe exactly what the poster depicts — subject, colors, composition, mood.
- Paragraph 2 — VALUE: Who this is for, what rooms and styles it complements. Weave in 3-4 relevant keywords naturally.
- Paragraph 3 — STORY: The artistic angle — technique, inspiration, what makes this piece unique. Include 2-3 more keywords naturally.
- ♥ PERFECT FOR: 4 keyword-rich bullet points (room+style, gift scenario, mood goal, interior design)
- 🖼 PRINT DETAILS: Museum-quality matte paper (250 gsm / 110 lb), fade-resistant archival inks, multiple sizes, sturdy packaging, frame not included
- 📐 AVAILABLE SIZES: keep ONLY sizes from the original description, do NOT add new sizes
- 🎁 Gift paragraph with occasion keywords
- Last line: shop promo for DovShopDesign

RULES:
- Min 500 characters total
- BANNED: "Transform your space", "Elevate", "Stunning", "Perfect addition", "Captivating", "Add a touch of", "Breathtaking", "Bring nature indoors"
- Be specific about colors, subject, composition, technique, mood

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
            self._check_response(response)
            data = response.json()

        return data["content"][0]["text"].strip()
