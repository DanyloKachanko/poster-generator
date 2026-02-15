from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from seasonal_calendar import get_upcoming_events, get_event, get_event_presets
import database as db

router = APIRouter(tags=["calendar"])


class CalendarTrackRequest(BaseModel):
    printify_product_id: str
    preset_id: Optional[str] = None


@router.get("/calendar/upcoming")
async def calendar_upcoming(days: int = Query(90, ge=7, le=365)):
    """Get upcoming seasonal events with status and product counts."""
    events = get_upcoming_events(days_ahead=days)
    product_counts = await db.get_calendar_product_counts()
    used_presets = await db.get_used_preset_ids()
    for ev in events:
        ev["product_count"] = product_counts.get(ev["id"], 0)
        # Count how many of the event's suggested presets are used
        ev["presets_used"] = len([p for p in ev["preset_ids"] if p in used_presets])
        ev["presets_total"] = len(ev["preset_ids"])
    return {"events": events}


@router.get("/calendar/events/{event_id}")
async def calendar_event_detail(event_id: str):
    """Get a single event with full details."""
    ev = get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    product_counts = await db.get_calendar_product_counts()
    used_presets = await db.get_used_preset_ids()
    ev["product_count"] = product_counts.get(event_id, 0)
    ev["presets_used"] = len([p for p in ev["preset_ids"] if p in used_presets])
    ev["presets_total"] = len(ev["preset_ids"])
    ev["products"] = await db.get_calendar_event_products(event_id)
    return ev


@router.get("/calendar/events/{event_id}/presets")
async def calendar_event_presets(event_id: str):
    """Get presets suggested for an event, with used/unused status."""
    presets = get_event_presets(event_id)
    if not presets:
        raise HTTPException(status_code=404, detail="Event not found")
    used_ids = set(await db.get_used_preset_ids())
    for p in presets:
        p["is_used"] = p["id"] in used_ids
    return {"presets": presets}


@router.post("/calendar/events/{event_id}/track")
async def calendar_track_product(event_id: str, request: CalendarTrackRequest):
    """Link a product to a calendar event."""
    ev = get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.track_calendar_product(
        event_id=event_id,
        printify_product_id=request.printify_product_id,
        preset_id=request.preset_id,
    )
    return {"status": "tracked", "event_id": event_id, "printify_product_id": request.printify_product_id}
