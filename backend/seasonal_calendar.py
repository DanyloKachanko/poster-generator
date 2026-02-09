"""
Seasonal calendar — holiday definitions and helpers for content planning.

Static event data (like presets.py). Variable-date holidays use
a lookup table for 2025-2028.
"""

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from presets import POSTER_PRESETS, CATEGORIES


EST = timezone(timedelta(hours=-5))


@dataclass
class SeasonalEvent:
    id: str
    name: str
    month: int
    day: int
    icon: str
    color: str
    lead_time_weeks: int
    live_by_weeks: int
    description: str
    preset_categories: List[str]
    preset_ids: List[str]
    seasonal_tags: List[str]
    priority: int  # 1-5


# Variable-date holidays by year
_VARIABLE_DATES = {
    "lunar_new_year": {2025: (1, 29), 2026: (2, 17), 2027: (2, 6), 2028: (1, 26)},
    "easter": {2025: (4, 20), 2026: (4, 5), 2027: (3, 28), 2028: (4, 16)},
    "mothers_day": {2025: (5, 11), 2026: (5, 10), 2027: (5, 9), 2028: (5, 14)},
    "fathers_day": {2025: (6, 15), 2026: (6, 21), 2027: (6, 20), 2028: (6, 18)},
    "thanksgiving": {2025: (11, 27), 2026: (11, 26), 2027: (11, 25), 2028: (11, 23)},
}

SEASONAL_EVENTS: List[SeasonalEvent] = [
    SeasonalEvent(
        id="new_years",
        name="New Year's Day",
        month=1, day=1,
        icon="\U0001F386",  # fireworks
        color="#8B5CF6",
        lead_time_weeks=8, live_by_weeks=3,
        description="Fresh start, resolutions, celebratory mood",
        preset_categories=["celestial", "abstract", "artdeco"],
        preset_ids=["celestial_moon_phases", "artdeco_sunburst", "abstract_soft_shapes"],
        seasonal_tags=["new year art", "new year poster", "celebration wall art"],
        priority=3,
    ),
    SeasonalEvent(
        id="lunar_new_year",
        name="Lunar New Year",
        month=2, day=17,  # default 2026
        icon="\U0001F40E",  # horse
        color="#DC2626",
        lead_time_weeks=8, live_by_weeks=3,
        description="Year of the Horse 2026 — Chinese/Lunar New Year",
        preset_categories=["horse2026", "japanese"],
        preset_ids=["horse_fire_ink", "horse_elegant_portrait", "japanese_cherry_blossom"],
        seasonal_tags=["lunar new year", "chinese new year 2026", "year of horse"],
        priority=5,
    ),
    SeasonalEvent(
        id="valentines_day",
        name="Valentine's Day",
        month=2, day=14,
        icon="\u2764\uFE0F",  # heart
        color="#EC4899",
        lead_time_weeks=8, live_by_weeks=4,
        description="Love, romance, couple gifts — peak poster demand",
        preset_categories=["valentine", "botanical"],
        preset_ids=[
            "valentine_love_line_art", "valentine_abstract_hearts",
            "valentine_romantic_sunset", "valentine_heart_botanical",
            "valentine_xoxo_typography",
        ],
        seasonal_tags=["valentine poster", "romantic wall art", "love gift"],
        priority=5,
    ),
    SeasonalEvent(
        id="st_patricks",
        name="St. Patrick's Day",
        month=3, day=17,
        icon="\u2618\uFE0F",  # shamrock
        color="#22C55E",
        lead_time_weeks=6, live_by_weeks=3,
        description="Irish-themed, green, nature, luck",
        preset_categories=["botanical", "landscape"],
        preset_ids=["botanical_fern", "botanical_eucalyptus", "landscape_forest_fog"],
        seasonal_tags=["st patricks day", "green wall art", "irish decor"],
        priority=2,
    ),
    SeasonalEvent(
        id="spring_season",
        name="Spring Season",
        month=3, day=20,
        icon="\U0001F338",  # cherry blossom
        color="#F472B6",
        lead_time_weeks=8, live_by_weeks=4,
        description="Renewal, florals, pastels — spring refresh decor",
        preset_categories=["botanical", "japanese", "landscape"],
        preset_ids=[
            "japanese_cherry_blossom", "botanical_wildflowers",
            "botanical_eucalyptus", "landscape_forest_fog",
        ],
        seasonal_tags=["spring decor", "spring wall art", "floral poster"],
        priority=4,
    ),
    SeasonalEvent(
        id="easter",
        name="Easter",
        month=4, day=5,  # default 2026
        icon="\U0001F430",  # rabbit
        color="#A78BFA",
        lead_time_weeks=6, live_by_weeks=3,
        description="Pastels, florals, nature, family",
        preset_categories=["botanical", "nursery"],
        preset_ids=["botanical_wildflowers", "nursery_rainbow", "nursery_clouds"],
        seasonal_tags=["easter decor", "spring art", "pastel wall art"],
        priority=3,
    ),
    SeasonalEvent(
        id="mothers_day",
        name="Mother's Day",
        month=5, day=10,  # default 2026
        icon="\U0001F490",  # bouquet
        color="#F43F5E",
        lead_time_weeks=8, live_by_weeks=4,
        description="Florals, love, feminine art — top gift holiday",
        preset_categories=["botanical", "nursery", "valentine"],
        preset_ids=[
            "botanical_wildflowers", "valentine_heart_botanical",
            "valentine_love_line_art", "abstract_line_woman",
            "botanical_monstera",
        ],
        seasonal_tags=["mothers day gift", "mom wall art", "floral gift"],
        priority=5,
    ),
    SeasonalEvent(
        id="fathers_day",
        name="Father's Day",
        month=6, day=21,  # default 2026
        icon="\U0001F454",  # necktie
        color="#3B82F6",
        lead_time_weeks=8, live_by_weeks=4,
        description="Landscapes, masculine themes, mid-century modern",
        preset_categories=["landscape", "midcentury"],
        preset_ids=[
            "landscape_misty_mountains", "landscape_ocean_horizon",
            "midcentury_abstract", "midcentury_travel",
        ],
        seasonal_tags=["fathers day gift", "dad wall art", "masculine decor"],
        priority=4,
    ),
    SeasonalEvent(
        id="summer_season",
        name="Summer Season",
        month=6, day=20,
        icon="\u2600\uFE0F",  # sun
        color="#F59E0B",
        lead_time_weeks=8, live_by_weeks=4,
        description="Beach, ocean, tropical vibes, bright colors",
        preset_categories=["landscape", "botanical"],
        preset_ids=[
            "landscape_ocean_horizon", "landscape_desert_sunset",
            "botanical_palm_shadow", "botanical_monstera",
        ],
        seasonal_tags=["summer decor", "beach wall art", "tropical poster"],
        priority=4,
    ),
    SeasonalEvent(
        id="independence_day",
        name="4th of July",
        month=7, day=4,
        icon="\U0001F1FA\U0001F1F8",  # US flag
        color="#EF4444",
        lead_time_weeks=6, live_by_weeks=3,
        description="Patriotic, landscape, American themes",
        preset_categories=["landscape", "abstract"],
        preset_ids=["landscape_desert_sunset", "landscape_misty_mountains", "abstract_terracotta"],
        seasonal_tags=["4th of july decor", "patriotic wall art", "american art"],
        priority=3,
    ),
    SeasonalEvent(
        id="back_to_school",
        name="Back to School",
        month=8, day=15,
        icon="\U0001F393",  # grad cap
        color="#6366F1",
        lead_time_weeks=8, live_by_weeks=4,
        description="Dorm room decor, study space, inspirational",
        preset_categories=["abstract", "midcentury"],
        preset_ids=[
            "abstract_matisse", "abstract_terracotta",
            "midcentury_abstract", "abstract_soft_shapes",
        ],
        seasonal_tags=["dorm room art", "college poster", "study decor"],
        priority=3,
    ),
    SeasonalEvent(
        id="fall_season",
        name="Fall Season",
        month=9, day=22,
        icon="\U0001F342",  # fallen leaf
        color="#D97706",
        lead_time_weeks=8, live_by_weeks=4,
        description="Warm tones, harvest, cozy vibes",
        preset_categories=["landscape", "botanical"],
        preset_ids=[
            "landscape_forest_fog", "botanical_fern",
            "abstract_terracotta", "landscape_misty_mountains",
        ],
        seasonal_tags=["fall decor", "autumn wall art", "cozy poster"],
        priority=4,
    ),
    SeasonalEvent(
        id="halloween",
        name="Halloween",
        month=10, day=31,
        icon="\U0001F383",  # pumpkin
        color="#F97316",
        lead_time_weeks=8, live_by_weeks=4,
        description="Spooky, mystical, dark celestial themes",
        preset_categories=["celestial", "abstract"],
        preset_ids=[
            "celestial_moon_phases", "celestial_sun_moon",
            "celestial_constellation", "landscape_aurora",
        ],
        seasonal_tags=["halloween art", "spooky decor", "mystical poster"],
        priority=4,
    ),
    SeasonalEvent(
        id="thanksgiving",
        name="Thanksgiving",
        month=11, day=26,  # default 2026
        icon="\U0001F983",  # turkey
        color="#92400E",
        lead_time_weeks=6, live_by_weeks=3,
        description="Gratitude, harvest, warm earth tones",
        preset_categories=["botanical", "landscape"],
        preset_ids=[
            "botanical_wildflowers", "landscape_forest_fog",
            "abstract_terracotta", "botanical_fern",
        ],
        seasonal_tags=["thanksgiving decor", "harvest art", "autumn poster"],
        priority=3,
    ),
    SeasonalEvent(
        id="christmas",
        name="Christmas",
        month=12, day=25,
        icon="\U0001F384",  # christmas tree
        color="#16A34A",
        lead_time_weeks=10, live_by_weeks=6,
        description="Biggest gift holiday — winter, cozy, festive",
        preset_categories=["landscape", "botanical", "nursery"],
        preset_ids=[
            "landscape_aurora", "landscape_forest_fog",
            "landscape_misty_mountains", "nursery_clouds",
            "botanical_eucalyptus",
        ],
        seasonal_tags=["christmas wall art", "holiday poster", "winter decor"],
        priority=5,
    ),
    SeasonalEvent(
        id="nye",
        name="New Year's Eve",
        month=12, day=31,
        icon="\U0001F389",  # party popper
        color="#7C3AED",
        lead_time_weeks=6, live_by_weeks=3,
        description="Glamour, celebration, sparkle",
        preset_categories=["celestial", "artdeco"],
        preset_ids=[
            "artdeco_sunburst", "artdeco_geometric",
            "celestial_constellation",
        ],
        seasonal_tags=["nye decor", "celebration art", "glamour poster"],
        priority=3,
    ),
]

_EVENTS_BY_ID = {e.id: e for e in SEASONAL_EVENTS}


def _event_date(event: SeasonalEvent, year: int) -> date:
    """Get the actual date for an event in a given year."""
    if event.id in _VARIABLE_DATES:
        lookup = _VARIABLE_DATES[event.id]
        if year in lookup:
            m, d = lookup[year]
            return date(year, m, d)
    return date(year, event.month, event.day)


def _event_status(
    event_date: date, lead_weeks: int, live_by_weeks: int, today: date
) -> str:
    """Compute status based on where today falls relative to event windows."""
    if today > event_date:
        return "past"
    start_creating = event_date - timedelta(weeks=lead_weeks)
    must_be_live = event_date - timedelta(weeks=live_by_weeks)
    if today >= must_be_live:
        return "must_be_live"
    if today >= start_creating:
        return "creating"
    if today >= start_creating - timedelta(weeks=2):
        return "soon"
    return "upcoming"


def get_upcoming_events(days_ahead: int = 90) -> List[dict]:
    """Return events within the next `days_ahead` days, with computed fields."""
    today = datetime.now(EST).date()
    cutoff = today + timedelta(days=days_ahead)
    results = []

    for event in SEASONAL_EVENTS:
        # Check current year and next year
        for year in [today.year, today.year + 1]:
            ev_date = _event_date(event, year)
            if ev_date < today - timedelta(days=7):
                continue  # skip events more than a week ago
            if ev_date > cutoff:
                continue

            start_creating = ev_date - timedelta(weeks=event.lead_time_weeks)
            must_be_live = ev_date - timedelta(weeks=event.live_by_weeks)
            status = _event_status(ev_date, event.lead_time_weeks, event.live_by_weeks, today)
            days_until = (ev_date - today).days

            results.append({
                **asdict(event),
                "event_date": ev_date.isoformat(),
                "year": year,
                "start_creating": start_creating.isoformat(),
                "must_be_live": must_be_live.isoformat(),
                "status": status,
                "days_until": days_until,
            })
            break  # only include the nearest occurrence

    results.sort(key=lambda e: e["event_date"])
    return results


def get_event(event_id: str) -> Optional[dict]:
    """Get a single event with computed dates for current year."""
    event = _EVENTS_BY_ID.get(event_id)
    if not event:
        return None
    today = datetime.now(EST).date()
    # Find nearest upcoming occurrence
    for year in [today.year, today.year + 1]:
        ev_date = _event_date(event, year)
        if ev_date >= today - timedelta(days=7):
            start_creating = ev_date - timedelta(weeks=event.lead_time_weeks)
            must_be_live = ev_date - timedelta(weeks=event.live_by_weeks)
            status = _event_status(ev_date, event.lead_time_weeks, event.live_by_weeks, today)
            return {
                **asdict(event),
                "event_date": ev_date.isoformat(),
                "year": year,
                "start_creating": start_creating.isoformat(),
                "must_be_live": must_be_live.isoformat(),
                "status": status,
                "days_until": (ev_date - today).days,
            }
    return asdict(event)


def get_event_presets(event_id: str) -> List[dict]:
    """Return presets mapped to an event, with category info."""
    event = _EVENTS_BY_ID.get(event_id)
    if not event:
        return []

    results = []
    seen = set()

    # First add explicitly listed preset IDs
    for pid in event.preset_ids:
        if pid in POSTER_PRESETS and pid not in seen:
            p = POSTER_PRESETS[pid]
            cat = CATEGORIES.get(p.category, {})
            results.append({
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "category_name": cat.get("name", p.category) if isinstance(cat, dict) else p.category,
                "difficulty": p.difficulty,
                "trending_score": p.trending_score,
                "tags": p.tags,
            })
            seen.add(pid)

    # Then add any from matching categories not already included
    for pid, p in POSTER_PRESETS.items():
        if p.category in event.preset_categories and pid not in seen:
            cat = CATEGORIES.get(p.category, {})
            results.append({
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "category_name": cat.get("name", p.category) if isinstance(cat, dict) else p.category,
                "difficulty": p.difficulty,
                "trending_score": p.trending_score,
                "tags": p.tags,
            })
            seen.add(pid)

    return results
