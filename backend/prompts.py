"""Prompts for Etsy listing generation"""

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in wall art and home decor.
You write compelling, search-optimized listings that convert browsers into buyers.
You understand Etsy's algorithm and buyer psychology.
Always respond in the exact JSON format requested."""

LISTING_PROMPT_TEMPLATE = """Generate an Etsy listing for a wall art poster with these details:

**Poster Style:** {style}
**Preset/Theme:** {preset}
**Visual Description:** {description}
**Target Audience:** US homeowners interested in home decor, minimalist design lovers

Generate a complete Etsy listing in JSON format:

{{
  "title": "SEO-optimized title, max 140 characters. Front-load main keywords. Include: style + subject + 'Wall Art' or 'Poster' + room suggestion",
  "tags": ["exactly 13 tags", "each max 20 chars", "mix of specific and broad", "include style", "include room types", "include gift occasions"],
  "description": "Compelling description 500-800 characters. Structure: 1) Hook about the art 2) What makes it special 3) Room suggestions 4) Print quality mention 5) Gift idea. Use line breaks. No emojis."
}}

IMPORTANT RULES:
- Title: Must be under 140 characters, keyword-rich, readable
- Tags: Exactly 13 tags, each under 20 characters, no hashtags, lowercase
- Description: 500-800 characters, persuasive but not pushy, mention "museum-quality" paper
- Focus on emotional benefits and room transformation
- Include seasonal angles where relevant (gift, new home, refresh)

Respond ONLY with valid JSON, no markdown, no explanation."""

STYLE_KEYWORDS = {
    "japanese": {
        "primary": ["japanese wall art", "zen decor", "minimalist asian", "japan poster"],
        "secondary": ["meditation room", "zen bathroom", "oriental style", "wabi sabi"],
        "emotions": ["peaceful", "calming", "serene", "tranquil"],
    },
    "botanical": {
        "primary": ["botanical print", "plant wall art", "leaf poster", "nature decor"],
        "secondary": ["living room art", "bedroom decor", "botanical bathroom", "greenery"],
        "emotions": ["fresh", "natural", "organic", "earthy"],
    },
    "abstract": {
        "primary": ["abstract wall art", "modern art print", "geometric poster", "contemporary"],
        "secondary": ["office decor", "modern living room", "minimalist art", "mid century"],
        "emotions": ["bold", "sophisticated", "artistic", "unique"],
    },
    "celestial": {
        "primary": ["celestial wall art", "moon poster", "star print", "cosmic decor"],
        "secondary": ["bedroom art", "nursery decor", "mystical", "night sky"],
        "emotions": ["dreamy", "magical", "mysterious", "inspiring"],
    },
    "landscape": {
        "primary": ["landscape poster", "nature wall art", "scenic print", "mountain art"],
        "secondary": ["living room decor", "office art", "travel poster", "wanderlust"],
        "emotions": ["adventurous", "peaceful", "breathtaking", "escapist"],
    },
}


def get_style_context(style: str, preset: str) -> str:
    """Get additional context for a style"""
    keywords = STYLE_KEYWORDS.get(style, STYLE_KEYWORDS["abstract"])
    return f"""
Style keywords to consider:
- Primary: {', '.join(keywords['primary'])}
- Secondary: {', '.join(keywords['secondary'])}
- Emotional appeals: {', '.join(keywords['emotions'])}
"""
