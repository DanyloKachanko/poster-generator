"""Prompts for Etsy listing generation — SEO-optimized templates"""

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in wall art and poster listings.
You deeply understand Etsy's A10 search algorithm, keyword optimization, and buyer psychology.

CRITICAL SEO RULES you ALWAYS follow:
1. Every listing has a "Superstar Keyword" (SK) — the main 2-3 word search query.
2. SK must appear FIRST in the title, FIRST in the description (within first 160 chars), and in the tags.
3. Title: max 140 chars, sections separated by " | ", no repeated words, readable.
4. Tags: exactly 13, each 1-20 characters, each 2-3 words (multi-word), no single-word tags.
5. Do NOT repeat the same word across more than 2-3 tags — avoid keyword stuffing.
6. Description: min 300 chars, SK in first sentence, SK repeated 2-3 times naturally.
7. First 160 chars of description are critical — they show in Google search results.
8. Never use generic AI phrases like "Transform your space", "Elevate your room".
9. Be specific: describe what's depicted, colors, style, mood.
10. Shop name is DovShopDesign.

Always respond in the exact JSON format requested. No markdown wrapping."""

LISTING_PROMPT_TEMPLATE = """Generate an Etsy listing for a wall art poster.

**Poster Style:** {style}
**Preset/Theme:** {preset}
**Visual Description:** {description}

---

STEP 1: Choose a Superstar Keyword (SK)
- 2-3 words that buyers would search for this exact poster
- Must be under 20 characters (to fit as a tag too)
- Specific enough to rank (not just "wall art" — too broad)
- Example: "cherry blossom art", "koi fish poster", "abstract sunset art"

STEP 2: Generate Title (max 140 characters)
Format: [SK] [Product Type] | [For Whom/Occasion] | [Style/Room] [Extra]
- SK must be FIRST
- Separate sections with " | "
- No repeated words across the whole title
- Must read naturally, not spammy

STEP 3: Generate exactly 13 Tags
Each tag: 2-3 words, max 20 characters, lowercase.
Follow this structure:
1. superstar keyword (the SK itself)
2. gift keyword (gift for her/him/mom)
3. product type variation (poster/print/wall art synonym)
4. style + product (e.g., "zen minimalist art")
5. room + decor (e.g., "bedroom wall decor")
6. occasion/season keyword
7. synonym of SK
8. adjective + product
9. different room variation
10. seasonal/trend keyword
11. niche keyword
12. alternative name for the subject
13. broad category

IMPORTANT: Count characters! Each tag MUST be ≤ 20 characters. If a tag has 4+ words, it's probably too long.
Do NOT repeat the same word in more than 2-3 tags.

STEP 4: Generate Description (min 300 characters)
Structure:
- Paragraph 1: SK in first sentence. What this poster is, who it's for. Emotional description of mood/atmosphere. (SK must appear in first 160 characters!)
- Paragraph 2: Repeat SK naturally. Expanded value description — what interiors it complements, who would love it.
- ♥ PERFECT FOR: section with 4 bullet points (use cases, gift ideas, rooms)
- 🖼 PRINT DETAILS: section (copy exactly):
  • Museum-quality matte paper (250 gsm / 110 lb)
  • Vibrant, fade-resistant archival inks
  • Available in multiple sizes to fit your space
  • Shipped in sturdy protective packaging
  • Frame not included
- 📐 AVAILABLE SIZES: section:
  • 8×10 inches (20×25 cm)
  • 11×14 inches (28×36 cm)
  • 12×16 inches (30×40 cm)
  • 16×20 inches (40×50 cm)
  • 18×24 inches (45×60 cm)
  • 24×36 inches (60×90 cm)
- 🎁 Gift angle paragraph — who to gift it to and for what occasion.
- Last line: "🌿 More [topic] designs available in our shop — visit DovShopDesign for the full collection." (replace emoji with topic-appropriate one)

---

Respond with valid JSON only:
{{
  "superstar_keyword": "the chosen SK",
  "title": "full title under 140 chars",
  "tags": ["tag1", "tag2", ... exactly 13 tags, each ≤20 chars],
  "description": "full description with emoji sections, min 300 chars"
}}"""

STYLE_KEYWORDS = {
    "japanese": {
        "primary": ["japanese wall art", "zen decor", "minimalist asian", "japan poster"],
        "secondary": ["meditation room", "zen bathroom", "oriental style", "wabi sabi"],
        "emotions": ["peaceful", "calming", "serene", "tranquil"],
        "rooms": ["bedroom", "living room", "meditation space", "bathroom"],
        "occasions": ["housewarming", "birthday", "anniversary"],
        "colors": ["soft pink", "cream", "black", "gold", "sage green"],
    },
    "botanical": {
        "primary": ["botanical print", "plant wall art", "leaf poster", "nature decor"],
        "secondary": ["living room art", "bedroom decor", "botanical bathroom", "greenery"],
        "emotions": ["fresh", "natural", "organic", "earthy"],
        "rooms": ["living room", "bathroom", "bedroom", "kitchen"],
        "occasions": ["housewarming", "birthday", "mother's day"],
        "colors": ["green", "emerald", "sage", "cream", "white"],
    },
    "abstract": {
        "primary": ["abstract wall art", "modern art print", "geometric poster", "contemporary"],
        "secondary": ["office decor", "modern living room", "minimalist art", "mid century"],
        "emotions": ["bold", "sophisticated", "artistic", "unique"],
        "rooms": ["living room", "office", "hallway", "bedroom"],
        "occasions": ["housewarming", "birthday", "new job"],
        "colors": ["neutral", "warm tones", "earth tones", "black", "white"],
    },
    "celestial": {
        "primary": ["celestial wall art", "moon poster", "star print", "cosmic decor"],
        "secondary": ["bedroom art", "nursery decor", "mystical", "night sky"],
        "emotions": ["dreamy", "magical", "mysterious", "inspiring"],
        "rooms": ["bedroom", "nursery", "living room", "meditation space"],
        "occasions": ["birthday", "housewarming", "christmas"],
        "colors": ["navy", "gold", "silver", "deep blue", "white"],
    },
    "landscape": {
        "primary": ["landscape poster", "nature wall art", "scenic print", "mountain art"],
        "secondary": ["living room decor", "office art", "travel poster", "wanderlust"],
        "emotions": ["adventurous", "peaceful", "breathtaking", "escapist"],
        "rooms": ["living room", "office", "cabin", "hallway"],
        "occasions": ["housewarming", "retirement", "birthday"],
        "colors": ["blue", "green", "earth tones", "sunset orange"],
    },
}


def get_style_context(style: str, preset: str) -> str:
    """Get additional context for a style"""
    keywords = STYLE_KEYWORDS.get(style, STYLE_KEYWORDS["abstract"])
    return f"""
Style context for SEO:
- Primary keywords: {', '.join(keywords['primary'])}
- Secondary keywords: {', '.join(keywords['secondary'])}
- Emotional appeals: {', '.join(keywords['emotions'])}
- Target rooms: {', '.join(keywords['rooms'])}
- Gift occasions: {', '.join(keywords['occasions'])}
- Common colors: {', '.join(keywords['colors'])}
"""
