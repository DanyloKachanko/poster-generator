"""Mockup templates, image mockups, and mockup packs queries."""

from typing import Optional, List, Dict, Any
from db.connection import get_pool


# === Mockup Templates ===

async def save_mockup_template(name: str, scene_url: str, scene_width: int, scene_height: int, corners: str, blend_mode: str = "normal") -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO mockup_templates (name, scene_url, scene_width, scene_height, corners, blend_mode)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            name, scene_url, scene_width, scene_height, corners, blend_mode,
        )
        return dict(row)


async def get_mockup_templates() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mockup_templates ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]


async def get_mockup_template(template_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mockup_templates WHERE id = $1", template_id
        )
        return dict(row) if row else None


async def delete_mockup_template(template_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM mockup_templates WHERE id = $1", template_id
        )


async def update_mockup_template(
    template_id: int,
    name: str,
    scene_url: str,
    scene_width: int,
    scene_height: int,
    corners: str,
    blend_mode: str = "normal"
) -> Optional[dict]:
    """Update an existing mockup template."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE mockup_templates
               SET name = $1, scene_url = $2, scene_width = $3, scene_height = $4, corners = $5, blend_mode = $6
               WHERE id = $7
               RETURNING *""",
            name, scene_url, scene_width, scene_height, corners, blend_mode, template_id
        )
        return dict(row) if row else None


# === Mockup Workflow ===

async def update_image_mockup_status(
    image_id: int,
    mockup_url: Optional[str] = None,
    mockup_status: str = "pending",
) -> bool:
    """Update mockup URL and status for a generated image."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if mockup_url:
            result = await conn.execute(
                """
                UPDATE generated_images
                SET mockup_url = $1, mockup_status = $2
                WHERE id = $3
                """,
                mockup_url, mockup_status, image_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE generated_images
                SET mockup_status = $1
                WHERE id = $2
                """,
                mockup_status, image_id,
            )
        return result != "UPDATE 0"


async def get_workflow_posters(
    status: str = "pending",
    limit: int = 50,
    linked_only: bool = True,
) -> List[Dict[str, Any]]:
    """Get posters for workflow approval (pending/needs_attention).

    linked_only=True filters to only images linked to a product (product_id IS NOT NULL).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        linked_filter = "AND gi.product_id IS NOT NULL" if linked_only else ""
        rows = await conn.fetch(
            f"""
            SELECT gi.*, g.prompt, g.style, g.width, g.height
            FROM generated_images gi
            JOIN generations g ON gi.generation_id = g.generation_id
            WHERE gi.mockup_status = $1
              AND g.archived = 0
              AND (g.style IS NULL OR g.style != 'mockup')
              {linked_filter}
            ORDER BY gi.created_at DESC
            LIMIT $2
            """,
            status, limit,
        )
        return [dict(r) for r in rows]


# === Active Mockup Templates ===

async def get_active_mockup_templates() -> List[Dict[str, Any]]:
    """Get all templates marked as active, ordered by id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mockup_templates WHERE is_active = true ORDER BY id"
        )
        return [dict(r) for r in rows]


async def set_template_active(template_id: int, is_active: bool) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE mockup_templates SET is_active = $1 WHERE id = $2",
            is_active, template_id,
        )
        return result != "UPDATE 0"


async def set_active_templates(template_ids: List[int]) -> None:
    """Set exactly these templates as active, deactivating all others."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE mockup_templates SET is_active = false")
        if template_ids:
            await conn.execute(
                "UPDATE mockup_templates SET is_active = true WHERE id = ANY($1)",
                template_ids,
            )


# === Image Mockups (multi-mockup junction) ===

async def save_image_mockup(
    image_id: int,
    template_id: int,
    mockup_data: str,
    rank: int = 1,
    is_included: bool = True,
    pack_id: Optional[int] = None,
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO image_mockups (image_id, template_id, mockup_data, rank, is_included, pack_id)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (image_id, template_id) DO UPDATE SET
                 mockup_data = EXCLUDED.mockup_data,
                 rank = EXCLUDED.rank,
                 is_included = EXCLUDED.is_included,
                 pack_id = EXCLUDED.pack_id
               RETURNING *""",
            image_id, template_id, mockup_data, rank, is_included, pack_id,
        )
        return dict(row)


async def get_image_mockups(image_id: int) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM image_mockups WHERE image_id = $1 ORDER BY rank",
            image_id,
        )
        return [dict(r) for r in rows]


async def delete_image_mockups(image_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM image_mockups WHERE image_id = $1", image_id
        )


async def update_image_mockup_inclusion(mockup_id: int, is_included: bool) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE image_mockups SET is_included = $1 WHERE id = $2",
            is_included, mockup_id,
        )
        return result != "UPDATE 0"


async def update_image_mockup_dovshop_inclusion(mockup_id: int, dovshop_included: bool) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE image_mockups SET dovshop_included = $1 WHERE id = $2",
            dovshop_included, mockup_id,
        )
        return result != "UPDATE 0"


async def set_image_mockup_dovshop_primary(mockup_id: int, image_id: int) -> bool:
    """Set a mockup as dovshop primary, unsetting all others for that image."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE image_mockups SET dovshop_primary = false WHERE image_id = $1",
            image_id,
        )
        result = await conn.execute(
            "UPDATE image_mockups SET dovshop_primary = true WHERE id = $1",
            mockup_id,
        )
        return result != "UPDATE 0"


async def get_image_mockups_for_dovshop(image_id: int) -> List[Dict[str, Any]]:
    """Get mockups for an image with is_included, dovshop_included, and dovshop_primary flags."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, template_id, rank, is_included, dovshop_included, dovshop_primary
               FROM image_mockups
               WHERE image_id = $1
               ORDER BY rank""",
            image_id,
        )
        return [dict(r) for r in rows]


async def update_image_mockup_etsy_info(
    mockup_id: int, etsy_image_id: str, etsy_cdn_url: str
) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE image_mockups SET etsy_image_id = $1, etsy_cdn_url = $2 WHERE id = $3",
            etsy_image_id, etsy_cdn_url, mockup_id,
        )
        return result != "UPDATE 0"


# === Mockup Packs ===

async def create_mockup_pack(name: str, color_grade: str = "none") -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO mockup_packs (name, color_grade) VALUES ($1, $2) RETURNING *",
            name, color_grade,
        )
        return dict(row)


async def get_mockup_packs() -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT mp.*, COUNT(mpt.id) as template_count
            FROM mockup_packs mp
            LEFT JOIN mockup_pack_templates mpt ON mpt.pack_id = mp.id
            GROUP BY mp.id
            ORDER BY mp.created_at DESC
        """)
        return [dict(r) for r in rows]


async def get_mockup_pack(pack_id: int) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mockup_packs WHERE id = $1", pack_id
        )
        return dict(row) if row else None


async def update_mockup_pack(pack_id: int, name: str, color_grade: str = "none") -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE mockup_packs SET name = $1, color_grade = $2 WHERE id = $3 RETURNING *",
            name, color_grade, pack_id,
        )
        return dict(row) if row else None


async def delete_mockup_pack(pack_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM mockup_packs WHERE id = $1", pack_id)


async def set_pack_templates(pack_id: int, template_ids: List[int]) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM mockup_pack_templates WHERE pack_id = $1", pack_id
        )
        if template_ids:
            await conn.executemany(
                "INSERT INTO mockup_pack_templates (pack_id, template_id, rank) VALUES ($1, $2, $3)",
                [(pack_id, tid, rank) for rank, tid in enumerate(template_ids, start=1)],
            )


async def get_pack_templates(pack_id: int) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT mt.*, mpt.rank as pack_rank
            FROM mockup_pack_templates mpt
            JOIN mockup_templates mt ON mt.id = mpt.template_id
            WHERE mpt.pack_id = $1
            ORDER BY mpt.rank
        """, pack_id)
        return [dict(r) for r in rows]


async def get_image_mockup_pack_id(image_id: int) -> Optional[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT pack_id FROM image_mockups WHERE image_id = $1 LIMIT 1",
            image_id,
        )
