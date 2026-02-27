"""Auto-categorization of products for DovShop sync.

Matches product tags and style against keyword dictionaries
to determine category slugs (style + room).
"""

from prompts import STYLE_KEYWORDS

# Style category keywords — slug → list of trigger words
STYLE_CATEGORIES = {
    "japanese": [
        "japanese", "zen", "torii", "koi", "bamboo", "cherry blossom",
        "wabi sabi", "asian", "sakura", "japan", "fuji", "bonsai",
    ],
    "botanical": [
        "botanical", "plant", "leaf", "fern", "eucalyptus", "monstera",
        "wildflower", "palm", "succulent", "olive", "greenery", "floral",
        "flower", "herb", "dried flower",
    ],
    "abstract": [
        "abstract", "geometric", "modern art", "contemporary",
        "minimalist art", "mid century", "marble", "line art",
        "wave", "flowing", "gradient",
    ],
    "celestial": [
        "celestial", "moon", "star", "cosmic", "night sky",
        "constellation", "eclipse", "nebula", "planet", "galaxy",
        "aurora",
    ],
    "landscape": [
        "landscape", "mountain", "ocean", "forest", "desert",
        "lake", "nature", "scenic", "beach", "sunset", "sunrise",
        "waterfall", "valley", "cliff", "field", "dune", "mist",
        "tuscany", "rolling hills",
    ],
}

# Room category keywords — slug → list of trigger words
ROOM_CATEGORIES = {
    "living-room": ["living room", "living space", "lounge"],
    "bedroom": ["bedroom", "bed room", "bedside"],
    "office": ["office", "workspace", "desk", "study"],
    "bathroom": ["bathroom", "bath room", "zen bathroom"],
    "nursery": ["nursery", "kids room", "children", "baby"],
    "kitchen": ["kitchen", "dining"],
    "hallway": ["hallway", "entryway", "corridor"],
    "gift-ideas": [
        "gift", "housewarming", "birthday", "anniversary",
        "christmas", "mother's day", "valentine", "retirement",
    ],
    "meditation-space": ["meditation", "yoga", "mindful", "zen space"],
}

# Map STYLE_KEYWORDS room names → category slugs
_ROOM_SLUG_MAP = {
    "bedroom": "bedroom",
    "living room": "living-room",
    "office": "office",
    "bathroom": "bathroom",
    "nursery": "nursery",
    "kitchen": "kitchen",
    "hallway": "hallway",
    "meditation space": "meditation-space",
    "cabin": "living-room",
}


def categorize_product(tags: list[str] | None, style: str | None = None) -> list[str]:
    """Determine category slugs for a product from its tags and style.

    Returns sorted list of unique category slugs, e.g.:
    ["bedroom", "gift-ideas", "japanese", "living-room"]
    """
    categories: set[str] = set()
    tags_lower = [t.lower() for t in (tags or [])]
    tags_text = " ".join(tags_lower)

    # 1. Style from generation metadata (highest confidence)
    if style and style in STYLE_CATEGORIES:
        categories.add(style)

    # 2. Scan tags for style keywords
    for slug, keywords in STYLE_CATEGORIES.items():
        for kw in keywords:
            if kw in tags_text:
                categories.add(slug)
                break

    # 3. Scan tags for room keywords
    for slug, keywords in ROOM_CATEGORIES.items():
        for kw in keywords:
            if kw in tags_text:
                categories.add(slug)
                break

    # 4. Use STYLE_KEYWORDS default rooms as fallback
    if style and style in STYLE_KEYWORDS:
        sk = STYLE_KEYWORDS[style]
        for room in sk.get("rooms", []):
            mapped = _ROOM_SLUG_MAP.get(room)
            if mapped:
                categories.add(mapped)
        if sk.get("occasions"):
            categories.add("gift-ideas")

    return sorted(categories)


# DovShop collection keywords — slug → list of trigger words (checked against name + tags)
COLLECTION_KEYWORDS = {
    "botanical-garden": [
        "botanical", "eucalyptus", "fern", "monstera", "wildflower", "olive branch",
        "palm leaf", "tropical", "cherry blossom", "sakura", "succulent", "dried flower",
        "plant art", "leaf art", "dark botanical",
    ],
    "japanese-zen": [
        "japanese", "torii", "bamboo", "koi", "ukiyo", "zen art", "zen mist",
        "mount fuji", "japandi", "asian ink", "asian wall", "woodblock",
        "cat moon", "black cat cherry", "chinese horse",
    ],
    "cosmic-dreams": [
        "nebula", "galaxy", "aurora", "northern lights", "celestial", "lunar eclipse",
        "solar system", "constellation", "zodiac", "night sky", "starry night",
        "sun moon", "moon phases", "cosmic", "space poster", "astronomy",
    ],
    "nature-landscapes": [
        "landscape", "mountain", "desert", "wheat field", "misty forest",
        "misty mountain", "ocean sunset", "lake", "tuscany", "countryside",
        "dunes", "sunrise", "golden hour", "beach wall", "library", "dark academia",
    ],
    "modern-abstract": [
        "abstract", "geometric", "gradient", "wave art", "stripes", "mandala",
        "modern arch", "marble", "flowing lines", "diagonal lines", "circle art",
        "mid century", "valentine", "fire horse", "flaming stallion",
    ],
    "neon-nights": [
        "cyberpunk", "vaporwave", "neon geometric", "neon city", "neon palm",
        "synthwave", "retro neon",
    ],
}


def get_collection_slug(name: str, tags: list[str] | None = None) -> str | None:
    """Determine the DovShop collection slug for a product.

    Matches product name and tags against keyword dictionaries.
    Returns the first matching collection slug, or None.
    """
    search_text = name.lower()
    if tags:
        search_text += " " + " ".join(t.lower() for t in tags)

    for slug, keywords in COLLECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in search_text:
                return slug
    return None
