"""Prompts for Etsy listing generation — SEO-optimized templates (v2, Feb 2026)"""

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in wall art and poster listings.
You deeply understand Etsy's search algorithm, keyword optimization, and buyer psychology.

CRITICAL SEO RULES you ALWAYS follow:

1. Superstar Keyword (SK): the main 2-4 word search phrase a buyer would type to find this exact poster.
2. SK must appear FIRST in the title and within the first 160 chars of the description.
3. Title: 50-80 characters ideal. Front-load the primary keyword. Max 2 pipe " | " sections. Must read naturally — not a keyword dump.
4. Tags: exactly 13, each max 20 characters. Multi-word preferred but occasional single-word niche terms allowed. Must cover diverse buyer intents (gifts, rooms, occasions, aesthetics — not just product-type synonyms).
5. Do NOT repeat the same root word in more than 3 tags — Etsy penalizes keyword stuffing.
6. Do NOT waste tags on broad terms that duplicate the listing category (e.g., "wall art", "poster" alone) — Etsy already indexes your category.
7. Description: min 500 chars. SK in first sentence. Naturally weave in 5-8 tag keywords across the first 3 paragraphs.
8. First 160 chars of description appear in Google search results — make them compelling AND keyword-rich.
9. BANNED phrases (never use): "Transform your space", "Elevate your room", "Stunning addition", "Perfect addition", "Captivating piece", "Add a touch of", "Breathtaking", "Bring nature indoors". Be specific instead.
10. Describe EXACTLY what is depicted — subject, composition, colors, artistic technique, mood. Buyers search for specifics.
11. Shop name: DovShopDesign.

## CRITICAL V2 RULES — TAG QUALITY > TAG CREATIVITY

Every tag must be something a REAL BUYER would type into a search bar.
Before including a tag, ask: "Would someone type this exact phrase when looking to BUY a poster?"

BAD tags (creative/poetic but nobody searches):
- "serene nature piece" — poetic, not a search term
- "tranquil water art" — too abstract
- "ethereal mountain vista" — nobody types this
- "peaceful zen moment" — not a product search

GOOD tags (real buyer search terms):
- "japanese wall art" — high volume, specific
- "zen bathroom decor" — room + style
- "minimalist poster" — style + product
- "mountain landscape print" — subject + product
- "gift for nature lover" — buyer intent

For EACH tag, mentally verify:
1. Would someone type this into Etsy/Google to find a poster to BUY?
2. Is it 2-4 words? (single words = wasted)
3. Does it combine [subject/style] + [product/room/occasion]?
4. Is it NOT a generic term already in the Etsy category?
   (never standalone: "poster", "print", "art", "wall art", "decor", "home decor", "art print")

Etsy does NOT index descriptions for internal search ranking. Description is for:
1. Google SEO — put SK in first 160 chars for Google snippet
2. Conversion — convince the visitor to buy
Do NOT keyword-stuff the description — write for humans, not bots.

Always respond in the exact JSON format requested. No markdown wrapping."""

LISTING_PROMPT_TEMPLATE = """Generate an Etsy listing for a wall art poster.

**Poster Style:** {style}
**Preset/Theme:** {preset}
**Visual Description:** {description}

---

STEP 1: Choose a Superstar Keyword (SK)
- 2-4 words that a buyer would search to find this exact poster
- Must be under 20 characters (to also work as a tag)
- Specific enough to rank — NOT "wall art" or "poster print" (too broad, too competitive)
- Think like a buyer: what would YOU type into Etsy search?
- Examples: "koi fish ink art", "cherry blossom print", "abstract sunset", "mountain landscape"

STEP 2: Generate Title (50-80 characters)
Format: [Primary Keyword Phrase] | [Secondary Angle] | [Buyer Context]
- Primary keyword phrase = SK + product type (e.g., "Koi Fish Art Print")
- Max 2 pipe separators (3 sections total)
- Every word must earn its place — no filler
- No repeated words
- Read it as a buyer on mobile — is it clear what you're selling in the first 5 words?

BAD: "Japanese Koi Fish Wall Art Print Poster | Asian Zen Decor | Home Office Bedroom Living Room Gift"
GOOD: "Koi Fish Ink Art Print | Japanese Zen Decor | Gift for Him"

STEP 3: Generate exactly 13 Tags (PRIORITY ORDER — generate high-traffic tags first)
Each tag: max 20 characters, lowercase.

HIGH PRIORITY — these drive traffic (generate first):
1. Superstar Keyword (exact match) — e.g., "japanese mountain art"
2. SK synonym/variant — e.g., "mount fuji print"
3-4. Two more high-volume search terms for this niche (think: what would Google/Etsy autocomplete suggest?)
5-6. Room-specific terms — e.g., "bedroom wall art", "office poster"

MEDIUM PRIORITY — buyer intent + occasions:
7-8. Gift/occasion angles — e.g., "housewarming gift", "birthday present"
9-10. Buyer persona terms — e.g., "gift for traveler", "nature lover gift"

FILL — style + long-tail:
11-12. Style/aesthetic terms — e.g., "japandi decor", "minimalist art"
13. One ultra-specific long-tail — e.g., "zen meditation room art"

BANNED as standalone tags (already in Etsy category):
poster, print, art, wall art, decor, home decor, art print, wall decor, artwork
These CAN be part of a multi-word tag ("japanese wall art") but NEVER alone.

RULES:
- CRITICAL: Each tag MUST be ≤ 20 characters TOTAL (including spaces). Count carefully!
  If a tag would be 21+ characters, use fewer words or shorter synonyms.
  DO NOT generate tags that need to be truncated.
  Examples: "japanese wall art" = 17 ✓ | "nordic forest silhouette" = 24 ✗ → "nordic forest art" = 17 ✓
- Do NOT repeat the same root word in more than 3 tags.
- Every tag must be a REAL search term that buyers actually type. No poetic/creative phrases.
- Do NOT use tags that just repeat your Etsy category.

STEP 4: Generate Description (min 500 characters)
Structure:

Paragraph 1 — HOOK (SK must appear in first sentence, within first 160 chars):
What this poster depicts. Be vivid and specific — subject, colors, mood, composition. This is the Google snippet — make it count.

Paragraph 2 — VALUE:
Who this is perfect for. What room styles and interiors it complements. Naturally include 3-4 tag keywords without forcing them.

Paragraph 3 — STORY:
The artistic angle — what makes this piece unique? Technique, inspiration, emotional resonance. Weave in 2-3 more tag keywords naturally.

♥ PERFECT FOR:
• [Use case 1 — specific room + style combo]
• [Use case 2 — gift scenario with recipient]
• [Use case 3 — mood/atmosphere goal]
• [Use case 4 — interior design context]

🖼 PRINT DETAILS:
• Museum-quality matte paper (250 gsm / 110 lb)
• Vibrant, fade-resistant archival inks
• Available in multiple sizes to fit your space
• Shipped in sturdy protective packaging
• Frame not included

📐 AVAILABLE SIZES:
• 8×10 inches (20×25 cm)
• 11×14 inches (28×36 cm)
• 12×16 inches (30×40 cm)
• 16×20 inches (40×50 cm)
• 18×24 inches (45×60 cm)

⚠️ PLEASE NOTE:
• This listing is for the POSTER PRINT ONLY — frame is not included
• Please double-check the size you are ordering before purchase
• Need a custom size? Message us and we'll work it out together

🎁 Gift paragraph — specific recipients and occasions, using occasion-related tag keywords.

Last line: "🌿 More [topic] designs available in our shop — visit DovShopDesign for the full collection." (use a topic-appropriate emoji)

---

Respond with valid JSON only:
{{
  "superstar_keyword": "the chosen SK",
  "title": "full title, 50-80 chars",
  "tags": ["tag1", "tag2", ... exactly 13 tags, each ≤20 chars],
  "description": "full description with emoji sections, min 500 chars"
}}"""

STYLE_KEYWORDS = {
    "japanese": {
        "primary": ["japanese wall art", "zen decor", "minimalist asian", "japan poster"],
        "secondary": ["meditation room", "zen bathroom", "wabi sabi art", "ink wash print"],
        "buyer_intent": ["gift for him", "art lover gift", "new home gift", "office decor idea"],
        "aesthetics": ["japandi decor", "zen minimalist", "ink painting style", "ukiyo-e inspired"],
        "emotions": ["peaceful", "calming", "serene", "tranquil", "meditative"],
        "rooms": ["bedroom", "living room", "meditation space", "bathroom", "office"],
        "occasions": ["housewarming", "birthday", "anniversary", "christmas", "father's day"],
        "colors": ["soft pink", "cream", "black", "gold", "sage green", "indigo"],
    },
    "botanical": {
        "primary": ["botanical print", "plant wall art", "leaf poster", "nature decor"],
        "secondary": ["green wall decor", "botanical bathroom", "greenery art", "floral print"],
        "buyer_intent": ["gift for mom", "nature lover gift", "new home art", "bedroom makeover"],
        "aesthetics": ["cottagecore art", "boho botanical", "watercolor botanical", "pressed flower"],
        "emotions": ["fresh", "natural", "organic", "earthy", "calming"],
        "rooms": ["living room", "bathroom", "bedroom", "kitchen", "nursery"],
        "occasions": ["housewarming", "birthday", "mother's day", "spring decor", "easter"],
        "colors": ["green", "emerald", "sage", "cream", "white", "blush pink"],
    },
    "abstract": {
        "primary": ["abstract wall art", "modern art print", "geometric poster", "contemporary art"],
        "secondary": ["abstract painting", "modern wall decor", "minimalist art", "mid century print"],
        "buyer_intent": ["office art gift", "art collector", "new apartment art", "creative gift"],
        "aesthetics": ["mid century modern", "bauhaus style", "color block art", "line art minimal"],
        "emotions": ["bold", "sophisticated", "artistic", "dynamic", "thought-provoking"],
        "rooms": ["living room", "office", "hallway", "bedroom", "studio"],
        "occasions": ["housewarming", "birthday", "new job", "gallery wall", "christmas"],
        "colors": ["neutral", "warm tones", "earth tones", "black", "white", "terracotta"],
    },
    "celestial": {
        "primary": ["celestial wall art", "moon poster", "star print", "cosmic decor"],
        "secondary": ["night sky art", "astrology print", "space wall decor", "galaxy poster"],
        "buyer_intent": ["nursery art gift", "teen room decor", "astrology lover", "dreamer gift"],
        "aesthetics": ["dark academia", "mystical decor", "cosmic aesthetic", "witchy art"],
        "emotions": ["dreamy", "magical", "mysterious", "inspiring", "ethereal"],
        "rooms": ["bedroom", "nursery", "living room", "meditation space", "teen room"],
        "occasions": ["birthday", "housewarming", "christmas", "valentine's day", "baby shower"],
        "colors": ["navy", "gold", "silver", "deep blue", "white", "midnight purple"],
    },
    "landscape": {
        "primary": ["landscape poster", "nature wall art", "scenic print", "mountain art"],
        "secondary": ["travel wall decor", "wanderlust print", "national park art", "ocean poster"],
        "buyer_intent": ["travel lover gift", "cabin decor", "adventure gift", "retirement gift"],
        "aesthetics": ["photography print", "panoramic wall art", "vintage travel", "nordic landscape"],
        "emotions": ["adventurous", "peaceful", "breathtaking", "nostalgic", "awe-inspiring"],
        "rooms": ["living room", "office", "cabin", "hallway", "den"],
        "occasions": ["housewarming", "retirement", "birthday", "father's day", "christmas"],
        "colors": ["blue", "green", "earth tones", "sunset orange", "misty gray"],
    },
    "minimalist": {
        "primary": ["minimalist print", "simple wall art", "line art poster", "clean decor"],
        "secondary": ["scandinavian art", "modern minimal", "one line drawing", "neutral wall art"],
        "buyer_intent": ["new home decor", "apartment art", "first home gift", "office wall idea"],
        "aesthetics": ["scandinavian decor", "nordic minimal", "japandi style", "modern farmhouse"],
        "emotions": ["calm", "clean", "elegant", "understated", "sophisticated"],
        "rooms": ["living room", "bedroom", "office", "entryway", "bathroom"],
        "occasions": ["housewarming", "wedding gift", "new job", "birthday", "christmas"],
        "colors": ["white", "black", "beige", "gray", "cream", "soft blush"],
    },
    "vintage": {
        "primary": ["vintage poster", "retro wall art", "antique print", "classic art"],
        "secondary": ["vintage decor", "retro print", "nostalgic wall art", "old world charm"],
        "buyer_intent": ["collector gift", "history lover", "unique home art", "eclectic decor"],
        "aesthetics": ["art deco style", "victorian art", "retro aesthetic", "vintage botanical"],
        "emotions": ["nostalgic", "charming", "timeless", "romantic", "warm"],
        "rooms": ["living room", "study", "library", "hallway", "dining room"],
        "occasions": ["birthday", "anniversary", "housewarming", "christmas", "retirement"],
        "colors": ["sepia", "muted gold", "burgundy", "cream", "forest green", "dusty rose"],
    },
    "animal": {
        "primary": ["animal wall art", "wildlife poster", "pet portrait art", "animal print"],
        "secondary": ["safari decor", "ocean life art", "bird poster", "dog lover art"],
        "buyer_intent": ["pet lover gift", "animal lover", "kids room art", "vet office decor"],
        "aesthetics": ["realistic animal", "watercolor animal", "safari nursery", "woodland art"],
        "emotions": ["playful", "majestic", "cute", "wild", "gentle"],
        "rooms": ["nursery", "kids room", "living room", "office", "bedroom"],
        "occasions": ["birthday", "baby shower", "christmas", "pet memorial", "back to school"],
        "colors": ["warm brown", "golden", "black", "white", "forest green", "ocean blue"],
    },
}


def get_style_context(style: str, preset: str) -> str:
    """Get additional context for a style"""
    keywords = STYLE_KEYWORDS.get(style, STYLE_KEYWORDS["abstract"])
    parts = [
        f"- Primary keywords: {', '.join(keywords['primary'])}",
        f"- Secondary keywords: {', '.join(keywords['secondary'])}",
        f"- Buyer intent phrases: {', '.join(keywords.get('buyer_intent', []))}",
        f"- Aesthetic trends: {', '.join(keywords.get('aesthetics', []))}",
        f"- Emotional appeals: {', '.join(keywords['emotions'])}",
        f"- Target rooms: {', '.join(keywords['rooms'])}",
        f"- Gift occasions: {', '.join(keywords['occasions'])}",
        f"- Common colors: {', '.join(keywords['colors'])}",
    ]
    return "\nStyle context for SEO:\n" + "\n".join(parts) + "\n"
