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

    def to_dict(self):
        return {
            "title": self.title,
            "tags": self.tags,
            "description": self.description,
            "tags_string": ", ".join(self.tags),
        }


class ListingGenerator:
    """Generate Etsy listing text using Claude API"""

    BASE_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-3-5-haiku-20241022"

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
            "max_tokens": 1024,
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
                timeout=30.0,
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

        title = listing_data["title"][:140]
        tags = [tag[:20].lower().strip() for tag in listing_data["tags"][:13]]
        description = listing_data["description"][:2000]

        return EtsyListing(
            title=title,
            tags=tags,
            description=description,
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

Generate 1 alternative title that:
- Is under 140 characters
- Uses different keyword order
- Maintains SEO value
- Sounds natural

Respond with ONLY the new title, no quotes, no explanation."""

        payload = {
            "model": self.MODEL,
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=15.0,
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

Generate exactly 13 new Etsy tags that:
- Each tag is max 20 characters
- Mix specific and broad keywords
- Include style, room types, gift occasions
- Lowercase, no hashtags
- Different from current tags where possible
- Optimized for Etsy SEO

Respond with ONLY a comma-separated list of 13 tags, no quotes, no explanation."""

        payload = {
            "model": self.MODEL,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=15.0,
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

Rules:
- 500-800 characters
- Mention museum-quality paper
- Include room suggestions
- Make it compelling but not pushy

Respond with ONLY the new description, no quotes."""

        payload = {
            "model": self.MODEL,
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

        return data["content"][0]["text"].strip()[:2000]
