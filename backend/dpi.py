"""DPI analysis for poster sizes.

Calculates effective DPI for each poster size given a source image,
determines quality tiers, and groups sizes by whether they need upscaling.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple, List

from sizes import POSTER_SIZES


class QualityTier(str, Enum):
    IDEAL = "ideal"             # >= 300 DPI
    GOOD = "good"               # 200-299 DPI
    ACCEPTABLE = "acceptable"   # 150-199 DPI
    NEEDS_UPSCALE = "needs_upscale"  # < 150 DPI


# Thresholds
MIN_SELLABLE_DPI = 150
TARGET_UPSCALE_DPI = 200
MAX_UPSCALE_FACTOR = 4.0

# Physical dimensions per size key (inches)
SIZE_INCHES = {
    "8x10":  (8, 10),
    "11x14": (11, 14),
    "12x16": (12, 16),
    "16x20": (16, 20),
    "18x24": (18, 24),
    "24x36": (24, 36),
}


@dataclass
class SizeAnalysis:
    size_key: str
    size_label: str
    width_inches: int
    height_inches: int
    native_dpi: float
    quality: QualityTier
    is_sellable: bool
    upscale_needed: bool
    upscale_factor: float
    achievable_dpi: float
    target_width: int
    target_height: int
    variant_id: int

    def to_dict(self):
        return {
            "size_key": self.size_key,
            "size_label": self.size_label,
            "native_dpi": self.native_dpi,
            "quality": self.quality.value,
            "is_sellable": self.is_sellable,
            "upscale_needed": self.upscale_needed,
            "upscale_factor": self.upscale_factor,
            "achievable_dpi": self.achievable_dpi,
            "target_width": self.target_width,
            "target_height": self.target_height,
        }


def _classify(dpi: float) -> QualityTier:
    if dpi >= 300:
        return QualityTier.IDEAL
    elif dpi >= 200:
        return QualityTier.GOOD
    elif dpi >= 150:
        return QualityTier.ACCEPTABLE
    return QualityTier.NEEDS_UPSCALE


def analyze_sizes(
    image_width: int,
    image_height: int,
) -> Dict[str, SizeAnalysis]:
    """Analyze all poster sizes for a given source image resolution.

    Returns dict of size_key -> SizeAnalysis with DPI info and
    whether upscaling is needed / feasible.
    """
    from printify import PrintifyAPI

    results: Dict[str, SizeAnalysis] = {}

    for key, size in POSTER_SIZES.items():
        inches = SIZE_INCHES.get(key)
        if not inches:
            continue
        w_in, h_in = inches

        # Native DPI from source without any upscaling
        native_dpi = min(image_width / w_in, image_height / h_in)

        # Factor needed to reach 300 DPI target (full Printify resolution)
        factor_w = size.width / image_width
        factor_h = size.height / image_height
        upscale_factor = max(factor_w, factor_h)

        # What DPI can we achieve with MAX_UPSCALE_FACTOR?
        if upscale_factor <= MAX_UPSCALE_FACTOR:
            # We can reach full 300 DPI target
            achievable_dpi = min(size.width / w_in, size.height / h_in)
        else:
            # Capped at MAX — calculate resulting DPI
            max_w = image_width * MAX_UPSCALE_FACTOR
            max_h = image_height * MAX_UPSCALE_FACTOR
            achievable_dpi = min(max_w / w_in, max_h / h_in)

        quality = _classify(achievable_dpi)
        is_sellable = achievable_dpi >= MIN_SELLABLE_DPI
        upscale_needed = native_dpi < TARGET_UPSCALE_DPI

        results[key] = SizeAnalysis(
            size_key=key,
            size_label=size.label,
            width_inches=w_in,
            height_inches=h_in,
            native_dpi=round(native_dpi, 1),
            quality=quality,
            is_sellable=is_sellable,
            upscale_needed=upscale_needed,
            upscale_factor=round(upscale_factor, 2),
            achievable_dpi=round(achievable_dpi, 1),
            target_width=size.width,
            target_height=size.height,
            variant_id=PrintifyAPI.SIZE_VARIANT_IDS.get(key, 0),
        )

    return results


def group_sizes_by_ratio(
    analysis: Dict[str, SizeAnalysis],
) -> Dict[float, List[str]]:
    """Group sellable sizes by aspect ratio (width/height in inches).

    Returns dict mapping ratio (float) -> list of size keys.
    Only includes sellable sizes.
    """
    from collections import defaultdict
    groups: Dict[float, List[str]] = defaultdict(list)
    for key, sa in analysis.items():
        if sa.is_sellable:
            ratio = round(sa.width_inches / sa.height_inches, 3)
            groups[ratio].append(key)
    return dict(groups)


def get_size_groups(
    analysis: Dict[str, SizeAnalysis],
) -> Tuple[List[str], List[str], List[str]]:
    """Group sizes into action categories.

    Returns:
        (original_ok, upscale_needed, skip)
        - original_ok: native DPI >= TARGET_UPSCALE_DPI, use source image
        - upscale_needed: need upscaling but achievable within MAX factor
        - skip: not sellable (achievable DPI < MIN_SELLABLE_DPI)
    """
    original_ok: List[str] = []
    upscale_needed: List[str] = []
    skip: List[str] = []

    for key, sa in analysis.items():
        if not sa.is_sellable:
            skip.append(key)
        elif not sa.upscale_needed:
            original_ok.append(key)
        else:
            upscale_needed.append(key)

    return original_ok, upscale_needed, skip


def print_analysis(image_width: int, image_height: int):
    """Pretty print for debugging."""
    results = analyze_sizes(image_width, image_height)
    print(f"\nImage: {image_width} x {image_height} px\n")
    print(f"{'Size':<10} {'DPI':<10} {'Quality':<15} {'Action'}")
    print("-" * 70)
    for key in ["8x10", "11x14", "12x16", "16x20", "18x24", "24x36"]:
        if key not in results:
            continue
        r = results[key]
        if not r.is_sellable:
            action = "SKIP (below 150 DPI even with 4x upscale)"
        elif not r.upscale_needed:
            action = f"Use original ({r.native_dpi} DPI)"
        else:
            action = f"Upscale {r.upscale_factor}x -> {r.achievable_dpi} DPI"
        print(f"{key:<10} {r.native_dpi:<10} {r.quality.value:<15} {action}")

    ok, up, sk = get_size_groups(results)
    print(f"\nOriginal OK: {ok}")
    print(f"Upscale needed: {up}")
    print(f"Skip: {sk}")
