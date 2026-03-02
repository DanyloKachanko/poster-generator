# Default negative prompt for all generations
DEFAULT_NEGATIVE_PROMPT = "text, words, letters, watermark, signature, logo, blurry, low quality, distorted, deformed, ugly, poorly drawn, bad anatomy, extra limbs, disfigured, grain, noise"

# Available models for poster generation (V1 API)
MODELS = {
    "phoenix": {
        "id": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3",
        "name": "Phoenix 1.0",
        "description": "Best prompt adherence and text rendering",
        "ultra": True,
    },
    "kino_xl": {
        "id": "aa77f04e-3eec-4034-9c07-d0f619684628",
        "name": "Kino XL",
        "description": "Cinematic style, great for dramatic scenes",
    },
    "lightning_xl": {
        "id": "b24e16ff-06e3-43eb-8d33-4416c2d75876",
        "name": "Lightning XL",
        "description": "Fast generation, good for iterations",
    },
    "vision_xl": {
        "id": "5c232a9e-9061-4777-980a-ddc8e65647c6",
        "name": "Vision XL",
        "description": "Excels at realism and photography",
    },
    "diffusion_xl": {
        "id": "1e60896f-3c26-4296-8ecc-53e2afecc132",
        "name": "Diffusion XL",
        "description": "Versatile, good for abstract art",
    },
    "anime_xl": {
        "id": "e71a1c2f-4f80-4800-934f-2c68979d8cc8",
        "name": "Anime XL",
        "description": "Anime and illustration style",
    },
}

DEFAULT_MODEL = "phoenix"

# Available poster sizes (dimensions must be multiples of 64 for Leonardo API)
SIZES = {
    "poster_2_3": {
        "name": "Poster 2:3",
        "width": 1536,
        "height": 2304,
        "description": "Standard poster — auto-crops to all print sizes",
    },
    "poster_4_5": {
        "name": "Poster 4:5",
        "width": 1232,
        "height": 1536,
        "description": "8×10, 16×20 prints — exact ratio, no crop needed",
    },
    "poster_3_4": {
        "name": "Poster 3:4",
        "width": 1152,
        "height": 1536,
        "description": "Photo-ratio poster — 11×14, 9×12 prints",
    },
    "square_1_1": {
        "name": "Square 1:1",
        "width": 1024,
        "height": 1024,
        "description": "Instagram, Etsy thumbnails",
    },
    "landscape_16_9": {
        "name": "Landscape 16:9",
        "width": 1344,
        "height": 768,
        "description": "Widescreen, desktop wallpapers",
    },
}

DEFAULT_SIZE = "poster_4_5"

# Prompt suffix for consistent quality
PROMPT_SUFFIX = ", high resolution, print-ready art, professional quality, no text, no watermark"

# Style presets
STYLE_PRESETS = {
    "japanese": {
        "name": "Japanese",
        "presets": {
            "mountain": {
                "name": "Mountain Landscape",
                "prompt": f"Minimalist Japanese mountain landscape, Mount Fuji silhouette, soft gradient sky, muted earth tones, zen aesthetic, clean lines, modern poster design{PROMPT_SUFFIX}"
            },
            "wave": {
                "name": "Ocean Waves",
                "prompt": f"The Great Wave Japanese style, modern minimalist interpretation, navy blue and cream colors, clean geometric shapes, zen aesthetic, wall art poster{PROMPT_SUFFIX}"
            },
            "cherry": {
                "name": "Cherry Blossom",
                "prompt": f"Cherry blossom branch, minimalist Japanese art, soft pink gradient sky, clean design, zen aesthetic, wall art poster{PROMPT_SUFFIX}"
            },
            "zen": {
                "name": "Zen Garden",
                "prompt": f"Minimalist zen garden illustration, raked sand patterns, single stone, soft neutral colors, meditative aesthetic, modern Japanese poster art{PROMPT_SUFFIX}"
            },
            "torii": {
                "name": "Torii Gate",
                "prompt": f"Floating torii gate silhouette, calm water reflection, misty atmosphere, minimalist Japanese art, red and grey tones, serene aesthetic{PROMPT_SUFFIX}"
            },
            "bamboo": {
                "name": "Bamboo Forest",
                "prompt": f"Bamboo forest, morning mist, vertical composition, minimalist Japanese art, sage green tones, zen aesthetic, modern poster design{PROMPT_SUFFIX}"
            },
            "koi": {
                "name": "Koi Fish",
                "prompt": f"Single koi fish, ink wash style, circular composition, minimalist Japanese art, black and gold, zen aesthetic{PROMPT_SUFFIX}"
            },
            "pagoda": {
                "name": "Pagoda",
                "prompt": f"Japanese pagoda silhouette in morning mist, layered mountains background, soft grey and rose tones, minimalist zen art, modern poster{PROMPT_SUFFIX}"
            },
            "crane": {
                "name": "Paper Crane",
                "prompt": f"Origami paper crane, delicate fold details, soft white and gold, minimalist Japanese art, clean composition, modern poster{PROMPT_SUFFIX}"
            },
            "bridge": {
                "name": "Moon Bridge",
                "prompt": f"Japanese garden moon bridge over calm pond, reflection in water, muted teal and cream tones, minimalist zen art{PROMPT_SUFFIX}"
            },
            "ink_circle": {
                "name": "Enso Circle",
                "prompt": f"Ink brush enso circle, imperfect brushstroke on cream paper, wabi-sabi aesthetic, minimalist zen art, meditative poster{PROMPT_SUFFIX}"
            }
        }
    },
    "botanical": {
        "name": "Botanical",
        "presets": {
            "leaves": {
                "name": "Single Leaf",
                "prompt": f"Minimalist botanical line art, single leaf illustration, sage green on cream background, modern poster design, clean aesthetic{PROMPT_SUFFIX}"
            },
            "fern": {
                "name": "Fern Fronds",
                "prompt": f"Delicate fern fronds, botanical illustration, minimalist style, muted green tones, wall art print{PROMPT_SUFFIX}"
            },
            "eucalyptus": {
                "name": "Eucalyptus",
                "prompt": f"Eucalyptus branch watercolor, soft muted colors, minimalist botanical art, modern poster design{PROMPT_SUFFIX}"
            },
            "monstera": {
                "name": "Monstera",
                "prompt": f"Single monstera leaf, deep green on cream background, botanical illustration, minimalist modern art, clean lines{PROMPT_SUFFIX}"
            },
            "wildflower": {
                "name": "Wildflower",
                "prompt": f"Dried pressed wildflower aesthetic, vintage botanical print, muted earth tones, delicate stems, minimalist composition{PROMPT_SUFFIX}"
            },
            "palm": {
                "name": "Palm Leaf",
                "prompt": f"Tropical palm leaf, bold shadow, black and cream contrast, minimalist botanical art, modern poster design{PROMPT_SUFFIX}"
            },
            "succulent": {
                "name": "Succulent",
                "prompt": f"Succulent plant overhead view, rosette pattern, sage and dusty pink tones, minimalist botanical illustration{PROMPT_SUFFIX}"
            },
            "olive": {
                "name": "Olive Branch",
                "prompt": f"Olive branch illustration, Mediterranean style, muted green and cream, minimalist botanical art, elegant composition{PROMPT_SUFFIX}"
            },
            "mushroom": {
                "name": "Wild Mushroom",
                "prompt": f"Forest mushroom cluster illustration, warm brown and cream tones, vintage botanical study style, detailed minimalist poster art{PROMPT_SUFFIX}"
            },
            "lavender": {
                "name": "Lavender Sprig",
                "prompt": f"Dried lavender sprig, soft purple on cream background, delicate botanical illustration, Provence style, minimalist poster art{PROMPT_SUFFIX}"
            },
            "peony": {
                "name": "Peony Bloom",
                "prompt": f"Single peony bloom, soft pink watercolor, detailed petals, elegant botanical illustration, light cream background, wall art poster{PROMPT_SUFFIX}"
            },
            "herb_garden": {
                "name": "Kitchen Herbs",
                "prompt": f"Rosemary thyme sage herb illustration, green line art on cream, kitchen botanical art, labeled stems, clean poster design{PROMPT_SUFFIX}"
            }
        }
    },
    "abstract": {
        "name": "Abstract",
        "presets": {
            "geometric": {
                "name": "Geometric Shapes",
                "prompt": f"Abstract geometric shapes, modern minimalist art, earth tones, clean lines, contemporary wall art poster{PROMPT_SUFFIX}"
            },
            "arch": {
                "name": "Arch Shapes",
                "prompt": f"Abstract arch shapes, terracotta and cream colors, mid-century modern style, minimalist poster art{PROMPT_SUFFIX}"
            },
            "circles": {
                "name": "Overlapping Circles",
                "prompt": f"Overlapping circles, soft gradient colors, abstract minimalist art, modern poster design{PROMPT_SUFFIX}"
            },
            "lines": {
                "name": "Flowing Lines",
                "prompt": f"Flowing parallel lines, wave pattern, smooth gradient, abstract minimalist art, modern poster design{PROMPT_SUFFIX}"
            },
            "blocks": {
                "name": "Color Blocks",
                "prompt": f"Abstract color blocks, Rothko inspired, soft edges, muted earth tones, contemplative minimalist art{PROMPT_SUFFIX}"
            },
            "marble": {
                "name": "Marble Texture",
                "prompt": f"Abstract marble texture, gold veins on white, luxurious minimalist art, elegant poster design{PROMPT_SUFFIX}"
            },
            "gradient": {
                "name": "Gradient Orb",
                "prompt": f"Smooth gradient orb, sunset colors, soft abstract art, modern minimalist poster, warm tones{PROMPT_SUFFIX}"
            },
            "terrazzo": {
                "name": "Terrazzo Pattern",
                "prompt": f"Abstract terrazzo pattern, warm neutral stone fragments on cream, modern material texture art, minimalist poster design{PROMPT_SUFFIX}"
            },
            "brushstroke": {
                "name": "Bold Brushstroke",
                "prompt": f"Single bold brushstroke, expressive gestural mark, earth tone on white, abstract expressionist minimalist poster art{PROMPT_SUFFIX}"
            },
            "wave_pattern": {
                "name": "Topographic Waves",
                "prompt": f"Topographic contour lines, flowing wave pattern, single color on cream, abstract minimalist map art, modern poster{PROMPT_SUFFIX}"
            },
            "splatter": {
                "name": "Ink Splatter",
                "prompt": f"Abstract ink splatter composition, controlled chaos, black and gold on white, dynamic minimalist art, modern poster{PROMPT_SUFFIX}"
            }
        }
    },
    "celestial": {
        "name": "Celestial",
        "presets": {
            "moon": {
                "name": "Moon Phases",
                "prompt": f"Minimalist moon phases illustration, soft gradient sky, celestial wall art, cream and navy colors, modern poster design{PROMPT_SUFFIX}"
            },
            "stars": {
                "name": "Starry Night",
                "prompt": f"Abstract starry night, minimalist style, deep blue gradient, scattered stars, modern celestial poster art{PROMPT_SUFFIX}"
            },
            "sun": {
                "name": "Sun Rays",
                "prompt": f"Abstract sun rays, warm gradient colors, minimalist celestial art, modern poster design{PROMPT_SUFFIX}"
            },
            "constellation": {
                "name": "Constellation",
                "prompt": f"Single constellation diagram, fine lines connecting stars, navy blue background, astronomical minimalist art{PROMPT_SUFFIX}"
            },
            "eclipse": {
                "name": "Solar Eclipse",
                "prompt": f"Total solar eclipse, black and gold, corona rays, dramatic celestial art, minimalist poster design{PROMPT_SUFFIX}"
            },
            "nebula": {
                "name": "Nebula Cloud",
                "prompt": f"Watercolor nebula cloud, purple blue pink gradient, soft cosmic art, abstract celestial poster{PROMPT_SUFFIX}"
            },
            "planets": {
                "name": "Solar System",
                "prompt": f"Solar system planets in line, pastel colors, minimalist astronomical art, modern poster design{PROMPT_SUFFIX}"
            },
            "zodiac": {
                "name": "Zodiac Wheel",
                "prompt": f"Minimalist zodiac wheel illustration, fine gold lines on deep navy, astrological art, celestial poster design{PROMPT_SUFFIX}"
            },
            "comet": {
                "name": "Shooting Comet",
                "prompt": f"Single comet with trailing tail, sweeping arc across dark sky, gold and deep blue, minimalist celestial art{PROMPT_SUFFIX}"
            },
            "crescent": {
                "name": "Crescent Moon",
                "prompt": f"Delicate crescent moon with botanical elements, fine line art, gold on navy blue, mystical celestial poster{PROMPT_SUFFIX}"
            },
            "galaxy": {
                "name": "Spiral Galaxy",
                "prompt": f"Spiral galaxy from above, soft purple blue and pink nebula colors, cosmic watercolor style, minimalist space poster{PROMPT_SUFFIX}"
            }
        }
    },
    "landscape": {
        "name": "Landscape",
        "presets": {
            "desert": {
                "name": "Desert Dunes",
                "prompt": f"Desert sand dunes, golden hour light, minimalist landscape art, warm earth tones, serene composition{PROMPT_SUFFIX}"
            },
            "ocean": {
                "name": "Ocean Horizon",
                "prompt": f"Calm ocean horizon, pastel sunrise colors, minimalist seascape, peaceful composition, soft gradients{PROMPT_SUFFIX}"
            },
            "forest": {
                "name": "Misty Forest",
                "prompt": f"Misty forest silhouette layers, minimalist landscape art, muted green and grey tones, atmospheric depth{PROMPT_SUFFIX}"
            },
            "mountain": {
                "name": "Mountain Range",
                "prompt": f"Mountain range silhouettes, sunset gradient sky, layered minimalist landscape, warm to cool tones{PROMPT_SUFFIX}"
            },
            "lake": {
                "name": "Still Lake",
                "prompt": f"Still lake with perfect reflection, minimalist landscape, soft blue and grey tones, peaceful symmetry{PROMPT_SUFFIX}"
            },
            "field": {
                "name": "Golden Field",
                "prompt": f"Single tree in golden wheat field, golden hour light, minimalist landscape art, warm earth tones{PROMPT_SUFFIX}"
            },
            "aurora": {
                "name": "Northern Lights",
                "prompt": f"Northern lights aurora borealis, snowy landscape silhouette, green and purple sky, minimalist art{PROMPT_SUFFIX}"
            },
            "canyon": {
                "name": "Red Canyon",
                "prompt": f"Layered red canyon walls, warm terracotta and orange gradient, dramatic rock formations, minimalist landscape poster{PROMPT_SUFFIX}"
            },
            "waterfall": {
                "name": "Hidden Waterfall",
                "prompt": f"Tall waterfall in lush green valley, misty spray, minimalist landscape art, blue and emerald tones, serene poster{PROMPT_SUFFIX}"
            },
            "meadow": {
                "name": "Wildflower Meadow",
                "prompt": f"Rolling wildflower meadow at golden hour, soft pastel blooms, gentle hills, minimalist landscape art, warm tones{PROMPT_SUFFIX}"
            },
            "volcano": {
                "name": "Distant Volcano",
                "prompt": f"Distant volcano silhouette at dusk, soft orange glow, layered atmosphere, minimalist landscape poster, dramatic sky{PROMPT_SUFFIX}"
            }
        }
    },
    "animal": {
        "name": "Animal",
        "presets": {
            "bear": {
                "name": "Forest Bear",
                "prompt": f"Brown bear portrait in forest setting, soft natural light, detailed fur texture, wildlife art, warm earth tones, modern poster{PROMPT_SUFFIX}"
            },
            "whale": {
                "name": "Blue Whale",
                "prompt": f"Blue whale diving deep ocean, underwater light rays, deep blue gradient, majestic marine life art, minimalist poster{PROMPT_SUFFIX}"
            },
            "deer": {
                "name": "Stag Portrait",
                "prompt": f"Deer stag with antlers, misty forest background, golden morning light, noble wildlife portrait, modern poster art{PROMPT_SUFFIX}"
            },
            "eagle": {
                "name": "Soaring Eagle",
                "prompt": f"Eagle in flight, spread wings, mountain backdrop, dramatic sky, wildlife art, brown and gold tones, modern poster{PROMPT_SUFFIX}"
            },
            "fox": {
                "name": "Red Fox",
                "prompt": f"Red fox portrait, autumn forest background, warm orange and brown tones, detailed wildlife art, modern poster design{PROMPT_SUFFIX}"
            },
            "butterfly": {
                "name": "Monarch Butterfly",
                "prompt": f"Monarch butterfly on wildflower, delicate wing detail, soft bokeh background, orange and black, nature art poster{PROMPT_SUFFIX}"
            },
            "heron": {
                "name": "Great Heron",
                "prompt": f"Great blue heron standing in still water, reflection, misty morning, elegant wildlife art, blue and grey tones, poster{PROMPT_SUFFIX}"
            },
            "octopus": {
                "name": "Octopus",
                "prompt": f"Octopus with flowing tentacles, deep ocean blue, vintage scientific illustration style, marine life art, modern poster{PROMPT_SUFFIX}"
            }
        }
    },
    "minimalist": {
        "name": "Minimalist",
        "presets": {
            "face": {
                "name": "Line Face",
                "prompt": f"Single continuous line drawing of a face, elegant minimal portrait, black line on white, modern art poster{PROMPT_SUFFIX}"
            },
            "body": {
                "name": "Figure Study",
                "prompt": f"Minimalist figure study, single flowing line, feminine silhouette, warm beige tones, modern art poster{PROMPT_SUFFIX}"
            },
            "hands": {
                "name": "Reaching Hands",
                "prompt": f"Two hands reaching toward each other, fine line art, Michelangelo inspired minimalist, cream background, poster art{PROMPT_SUFFIX}"
            },
            "vase": {
                "name": "Simple Vase",
                "prompt": f"Simple ceramic vase silhouette, neutral earth tones, clean shadow, minimalist still life, modern poster art{PROMPT_SUFFIX}"
            },
            "horizon": {
                "name": "Color Horizon",
                "prompt": f"Two-tone color field, horizontal split, complementary muted tones, Rothko inspired minimalist art poster{PROMPT_SUFFIX}"
            },
            "arch_window": {
                "name": "Arch Window",
                "prompt": f"Mediterranean arch window view, soft light streaming in, warm terracotta and blue sky, minimalist architecture poster{PROMPT_SUFFIX}"
            },
            "stairs": {
                "name": "Geometric Stairs",
                "prompt": f"Abstract geometric staircase, impossible architecture, clean lines, light and shadow, minimalist modern poster{PROMPT_SUFFIX}"
            }
        }
    },
    "vintage": {
        "name": "Vintage",
        "presets": {
            "travel": {
                "name": "Travel Poster",
                "prompt": f"Vintage travel poster style, European coastal town, retro color palette, bold graphic design, art deco typography feel{PROMPT_SUFFIX}"
            },
            "botanical_plate": {
                "name": "Botanical Plate",
                "prompt": f"Vintage botanical illustration plate, detailed flower study, aged parchment background, scientific art style, classic poster{PROMPT_SUFFIX}"
            },
            "map": {
                "name": "Antique Map",
                "prompt": f"Antique style map illustration, compass rose, warm sepia tones, aged paper texture, vintage cartography art poster{PROMPT_SUFFIX}"
            },
            "astronomy": {
                "name": "Astronomy Chart",
                "prompt": f"Vintage astronomy chart, star map with constellation lines, deep blue with gold details, antique scientific poster art{PROMPT_SUFFIX}"
            },
            "art_deco": {
                "name": "Art Deco",
                "prompt": f"Art Deco geometric pattern, gold and navy, symmetrical design, 1920s inspired, luxurious vintage poster art{PROMPT_SUFFIX}"
            },
            "still_life": {
                "name": "Still Life",
                "prompt": f"Classical still life painting style, fruit and flowers, Dutch master inspired, rich warm tones, vintage art poster{PROMPT_SUFFIX}"
            },
            "camera": {
                "name": "Vintage Camera",
                "prompt": f"Vintage film camera illustration, retro design, warm sepia and brown tones, technical drawing style, nostalgic poster art{PROMPT_SUFFIX}"
            }
        }
    },
    "coastal": {
        "name": "Coastal",
        "presets": {
            "waves": {
                "name": "Ocean Waves",
                "prompt": f"Crashing ocean waves, aerial view, turquoise and white foam, coastal photography style, serene beach poster art{PROMPT_SUFFIX}"
            },
            "shells": {
                "name": "Sea Shells",
                "prompt": f"Collection of sea shells on sandy beach, soft pastel tones, natural arrangement, coastal still life, minimalist poster{PROMPT_SUFFIX}"
            },
            "lighthouse": {
                "name": "Lighthouse",
                "prompt": f"Coastal lighthouse on rocky cliff, dramatic sky, navy and white, maritime art, minimalist coastal poster{PROMPT_SUFFIX}"
            },
            "driftwood": {
                "name": "Driftwood",
                "prompt": f"Weathered driftwood on empty beach, soft morning light, muted grey and sand tones, minimalist coastal art poster{PROMPT_SUFFIX}"
            },
            "coral": {
                "name": "Coral Reef",
                "prompt": f"Coral reef illustration, warm pink and orange tones, underwater botanical style, marine life art, coastal poster{PROMPT_SUFFIX}"
            },
            "sailboat": {
                "name": "Sailboat",
                "prompt": f"Single sailboat on calm sea, soft horizon, blue and white minimalist, coastal seascape art, modern poster{PROMPT_SUFFIX}"
            },
            "tide_pool": {
                "name": "Tide Pool",
                "prompt": f"Tide pool from above, clear water over colorful stones, soft natural light, coastal nature art, minimalist poster{PROMPT_SUFFIX}"
            },
            "palm_sunset": {
                "name": "Palm Sunset",
                "prompt": f"Palm tree silhouettes at sunset, warm orange and purple gradient sky, tropical coastal scene, modern poster art{PROMPT_SUFFIX}"
            }
        }
    }
}

# Mockup scene prompts for AI mockup generation
MOCKUP_SCENES = {
    "living_room": {
        "name": "Modern Living Room",
        "prompt": "professional interior photography of a modern minimalist living room, a single large white blank rectangular vertical poster in a thin black frame hanging centered on a light gray wall, clean modern furniture, natural daylight from window, 4K, photorealistic, high quality",
    },
    "bedroom": {
        "name": "Cozy Bedroom",
        "prompt": "professional interior photography of a cozy modern bedroom, a single large white blank rectangular vertical poster in a thin black frame hanging on the wall above the bed headboard, soft warm lighting, neutral tones, 4K, photorealistic, high quality",
    },
    "office": {
        "name": "Home Office",
        "prompt": "professional interior photography of a modern home office workspace, a single large white blank rectangular vertical poster in a thin black frame hanging on the wall behind a desk, clean minimal design, natural light, 4K, photorealistic, high quality",
    },
    "gallery": {
        "name": "Art Gallery",
        "prompt": "professional photography of a white-walled art gallery space, a single large white blank rectangular vertical poster in a thin black frame hanging centered on a pristine white wall, spotlight lighting from above, polished concrete floor, 4K, photorealistic, high quality",
    },
    "cafe": {
        "name": "Trendy Cafe",
        "prompt": "professional interior photography of a trendy modern cafe, a single large white blank rectangular vertical poster in a thin black frame hanging on an exposed brick wall, warm ambient lighting, cozy atmosphere, 4K, photorealistic, high quality",
    },
    "nursery": {
        "name": "Kids Nursery",
        "prompt": "professional interior photography of a bright modern nursery room, a single large white blank rectangular vertical poster in a thin light wooden frame hanging on a soft pastel colored wall, cheerful decor, natural daylight, 4K, photorealistic, high quality",
    },
}

MOCKUP_RATIOS = {
    "4:5": {"name": "4:5 (8x10, 16x20)", "width": 1024, "height": 1280},
    "3:4": {"name": "3:4 (12x16, 18x24)", "width": 1024, "height": 1368},
    "2:3": {"name": "2:3", "width": 1024, "height": 1536},
    "11:14": {"name": "11:14 (11x14)", "width": 1024, "height": 1304},
}

# Mockup generation styles (like Leonardo presets)
MOCKUP_STYLES = {
    "stock_photo": {
        "name": "Stock Photo",
        "description": "Professional stock photography style",
    },
    "cinematic": {
        "name": "Cinematic",
        "description": "Cinematic, dramatic lighting",
    },
    "vibrant": {
        "name": "Vibrant",
        "description": "Vibrant, saturated colors",
    },
    "minimal": {
        "name": "Minimal",
        "description": "Clean, minimalist aesthetic",
    },
    "cozy": {
        "name": "Cozy",
        "description": "Warm, inviting atmosphere",
    },
}

# Color grade presets for post-compose processing
COLOR_GRADE_PRESETS = {
    "none": {
        "name": "None",
        "warmth": 0,
        "brightness": 1.0,
        "saturation": 1.0,
        "contrast": 1.0,
    },
    "warm_home": {
        "name": "Warm Home",
        "warmth": 60,
        "brightness": 1.06,
        "saturation": 0.88,
        "contrast": 1.06,
    },
    "moody_dark": {
        "name": "Moody Dark",
        "warmth": 25,
        "brightness": 0.85,
        "saturation": 0.75,
        "contrast": 1.15,
    },
    "clean_bright": {
        "name": "Clean Bright",
        "warmth": 15,
        "brightness": 1.12,
        "saturation": 0.90,
        "contrast": 1.04,
    },
    "golden_hour": {
        "name": "Golden Hour",
        "warmth": 80,
        "brightness": 1.08,
        "saturation": 0.85,
        "contrast": 1.05,
    },
}
