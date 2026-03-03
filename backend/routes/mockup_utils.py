"""Shared utility functions and Pydantic models for mockup routes.

Split from routes/mockups.py — used by mockup_templates, mockup_compose, mockup_workflow.
Business logic functions moved to core/mockups/compose.py — re-exported here for
backward compatibility.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# Re-export business logic from core/mockups/compose
from core.mockups.compose import (  # noqa: F401
    calculate_zone_ratio_from_corners,
    letterbox_poster,
    crop_to_fill,
    _blend_poster_onto_scene,
    _find_perspective_coeffs,
    apply_color_grade,
    compose_all_templates,
    upload_multi_images_to_etsy,
)

# Backward-compat aliases (old names had leading underscores)
_compose_all_templates = compose_all_templates
_upload_multi_images_to_etsy = upload_multi_images_to_etsy


# --- Pydantic Models ---

class MockupSceneRequest(BaseModel):
    scene_type: str
    ratio: str = "4:5"
    custom_prompt: Optional[str] = None
    num_images: int = Field(default=2, ge=1, le=2)
    model_id: Optional[str] = None  # Model key from MODELS, defaults to "vision_xl" for mockups
    style: Optional[str] = None  # Style key from MOCKUP_STYLES, defaults to "black_natural"


class SaveTemplateRequest(BaseModel):
    name: str
    scene_url: str
    scene_width: int = 1024
    scene_height: int = 1280
    corners: List[List[float]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] — TL, TR, BR, BL
    blend_mode: str = "normal"  # "normal" or "multiply"


class ComposeRequest(BaseModel):
    template_id: int
    poster_url: str
    fill_mode: str = "fill"  # Options: "stretch", "fit" (letterbox), "fill" (crop)
    color_grade: str = "none"
