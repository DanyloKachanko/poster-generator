# Color Grading for Mockup Packs

## Summary

Add post-compose color grading to mockup images. Each mockup pack stores a color grade preset. When composing or approving with a pack, the grade is applied as the final step after perspective warp.

## Presets

| Preset | Brightness | Saturation | Contrast | Warmth | Use case |
|--------|-----------|-----------|---------|--------|----------|
| `none` | 1.0 | 1.0 | 1.0 | 0 | No processing |
| `warm-home` | 1.02 | 0.92 | 1.03 | 30 | Scandinavian/warm interior |
| `moody-dark` | 0.95 | 0.85 | 1.08 | 15 | Dark dramatic rooms |
| `clean-bright` | 1.05 | 0.95 | 1.0 | 10 | Bright/minimal scenes |
| `golden-hour` | 1.05 | 0.9 | 1.02 | 45 | Warm sunset lighting |

## Implementation

### Backend
- **Config**: `COLOR_GRADE_PRESETS` dict in `backend/config.py`
- **Processing**: `apply_color_grade(image, preset_name)` using PIL.ImageEnhance (brightness, contrast, saturation) + warmth tint via pixel blend
- **DB**: `color_grade TEXT DEFAULT 'none'` column on `mockup_packs`
- **Pipeline**: Applied in `_compose_all_templates()` after perspective warp, before PNG encoding
- **API**: Pack CRUD includes `color_grade`; `ComposeAllRequest` gets optional `color_grade` param

### Frontend
- Pack create/edit form: color grade dropdown selector
- Compose preview mode: optional grade dropdown
- Workflow: auto-uses pack's grade when composing with a pack

### Scope
- Compose preview: yes
- Approve flow: yes
- Scheduler: no (speed)
