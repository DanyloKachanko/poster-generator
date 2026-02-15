"""Utility functions for cleaning and rebuilding Etsy listing descriptions."""

import re
from typing import List, Optional

# Mapping from size key to display string
SIZE_DISPLAY = {
    "8x10": "8×10 inches (20×25 cm)",
    "11x14": "11×14 inches (28×36 cm)",
    "12x16": "12×16 inches (30×40 cm)",
    "16x20": "16×20 inches (40×50 cm)",
    "18x24": "18×24 inches (45×60 cm)",
    "24x36": "24×36 inches (60×90 cm)",
}

# Standard disclaimer — inserted after AVAILABLE SIZES, before gift section
POSTER_DISCLAIMER = (
    "⚠️ PLEASE NOTE:\n"
    "- This listing is for the POSTER PRINT ONLY — frame is not included\n"
    "- Please double-check the size you are ordering before purchase\n"
    "- Need a custom size? Message us and we'll work it out together"
)

# Regex to match the entire AVAILABLE SIZES block:
#   📐 AVAILABLE SIZES:\n- line\n- line\n...
# Stops at the next section (emoji header or blank line followed by non-bullet)
_SIZES_BLOCK_RE = re.compile(
    r"📐\s*AVAILABLE SIZES:?\s*\n(?:\s*[-•\*]\s*.*\n?)*",
    re.IGNORECASE,
)

# Regex to match individual size bullet lines anywhere in description
# Matches lines like "- 24×36 inches (60×90 cm)" or "• 8x10 inches (20x25 cm)"
_SIZE_LINE_RE = re.compile(
    r"[ \t]*[-•\*]\s*\d+\s*[x×]\s*\d+\s*(?:inches?)?\s*\(?\d+\s*[x×]\s*\d+\s*(?:cm)?\)?\s*\n?",
    re.IGNORECASE,
)

# Regex to detect if disclaimer is already present
_DISCLAIMER_RE = re.compile(r"⚠️\s*PLEASE NOTE:", re.IGNORECASE)


def ensure_disclaimer(description: str) -> str:
    """Ensure the standard poster disclaimer is present in the description.

    Inserts after AVAILABLE SIZES block if possible, otherwise appends before
    the last line (shop promo). Skips if already present.
    """
    if not description or _DISCLAIMER_RE.search(description):
        return description

    # Try to insert after AVAILABLE SIZES block
    sizes_match = _SIZES_BLOCK_RE.search(description)
    if sizes_match:
        insert_pos = sizes_match.end()
        return (
            description[:insert_pos].rstrip("\n")
            + "\n\n"
            + POSTER_DISCLAIMER
            + "\n\n"
            + description[insert_pos:].lstrip("\n")
        )

    # Fallback: insert before the last line (shop promo with emoji)
    lines = description.rstrip().split("\n")
    if len(lines) > 2:
        # Insert before last non-empty line
        return "\n".join(lines[:-1]) + "\n\n" + POSTER_DISCLAIMER + "\n\n" + lines[-1]

    # Last resort: append at the end
    return description.rstrip() + "\n\n" + POSTER_DISCLAIMER


def clean_description(
    description: str,
    enabled_sizes: Optional[List[str]] = None,
) -> str:
    """Clean a listing description by rebuilding the AVAILABLE SIZES section.

    - If enabled_sizes is provided: replaces the sizes block with only enabled sizes
    - If enabled_sizes is empty or None: removes the sizes block entirely
    - Always ensures the poster disclaimer is present
    """
    if not description:
        return description

    if enabled_sizes:
        # Build replacement block with only enabled sizes
        lines = []
        for size_key in ["8x10", "11x14", "12x16", "16x20", "18x24", "24x36"]:
            if size_key in enabled_sizes and size_key in SIZE_DISPLAY:
                lines.append(f"- {SIZE_DISPLAY[size_key]}")

        if lines:
            replacement = "📐 AVAILABLE SIZES:\n" + "\n".join(lines) + "\n"
        else:
            replacement = ""
    else:
        replacement = ""

    # Replace the entire sizes block
    cleaned = _SIZES_BLOCK_RE.sub(replacement, description)

    # Ensure disclaimer is present
    cleaned = ensure_disclaimer(cleaned)

    # Clean up extra blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
