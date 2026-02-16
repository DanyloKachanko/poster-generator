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
