"""Pinterest pin content generator — Claude-powered, Pinterest SEO optimized."""

import json
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

PINTEREST_PIN_PROMPT = """You are a Pinterest SEO expert for wall art and home decor.

Generate a Pinterest pin title and description for this poster listing.

POSTER INFO:
- Etsy title: {etsy_title}
- Etsy tags: {etsy_tags}
- Collection/niche: {niche}
- Etsy listing URL: {etsy_url}

PINTEREST TITLE RULES (max 100 chars):
- Short, descriptive, buyer-focused
- Include primary keyword naturally
- More emotional/aspirational than Etsy titles
- Use adjectives Pinterest loves: stunning, beautiful, gorgeous, cozy, dreamy
- Example: "Stunning Koi Fish Zen Art for a Peaceful Living Room"

PINTEREST DESCRIPTION RULES (max 500 chars):
- First sentence: hook with keyword
- Mention the room/occasion it's perfect for
- Include call-to-action: "Shop now on Etsy" or "Tap to shop"
- End with: "Browse more at dovshop.org"
- Include 5-8 hashtags at the end
- Hashtags: #WallArt #HomeDecor #[NicheSpecific] #[StyleSpecific] #PosterPrint
- Tone: inspirational, aspirational, warm

ALT TEXT RULES (max 500 chars):
- Describe the image for accessibility
- Include what the poster depicts and style
- Simple, factual, no marketing language

Return JSON only, no markdown:
{{"title": "...", "description": "...", "alt_text": "..."}}
"""


class PinterestPinGenerator:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def generate_pin_content(
        self,
        etsy_title: str,
        etsy_tags: list,
        niche: str,
        etsy_url: str,
        variant: int = 1,
    ) -> dict:
        """Generate Pinterest-optimized title, description, alt_text for a pin."""
        prompt = PINTEREST_PIN_PROMPT.format(
            etsy_title=etsy_title,
            etsy_tags=", ".join(etsy_tags) if etsy_tags else "none",
            niche=niche or "wall art",
            etsy_url=etsy_url,
        )

        if variant > 1:
            prompt += (
                f"\n\nThis is variant #{variant}. Make the title and description "
                "DIFFERENT from previous versions — use different keywords, "
                "different angle, different room suggestion."
            )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]

            try:
                result = json.loads(text, strict=False)
            except json.JSONDecodeError:
                match = re.search(r"\{[^}]+\}", text, re.DOTALL)
                if match:
                    result = json.loads(match.group(), strict=False)
                else:
                    raise ValueError(f"Could not parse pin content: {text}")

            return {
                "title": result.get("title", etsy_title)[:100],
                "description": result.get("description", "")[:500],
                "alt_text": result.get("alt_text", "")[:500],
            }
