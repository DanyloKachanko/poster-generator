"""Generation history, generated images, and credit usage queries."""

from typing import Optional, List, Dict, Any
from db.connection import get_pool


async def save_generation(
    generation_id: str,
    prompt: str,
    negative_prompt: Optional[str],
    model_id: str,
    model_name: Optional[str],
    style: Optional[str],
    preset: Optional[str],
    width: int,
    height: int,
    num_images: int,
    status: str = "PENDING",
) -> int:
    """Save a new generation record."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO generations
            (generation_id, prompt, negative_prompt, model_id, model_name,
             style, preset, width, height, num_images, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            generation_id, prompt, negative_prompt, model_id, model_name,
            style, preset, width, height, num_images, status,
        )
        return row["id"]


async def update_generation_status(
    generation_id: str,
    status: str,
    api_credit_cost: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Update generation status and credit cost."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status == "COMPLETE":
            await conn.execute(
                """
                UPDATE generations
                SET status = $1, api_credit_cost = $2, completed_at = NOW()
                WHERE generation_id = $3
                """,
                status, api_credit_cost, generation_id,
            )
        else:
            await conn.execute(
                """
                UPDATE generations
                SET status = $1, api_credit_cost = $2, error_message = $3
                WHERE generation_id = $4
                """,
                status, api_credit_cost, error_message, generation_id,
            )


async def save_generated_images(
    generation_id: str,
    images: List[Dict[str, str]],
) -> None:
    """Save generated images for a generation."""
    if not images:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO generated_images (generation_id, image_id, url)
            VALUES ($1, $2, $3)
            """,
            [(generation_id, img.get("id"), img.get("url")) for img in images],
        )


async def save_credit_usage(
    generation_id: str,
    credits_used: int,
    balance_after: Optional[int] = None,
) -> None:
    """Save credit usage record."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO credit_usage (generation_id, credits_used, balance_after)
            VALUES ($1, $2, $3)
            """,
            generation_id, credits_used, balance_after,
        )


async def get_generation(generation_id: str) -> Optional[Dict[str, Any]]:
    """Get a single generation by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM generations WHERE generation_id = $1",
            generation_id,
        )
        return dict(row) if row else None


async def get_generation_images(generation_id: str) -> List[Dict[str, Any]]:
    """Get all images for a generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM generated_images WHERE generation_id = $1",
            generation_id,
        )
        return [dict(row) for row in rows]


async def archive_generation(generation_id: str) -> bool:
    """Archive (soft-delete) a generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE generations SET archived = 1 WHERE generation_id = $1",
            generation_id,
        )
        return result != "UPDATE 0"


async def restore_generation(generation_id: str) -> bool:
    """Restore an archived generation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE generations SET archived = 0 WHERE generation_id = $1",
            generation_id,
        )
        return result != "UPDATE 0"


async def get_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    style: Optional[str] = None,
    exclude_style: Optional[str] = None,
    model_id: Optional[str] = None,
    archived: bool = False,
) -> Dict[str, Any]:
    """
    Get paginated generation history with optional filters.
    Returns dict with items, total count, and pagination info.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build WHERE clause
        conditions = ["g.archived = $1"]
        params: list = [1 if archived else 0]
        idx = 2

        if status:
            conditions.append(f"g.status = ${idx}")
            params.append(status)
            idx += 1
        if style:
            conditions.append(f"g.style = ${idx}")
            params.append(style)
            idx += 1
        if exclude_style:
            conditions.append(f"(g.style IS NULL OR g.style != ${idx})")
            params.append(exclude_style)
            idx += 1
        if model_id:
            conditions.append(f"g.model_id = ${idx}")
            params.append(model_id)
            idx += 1

        where_clause = "WHERE " + " AND ".join(conditions)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM generations g {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # Get items with images
        query = f"""
            SELECT g.*,
                   STRING_AGG(gi.url, ',') as image_urls,
                   STRING_AGG(gi.image_id, ',') as image_ids
            FROM generations g
            LEFT JOIN generated_images gi ON g.generation_id = gi.generation_id
            {where_clause}
            GROUP BY g.id
            ORDER BY g.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            item = dict(row)
            # Parse concatenated images
            if item.get("image_urls"):
                urls = item["image_urls"].split(",")
                ids = (item.get("image_ids") or "").split(",")
                item["images"] = [
                    {"url": url, "id": img_id}
                    for url, img_id in zip(urls, ids)
                ]
            else:
                item["images"] = []
            del item["image_urls"]
            if "image_ids" in item:
                del item["image_ids"]
            items.append(item)

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }


async def get_total_credits_used() -> int:
    """Get total API credits used."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(api_credit_cost), 0) FROM generations"
        )
        return val or 0


async def get_generation_stats() -> Dict[str, Any]:
    """Get generation statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_generations = await conn.fetchval(
            "SELECT COUNT(*) FROM generations"
        )

        status_rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM generations GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        total_credits = await conn.fetchval(
            "SELECT COALESCE(SUM(api_credit_cost), 0) FROM generations"
        )

        total_images = await conn.fetchval(
            "SELECT COUNT(*) FROM generated_images"
        )

        return {
            "total_generations": total_generations,
            "by_status": by_status,
            "total_credits_used": total_credits or 0,
            "total_images": total_images,
        }
