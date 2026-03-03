"""Product import business logic.

Extracted from routes/products.py — no FastAPI dependencies.
Used by scheduler.py and route handlers.
"""

import database as db


async def import_printify_product(p: dict) -> dict:
    """Import a single Printify product into local DB. Returns saved product dict."""
    pid = p["id"]
    image_url = None
    for img in p.get("images", []):
        if img.get("is_default"):
            image_url = img.get("src")
            break
    if not image_url and p.get("images"):
        image_url = p["images"][0].get("src")

    external = p.get("external") or {}
    etsy_listing_id = str(external["id"]) if external.get("id") else None

    product = await db.save_product(
        printify_product_id=pid,
        title=p.get("title", "Untitled"),
        description=p.get("description", ""),
        tags=p.get("tags", []),
        image_url=image_url,
        status="published" if etsy_listing_id else "draft",
    )
    if etsy_listing_id:
        await db.update_product_status(pid, product["status"], etsy_listing_id)
        product["etsy_listing_id"] = etsy_listing_id
    return product
