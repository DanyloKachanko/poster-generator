"""
Expanded prompt library - JSON-based.
Adds richer metadata: per-category Etsy tags, seasonality, demand level,
per-prompt variations, and style_preset hints.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


LIBRARY_PATH = Path(__file__).parent / "prompt_library.json"


@dataclass
class LibraryCategory:
    id: str
    display_name: str
    icon: str
    color: str
    etsy_tags_base: list
    seasonality: str
    demand_level: str
    competition: str

    def to_dict(self):
        return {
            "id": self.id,
            "display_name": self.display_name,
            "icon": self.icon,
            "color": self.color,
            "etsy_tags_base": self.etsy_tags_base,
            "seasonality": self.seasonality,
            "demand_level": self.demand_level,
            "competition": self.competition,
        }


@dataclass
class LibraryPrompt:
    id: str
    name: str
    category: str
    prompt: str
    negative_prompt: str
    tags_extra: list
    style_preset: str
    difficulty: str
    trending_score: int
    variations: list = field(default_factory=list)

    def get_full_tags(self, category: LibraryCategory) -> list:
        """Merge category base tags + prompt-specific extra tags (max 13 for Etsy)."""
        combined = list(category.etsy_tags_base) + self.tags_extra
        seen = set()
        unique = []
        for tag in combined:
            lower = tag.lower().strip()
            if lower not in seen:
                seen.add(lower)
                unique.append(lower)
        return unique[:13]

    def to_dict(self, category: Optional[LibraryCategory] = None):
        d = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "tags_extra": self.tags_extra,
            "style_preset": self.style_preset,
            "difficulty": self.difficulty,
            "trending_score": self.trending_score,
            "variations": self.variations,
        }
        if category:
            d["full_tags"] = self.get_full_tags(category)
            d["category_display"] = category.display_name
        return d


class PromptLibrary:
    """Loads and serves the expanded prompt library from JSON."""

    def __init__(self, path: Path = LIBRARY_PATH):
        self._categories: dict = {}
        self._prompts: dict = {}
        self._load(path)

    def _load(self, path: Path):
        if not path.exists():
            return

        with open(path) as f:
            data = json.load(f)

        for cat_id, cat_data in data.get("categories", {}).items():
            self._categories[cat_id] = LibraryCategory(id=cat_id, **cat_data)

        for p in data.get("prompts", []):
            self._prompts[p["id"]] = LibraryPrompt(**p)

    def get_categories(self) -> list:
        return [c.to_dict() for c in self._categories.values()]

    def get_category(self, category_id: str) -> Optional[LibraryCategory]:
        return self._categories.get(category_id)

    def get_prompts(self, category: str = None) -> list:
        prompts = list(self._prompts.values())
        if category:
            prompts = [p for p in prompts if p.category == category]
        result = []
        for p in prompts:
            cat = self._categories.get(p.category)
            result.append(p.to_dict(cat))
        return sorted(result, key=lambda x: x["trending_score"], reverse=True)

    def get_prompt(self, prompt_id: str) -> Optional[dict]:
        p = self._prompts.get(prompt_id)
        if not p:
            return None
        cat = self._categories.get(p.category)
        return p.to_dict(cat)

    def get_prompt_obj(self, prompt_id: str) -> Optional[LibraryPrompt]:
        return self._prompts.get(prompt_id)

    def get_prompts_by_seasonality(self, season: str) -> list:
        matching_cats = [
            c.id for c in self._categories.values()
            if c.seasonality == season
        ]
        return self.get_prompts_filtered(categories=matching_cats)

    def get_prompts_filtered(self, categories: list = None) -> list:
        prompts = list(self._prompts.values())
        if categories:
            prompts = [p for p in prompts if p.category in categories]
        result = []
        for p in prompts:
            cat = self._categories.get(p.category)
            result.append(p.to_dict(cat))
        return sorted(result, key=lambda x: x["trending_score"], reverse=True)

    @property
    def total_prompts(self) -> int:
        return len(self._prompts)

    @property
    def total_categories(self) -> int:
        return len(self._categories)


# Singleton
library = PromptLibrary()
