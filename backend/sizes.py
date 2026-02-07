"""Poster size configurations for Printify Matte Vertical Posters (300 DPI)"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PosterSize:
    name: str        # "8x10"
    width: int       # pixels at 300 DPI
    height: int      # pixels at 300 DPI
    label: str       # "8x10 inch"
    ratio: str       # "4:5" or "2:3"
    priority: int    # 1-5, higher = more popular
    needs_upscale: bool = False  # True if size exceeds Leonardo 2x upscale


POSTER_SIZES: Dict[str, PosterSize] = {
    "8x10": PosterSize("8x10", 2400, 3000, "8x10 inch", "4:5", 5),
    "11x14": PosterSize("11x14", 3300, 4200, "11x14 inch", "11:14", 4),
    "12x16": PosterSize("12x16", 3600, 4800, "12x16 inch", "3:4", 3),
    "16x20": PosterSize("16x20", 4800, 6000, "16x20 inch", "4:5", 2, needs_upscale=True),
    "18x24": PosterSize("18x24", 5400, 7200, "18x24 inch", "3:4", 1, needs_upscale=True),
    "24x36": PosterSize("24x36", 7200, 10800, "24x36 inch", "2:3", 1, needs_upscale=True),
}

# Leonardo generation at 2:3 — the tallest poster ratio.
# Crop to 3:4 and 4:5 from this base → no content added, only trimmed.
GENERATION_SETTINGS = {
    "default": {"width": 1536, "height": 2304},
    "2:3": {"width": 1536, "height": 2304},
    "3:4": {"width": 1536, "height": 2048},
    "4:5": {"width": 1536, "height": 1920},
}

# Prompt suffix to ensure AI-generated compositions survive center-cropping
COMPOSITION_SUFFIX = ", centered composition, main subject in center of frame, breathing space on all edges"

# Printify placeholder scale overrides per size.
# Printify's internal placeholder is slightly larger than our 300 DPI images.
# scale > 1.0 forces slight overflow so Printify crops excess instead of
# showing white padding. 4:5 ratio sizes need more (1.08), others need 1.05.
PRINTIFY_SCALE = {
    "8x10": 1.08,
    "11x14": 1.05,
    "12x16": 1.05,
    "16x20": 1.08,
    "18x24": 1.05,
    "24x36": 1.05,
}
PRINTIFY_SCALE_DEFAULT = 1.05


def get_sizes_by_ratio(ratio: str) -> Dict[str, PosterSize]:
    return {k: v for k, v in POSTER_SIZES.items() if v.ratio == ratio}


def get_required_upscale_factor(target_width: int, source_width: int = 1536) -> float:
    return target_width / source_width
