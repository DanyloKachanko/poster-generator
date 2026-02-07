"""
Poster presets — ready-made prompts organized by category.
Each preset includes prompt, negative prompt, Etsy tags, difficulty, and trending score.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class PosterPreset:
    id: str
    name: str
    category: str
    prompt: str
    negative_prompt: str
    tags: List[str]
    difficulty: str        # easy, medium, hard
    trending_score: int    # 1-10


POSTER_PRESETS = {
    # ── JAPANESE / ZEN ──────────────────────────────────────────
    "japanese_cherry_blossom": PosterPreset(
        id="japanese_cherry_blossom",
        name="Cherry Blossom Branch",
        category="japanese",
        prompt="Minimalist cherry blossom branch with delicate pink petals falling, soft watercolor style, Japanese ink painting influence, white background with subtle texture, peaceful zen aesthetic, sakura flowers in bloom, elegant botanical art",
        negative_prompt="text, watermark, busy background, photorealistic, harsh colors, cluttered",
        tags=["cherry blossom art", "japanese wall art", "sakura print", "minimalist flower", "zen decor", "botanical print", "pink wall art", "asian art", "spring decor", "bedroom art", "peaceful art", "watercolor print", "floral poster"],
        difficulty="easy",
        trending_score=9,
    ),
    "japanese_zen_garden": PosterPreset(
        id="japanese_zen_garden",
        name="Zen Garden",
        category="japanese",
        prompt="Minimalist Japanese zen garden with perfectly raked sand patterns, single moss-covered stone, morning mist, soft grey and green tones, peaceful meditation atmosphere, wabi-sabi aesthetic, negative space composition",
        negative_prompt="text, watermark, people, bright colors, complex patterns, cluttered",
        tags=["zen garden art", "japanese decor", "minimalist poster", "meditation art", "peaceful wall art", "zen home decor", "calming art", "sand garden", "japanese aesthetic", "spa decor", "bathroom art", "neutral wall art", "nature print"],
        difficulty="medium",
        trending_score=8,
    ),
    "japanese_wave": PosterPreset(
        id="japanese_wave",
        name="Japanese Wave",
        category="japanese",
        prompt="Stylized ocean wave in Japanese ukiyo-e style inspired by Hokusai, deep blue and white colors, dramatic foam patterns, minimalist modern interpretation, clean lines, powerful yet serene ocean art",
        negative_prompt="text, watermark, Mount Fuji, boats, too detailed, photorealistic",
        tags=["japanese wave art", "ocean wall art", "hokusai style", "blue wall art", "nautical decor", "beach house art", "japanese poster", "wave print", "coastal decor", "bathroom art", "modern japanese", "ukiyo-e style", "sea art"],
        difficulty="medium",
        trending_score=9,
    ),
    "japanese_bamboo": PosterPreset(
        id="japanese_bamboo",
        name="Bamboo Forest",
        category="japanese",
        prompt="Serene bamboo grove with tall green stalks reaching upward, soft diffused light filtering through, minimalist composition, peaceful forest atmosphere, Japanese sumi-e ink painting influence, zen tranquility",
        negative_prompt="text, watermark, people, animals, busy composition, bright harsh colors",
        tags=["bamboo art", "japanese wall art", "forest print", "green wall art", "zen decor", "nature poster", "minimalist art", "asian decor", "botanical print", "peaceful art", "living room art", "spa decor", "plant art"],
        difficulty="easy",
        trending_score=7,
    ),
    "japanese_torii": PosterPreset(
        id="japanese_torii",
        name="Torii Gate",
        category="japanese",
        prompt="Solitary red torii gate standing in misty landscape, minimalist Japanese aesthetic, soft morning fog, traditional vermillion color against muted grey background, spiritual peaceful atmosphere, negative space composition",
        negative_prompt="text, watermark, tourists, modern buildings, busy background, photorealistic",
        tags=["torii gate art", "japanese poster", "zen wall art", "red wall art", "spiritual decor", "asian art", "minimalist print", "japan travel art", "shrine art", "meditation room", "peaceful poster", "fog art", "gate print"],
        difficulty="medium",
        trending_score=7,
    ),
    "japanese_koi": PosterPreset(
        id="japanese_koi",
        name="Koi Fish",
        category="japanese",
        prompt="Elegant koi fish swimming in calm pond, Japanese watercolor style, orange and white fish with flowing fins, subtle water ripples, minimalist zen composition, peaceful contemplative mood, traditional asian art influence",
        negative_prompt="text, watermark, too many fish, cartoonish, harsh colors, cluttered",
        tags=["koi fish art", "japanese wall art", "fish poster", "orange wall art", "zen decor", "pond art", "asian print", "water art", "peaceful poster", "living room art", "feng shui art", "good luck art", "nature print"],
        difficulty="medium",
        trending_score=6,
    ),

    # ── BOTANICAL / NATURE ──────────────────────────────────────
    "botanical_monstera": PosterPreset(
        id="botanical_monstera",
        name="Monstera Leaf",
        category="botanical",
        prompt="Single large monstera deliciosa leaf, detailed botanical illustration style, deep green color with natural holes, white or cream background, modern minimalist plant art, clean sharp lines, tropical elegance",
        negative_prompt="text, watermark, multiple leaves, pot, busy background, cartoonish",
        tags=["monstera art", "botanical print", "plant poster", "tropical decor", "green wall art", "leaf print", "minimalist plant", "living room art", "modern botanical", "nature poster", "jungle decor", "plant lover gift", "greenery art"],
        difficulty="easy",
        trending_score=9,
    ),
    "botanical_eucalyptus": PosterPreset(
        id="botanical_eucalyptus",
        name="Eucalyptus Branch",
        category="botanical",
        prompt="Delicate eucalyptus branch with silvery-green leaves, watercolor style, soft muted sage green tones, white background, botanical illustration, elegant minimal composition, dried flower aesthetic",
        negative_prompt="text, watermark, bright colors, photorealistic, cluttered, harsh shadows",
        tags=["eucalyptus art", "botanical print", "sage green decor", "plant poster", "watercolor art", "minimalist botanical", "greenery print", "bedroom art", "neutral wall art", "boho decor", "dried flower art", "nature print", "leaf poster"],
        difficulty="easy",
        trending_score=8,
    ),
    "botanical_palm_shadow": PosterPreset(
        id="botanical_palm_shadow",
        name="Palm Leaf Shadow",
        category="botanical",
        prompt="Dramatic palm leaf shadow cast on white wall, high contrast black and white, minimalist tropical aesthetic, soft natural lighting, clean geometric shadow patterns, modern botanical art",
        negative_prompt="text, watermark, color, busy background, multiple shadows, harsh",
        tags=["palm leaf art", "shadow art", "black white poster", "tropical decor", "minimalist print", "modern wall art", "botanical shadow", "beach house decor", "living room art", "monochrome art", "palm print", "shadow poster", "nature art"],
        difficulty="easy",
        trending_score=8,
    ),
    "botanical_fern": PosterPreset(
        id="botanical_fern",
        name="Fern Frond",
        category="botanical",
        prompt="Elegant fern frond with detailed leaves, botanical illustration style, deep forest green, cream paper texture background, vintage scientific drawing influence, natural symmetry, delicate botanical art",
        negative_prompt="text, watermark, bright colors, cartoonish, cluttered, multiple ferns",
        tags=["fern art", "botanical print", "green wall art", "plant poster", "vintage botanical", "forest decor", "nature print", "botanical illustration", "leaf art", "greenery poster", "living room art", "earth tone decor", "plant lover"],
        difficulty="easy",
        trending_score=7,
    ),
    "botanical_wildflowers": PosterPreset(
        id="botanical_wildflowers",
        name="Wildflower Meadow",
        category="botanical",
        prompt="Delicate wildflower arrangement, soft watercolor style, lavender, chamomile, and dried grasses, muted pastel colors, white background, romantic botanical illustration, cottagecore aesthetic",
        negative_prompt="text, watermark, harsh colors, photorealistic, cluttered, modern elements",
        tags=["wildflower art", "botanical print", "floral poster", "cottage decor", "pastel wall art", "flower print", "meadow art", "romantic decor", "bedroom art", "botanical illustration", "dried flower art", "nature print", "vintage floral"],
        difficulty="medium",
        trending_score=8,
    ),

    # ── LANDSCAPE / NATURE SCENES ──────────────────────────────
    "landscape_misty_mountains": PosterPreset(
        id="landscape_misty_mountains",
        name="Misty Mountains",
        category="landscape",
        prompt="Layered mountain silhouettes in morning mist, soft gradient from dark to light, minimalist landscape, peaceful serene atmosphere, muted blue and grey tones, negative space composition, contemplative mood",
        negative_prompt="text, watermark, sun, people, buildings, harsh colors, detailed trees",
        tags=["mountain art", "misty landscape", "minimalist poster", "nature wall art", "blue wall art", "peaceful print", "mountain poster", "foggy art", "serene decor", "living room art", "landscape print", "nature decor", "calm art"],
        difficulty="easy",
        trending_score=9,
    ),
    "landscape_forest_fog": PosterPreset(
        id="landscape_forest_fog",
        name="Foggy Forest",
        category="landscape",
        prompt="Pine forest disappearing into morning fog, moody atmospheric landscape, muted green and grey tones, misty trees fading into distance, peaceful mysterious atmosphere, Scandinavian forest aesthetic",
        negative_prompt="text, watermark, animals, people, bright colors, sunny, cluttered",
        tags=["forest art", "foggy landscape", "pine tree poster", "nature wall art", "moody art", "scandinavian decor", "green wall art", "peaceful poster", "woodland art", "misty forest", "cabin decor", "nature print", "tree art"],
        difficulty="medium",
        trending_score=8,
    ),
    "landscape_desert_sunset": PosterPreset(
        id="landscape_desert_sunset",
        name="Desert Sunset",
        category="landscape",
        prompt="Minimalist desert landscape at sunset, warm orange and purple gradient sky, silhouetted saguaro cactus, clean horizon line, peaceful southwestern aesthetic, vast open space, dreamy warm tones",
        negative_prompt="text, watermark, people, animals, harsh details, busy composition",
        tags=["desert art", "sunset poster", "southwestern decor", "cactus art", "orange wall art", "landscape print", "warm wall art", "living room art", "nature poster", "minimalist landscape", "travel art", "boho decor", "earth tone art"],
        difficulty="easy",
        trending_score=7,
    ),
    "landscape_ocean_horizon": PosterPreset(
        id="landscape_ocean_horizon",
        name="Ocean Horizon",
        category="landscape",
        prompt="Calm ocean meeting sky at horizon line, soft blue gradient, minimal waves, peaceful seascape, meditative atmosphere, vast negative space, clean simple composition, serene coastal scene",
        negative_prompt="text, watermark, boats, people, beach, dramatic waves, sunset colors",
        tags=["ocean art", "sea poster", "blue wall art", "minimalist art", "coastal decor", "beach house art", "calm poster", "horizon art", "seascape print", "peaceful art", "bathroom decor", "nature print", "water art"],
        difficulty="easy",
        trending_score=8,
    ),
    "landscape_aurora": PosterPreset(
        id="landscape_aurora",
        name="Northern Lights",
        category="landscape",
        prompt="Aurora borealis dancing over snowy landscape, vibrant green and purple lights, starry night sky, silhouetted pine trees, magical winter scene, ethereal glowing atmosphere",
        negative_prompt="text, watermark, people, buildings, daytime, harsh edges, cartoonish",
        tags=["aurora art", "northern lights", "night sky poster", "winter wall art", "green wall art", "magical art", "nature print", "starry night", "landscape poster", "bedroom art", "celestial art", "nordic decor", "winter scene"],
        difficulty="hard",
        trending_score=7,
    ),

    # ── ART DECO / GEOMETRIC ───────────────────────────────────
    "artdeco_sunburst": PosterPreset(
        id="artdeco_sunburst",
        name="Art Deco Sunburst",
        category="artdeco",
        prompt="Art Deco geometric sunburst design, golden rays emanating from center, elegant 1920s glamour style, cream and gold color palette, symmetrical pattern, vintage luxury aesthetic, Gatsby era inspiration",
        negative_prompt="text, watermark, photorealistic, busy, modern elements, harsh colors",
        tags=["art deco print", "sunburst art", "gold wall art", "geometric poster", "1920s decor", "gatsby style", "vintage art", "glamour poster", "luxury decor", "living room art", "retro print", "golden art", "symmetrical art"],
        difficulty="medium",
        trending_score=9,
    ),
    "artdeco_geometric": PosterPreset(
        id="artdeco_geometric",
        name="Art Deco Geometric",
        category="artdeco",
        prompt="Art Deco geometric pattern with arches and fan shapes, deep emerald green and gold, luxurious vintage aesthetic, symmetrical design, elegant 1920s style, bold graphic composition",
        negative_prompt="text, watermark, photorealistic, messy, modern, harsh",
        tags=["art deco poster", "geometric art", "emerald green decor", "gold wall art", "vintage print", "1920s art", "luxury poster", "retro geometric", "glamour decor", "office art", "elegant poster", "pattern art", "gatsby decor"],
        difficulty="medium",
        trending_score=9,
    ),
    "artdeco_woman": PosterPreset(
        id="artdeco_woman",
        name="Art Deco Woman",
        category="artdeco",
        prompt="Stylized Art Deco woman profile silhouette, elegant 1920s fashion, geometric hair and dress patterns, gold and black color scheme, vintage poster style, glamorous feminine art, bold graphic design",
        negative_prompt="text, watermark, photorealistic, modern clothes, detailed face, messy",
        tags=["art deco woman", "vintage poster", "feminine art", "gold black art", "1920s print", "glamour poster", "retro woman art", "elegant wall art", "fashion poster", "bedroom art", "gatsby style", "silhouette art", "vintage feminine"],
        difficulty="hard",
        trending_score=8,
    ),

    # ── ABSTRACT / MINIMALIST ──────────────────────────────────
    "abstract_soft_shapes": PosterPreset(
        id="abstract_soft_shapes",
        name="Soft Abstract Shapes",
        category="abstract",
        prompt="Soft organic abstract shapes in pastel colors, pink sage and cream tones, modern minimalist composition, floating forms, gentle curves, calming nursery aesthetic, dreamy soft gradients",
        negative_prompt="text, watermark, harsh edges, bright colors, geometric, busy, detailed",
        tags=["abstract art", "pastel poster", "minimalist print", "nursery art", "soft wall art", "modern abstract", "pink wall art", "sage green decor", "bedroom poster", "neutral art", "calming art", "organic shapes", "dreamy art"],
        difficulty="easy",
        trending_score=8,
    ),
    "abstract_terracotta": PosterPreset(
        id="abstract_terracotta",
        name="Terracotta Abstract",
        category="abstract",
        prompt="Modern abstract shapes in warm terracotta, rust, and beige tones, mid-century modern influence, organic forms with clean edges, earthy minimalist composition, bohemian aesthetic",
        negative_prompt="text, watermark, bright colors, photorealistic, cluttered, cold tones",
        tags=["terracotta art", "abstract print", "boho wall art", "rust color decor", "mid century modern", "earth tone art", "minimalist poster", "warm wall art", "living room art", "neutral abstract", "organic shapes", "modern poster", "earthy decor"],
        difficulty="easy",
        trending_score=8,
    ),
    "abstract_line_woman": PosterPreset(
        id="abstract_line_woman",
        name="Line Art Woman",
        category="abstract",
        prompt="Minimalist continuous line drawing of woman face profile, single elegant line, simple graceful curves, black line on white background, modern feminine art, abstract portrait, sophisticated simplicity",
        negative_prompt="text, watermark, shading, color, detailed features, multiple lines, messy",
        tags=["line art", "woman portrait", "minimalist poster", "feminine art", "black white art", "modern print", "abstract face", "elegant wall art", "bedroom decor", "one line art", "simple art", "contemporary poster", "face art"],
        difficulty="medium",
        trending_score=9,
    ),
    "abstract_matisse": PosterPreset(
        id="abstract_matisse",
        name="Matisse Style Cutouts",
        category="abstract",
        prompt="Abstract organic shapes in Matisse cut-out style, bold blue and coral colors, playful flowing forms, paper collage aesthetic, modern art museum quality, joyful composition",
        negative_prompt="text, watermark, photorealistic, dull colors, geometric, harsh edges",
        tags=["matisse style", "abstract art", "blue wall art", "modern poster", "colorful print", "art museum", "cutout art", "playful decor", "living room art", "contemporary art", "bold art", "artistic poster", "gallery art"],
        difficulty="medium",
        trending_score=7,
    ),

    # ── CELESTIAL / MYSTICAL ───────────────────────────────────
    "celestial_moon_phases": PosterPreset(
        id="celestial_moon_phases",
        name="Moon Phases",
        category="celestial",
        prompt="Moon phases cycle from new to full moon, minimalist celestial design, soft golden moons on dark navy background, mystical lunar art, horizontal arrangement, elegant astronomical illustration",
        negative_prompt="text, watermark, stars, detailed craters, harsh colors, cluttered",
        tags=["moon phases art", "celestial poster", "lunar wall art", "moon print", "mystical decor", "navy gold art", "bedroom poster", "boho celestial", "astronomy art", "witch decor", "night sky print", "moon cycle", "spiritual art"],
        difficulty="easy",
        trending_score=8,
    ),
    "celestial_sun_moon": PosterPreset(
        id="celestial_sun_moon",
        name="Sun and Moon",
        category="celestial",
        prompt="Mystical sun and moon design with faces, celestial art in gold and black, vintage tarot card aesthetic, symmetrical composition, magical spiritual artwork, art nouveau influence",
        negative_prompt="text, watermark, photorealistic, harsh colors, modern, cluttered",
        tags=["sun moon art", "celestial poster", "mystical print", "tarot art", "gold black decor", "spiritual wall art", "boho poster", "bedroom art", "vintage celestial", "magical art", "cosmic print", "sun face art", "moon face"],
        difficulty="medium",
        trending_score=7,
    ),
    "celestial_constellation": PosterPreset(
        id="celestial_constellation",
        name="Constellation Map",
        category="celestial",
        prompt="Elegant star constellation map, minimalist astronomical design, white stars connected by thin lines on deep navy blue, vintage scientific illustration style, zodiac stars, celestial cartography",
        negative_prompt="text, watermark, colorful, cartoonish, busy, modern graphics",
        tags=["constellation art", "star map poster", "astronomy print", "navy wall art", "celestial decor", "zodiac art", "night sky poster", "scientific art", "bedroom decor", "vintage astronomy", "star print", "cosmic art", "space poster"],
        difficulty="medium",
        trending_score=7,
    ),

    # ── MID-CENTURY MODERN ─────────────────────────────────────
    "midcentury_abstract": PosterPreset(
        id="midcentury_abstract",
        name="Mid-Century Abstract",
        category="midcentury",
        prompt="Mid-century modern abstract composition, warm earth tones with mustard yellow, burnt orange and olive green, geometric organic shapes, retro 1950s aesthetic, atomic age influence, bold graphic design",
        negative_prompt="text, watermark, photorealistic, cold colors, busy, modern",
        tags=["mid century art", "retro poster", "abstract print", "mustard wall art", "vintage decor", "1950s style", "earth tone art", "living room poster", "modern retro", "geometric art", "atomic age", "vintage abstract", "warm wall art"],
        difficulty="medium",
        trending_score=8,
    ),
    "midcentury_travel": PosterPreset(
        id="midcentury_travel",
        name="Vintage Travel Poster",
        category="midcentury",
        prompt="Retro travel poster style illustration, stylized landscape with bold flat colors, vintage tourism aesthetic, art deco influence, warm sunset palette, classic mid-century graphic design, nostalgic travel art",
        negative_prompt="text, watermark, photorealistic, modern elements, detailed, harsh",
        tags=["travel poster", "vintage art", "retro print", "mid century poster", "tourism art", "nostalgic decor", "colorful wall art", "living room art", "vacation poster", "vintage travel", "graphic art", "retro decor", "adventure art"],
        difficulty="hard",
        trending_score=7,
    ),

    # ── NURSERY / SOFT ─────────────────────────────────────────
    "nursery_clouds": PosterPreset(
        id="nursery_clouds",
        name="Dreamy Clouds",
        category="nursery",
        prompt="Soft fluffy clouds in pastel pink and white, dreamy sky scene, gentle watercolor style, peaceful nursery aesthetic, calming baby room art, soft gradients, ethereal floating clouds",
        negative_prompt="text, watermark, harsh colors, dark, dramatic, busy",
        tags=["cloud art", "nursery poster", "baby room decor", "pink wall art", "pastel print", "dreamy art", "soft wall art", "girls room", "peaceful poster", "sky art", "gentle decor", "kids room art", "calming print"],
        difficulty="easy",
        trending_score=7,
    ),
    "nursery_rainbow": PosterPreset(
        id="nursery_rainbow",
        name="Pastel Rainbow",
        category="nursery",
        prompt="Minimalist pastel rainbow arc, soft muted colors in boho style, simple curved bands, cream background, modern nursery art, Scandinavian kids room aesthetic, gentle calming design",
        negative_prompt="text, watermark, bright colors, busy, cartoonish, detailed",
        tags=["rainbow art", "nursery print", "pastel poster", "boho nursery", "baby room art", "kids wall art", "minimalist rainbow", "soft decor", "neutral nursery", "scandinavian kids", "gentle art", "modern nursery", "simple print"],
        difficulty="easy",
        trending_score=7,
    ),

    # ── VALENTINE'S ───────────────────────────────────────────
    "valentine_love_line_art": PosterPreset(
        id="valentine_love_line_art",
        name="Love Line Art",
        category="valentine",
        prompt="minimalist continuous line art drawing of couple embracing, single thin black line on pure white background, elegant romantic illustration, modern love art, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="text, watermark, color, shading, multiple lines, busy, photorealistic",
        tags=["love line art", "couple drawing", "romantic wall art", "valentine poster", "minimalist love art", "couple embrace print", "romantic line drawing", "wedding gift art", "anniversary gift", "bedroom wall decor", "love illustration", "modern romantic art", "valentine gift"],
        difficulty="easy",
        trending_score=9,
    ),
    "valentine_abstract_hearts": PosterPreset(
        id="valentine_abstract_hearts",
        name="Abstract Hearts",
        category="valentine",
        prompt="abstract watercolor hearts composition, overlapping translucent hearts in soft pink red and gold, artistic valentine wall art, modern abstract love art, white background, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="text, watermark, cartoon, childish, busy background, photorealistic",
        tags=["abstract heart art", "valentine wall art", "heart poster print", "pink heart decor", "romantic abstract art", "love heart painting", "watercolor hearts", "valentine gift her", "modern heart print", "bedroom romantic art", "anniversary wall art", "heart illustration", "love poster"],
        difficulty="easy",
        trending_score=9,
    ),
    "valentine_romantic_sunset": PosterPreset(
        id="valentine_romantic_sunset",
        name="Romantic Sunset Silhouette",
        category="valentine",
        prompt="romantic sunset landscape with couple silhouette holding hands, warm orange pink purple gradient sky, minimalist horizon, dreamy atmospheric poster art, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="text, watermark, detailed faces, busy, photorealistic, harsh lines",
        tags=["romantic sunset art", "couple silhouette poster", "sunset wall art", "romantic landscape print", "love sunset poster", "couple holding hands art", "dreamy sunset print", "bedroom wall art romantic", "valentine poster", "wedding gift", "anniversary art", "sunset landscape", "romantic decor"],
        difficulty="medium",
        trending_score=8,
    ),
    "valentine_heart_botanical": PosterPreset(
        id="valentine_heart_botanical",
        name="Heart Botanical",
        category="valentine",
        prompt="botanical illustration arranged in heart shape, delicate wildflowers roses and leaves forming a heart, vintage botanical valentine art, soft muted colors on cream background, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="text, watermark, bright neon, photorealistic, busy background, modern",
        tags=["botanical heart art", "flower heart poster", "valentine botanical print", "floral heart wall art", "wildflower heart", "romantic botanical art", "vintage flower heart", "valentine gift her", "botanical love print", "heart shaped flowers", "garden valentine art", "floral love poster", "romantic flower print"],
        difficulty="easy",
        trending_score=9,
    ),
    "valentine_xoxo_typography": PosterPreset(
        id="valentine_xoxo_typography",
        name="XOXO Typography",
        category="valentine",
        prompt="modern typography poster XOXO in elegant serif font, kisses and hugs text art, soft blush pink background with gold foil texture accents, minimalist valentine typography, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="watermark, busy, cluttered, multiple fonts, childish, photorealistic",
        tags=["xoxo wall art", "valentine typography poster", "xoxo print", "love typography art", "kisses hugs poster", "blush pink wall art", "valentine decor", "modern love print", "romantic typography", "valentine gift", "gold pink wall art", "xoxo poster print", "love quote art"],
        difficulty="easy",
        trending_score=8,
    ),

    # ── YEAR OF HORSE 2026 ────────────────────────────────────
    "horse_fire_ink": PosterPreset(
        id="horse_fire_ink",
        name="Fire Horse Ink",
        category="horse2026",
        prompt="majestic fire horse in traditional Chinese ink wash painting style, dynamic galloping horse with flames and smoke, red and black ink on rice paper texture, lunar new year 2026 art, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="text, watermark, photorealistic, western style, cartoon, busy background",
        tags=["year of horse poster", "chinese new year 2026", "fire horse art", "horse ink painting", "lunar new year poster", "chinese zodiac horse", "horse wall art", "asian horse print", "galloping horse art", "fire horse print", "zodiac 2026 poster", "chinese ink horse", "oriental horse art"],
        difficulty="medium",
        trending_score=9,
    ),
    "horse_elegant_portrait": PosterPreset(
        id="horse_elegant_portrait",
        name="Elegant Horse Portrait",
        category="horse2026",
        prompt="elegant horse portrait in watercolor style, noble horse head with flowing mane, earth tones brown gold cream, artistic equestrian poster, fine art quality, centered composition, main subject in center, breathing space on all edges",
        negative_prompt="text, watermark, photorealistic, cartoon, busy, harsh colors",
        tags=["horse portrait art", "watercolor horse poster", "equestrian wall art", "horse lover gift", "elegant horse print", "horse head painting", "horse mane art", "equestrian decor", "animal portrait poster", "horse watercolor print", "noble horse art", "horse wall decor", "equine art print"],
        difficulty="easy",
        trending_score=8,
    ),
}


CATEGORIES = {
    "japanese": {"name": "Japanese / Zen", "icon": "sakura", "color": "#E8D4D4"},
    "botanical": {"name": "Botanical", "icon": "leaf", "color": "#D4E8D4"},
    "landscape": {"name": "Landscapes", "icon": "mountain", "color": "#D4D4E8"},
    "artdeco": {"name": "Art Deco", "icon": "sparkles", "color": "#E8E4D4"},
    "abstract": {"name": "Abstract", "icon": "palette", "color": "#E8D4E8"},
    "celestial": {"name": "Celestial", "icon": "moon", "color": "#D4D8E8"},
    "midcentury": {"name": "Mid-Century", "icon": "home", "color": "#E8DCD4"},
    "nursery": {"name": "Nursery / Soft", "icon": "cloud", "color": "#F4E8E8"},
    "valentine": {"name": "Valentine's", "icon": "heart", "color": "#F4D4D8"},
    "horse2026": {"name": "Year of Horse 2026", "icon": "horse", "color": "#D4C8B8"},
}


def get_presets_by_category(category: str) -> list:
    return [asdict(p) for p in POSTER_PRESETS.values() if p.category == category]


def get_all_presets() -> list:
    return [asdict(p) for p in POSTER_PRESETS.values()]


def get_trending_presets(limit: int = 10) -> list:
    sorted_presets = sorted(POSTER_PRESETS.values(), key=lambda x: x.trending_score, reverse=True)
    return [asdict(p) for p in sorted_presets[:limit]]


def get_preset(preset_id: str) -> dict | None:
    p = POSTER_PRESETS.get(preset_id)
    return asdict(p) if p else None
