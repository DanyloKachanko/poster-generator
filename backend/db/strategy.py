"""AI strategy history queries."""

import json
from typing import Optional
from db.connection import get_pool


async def save_ai_strategy(result: dict, product_count: int = 0) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """INSERT INTO ai_strategy_history (result, product_count)
               VALUES ($1::jsonb, $2) RETURNING id""",
            json.dumps(result),
            product_count,
        )


async def get_ai_strategy_history(limit: int = 20) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, result, product_count, created_at
               FROM ai_strategy_history ORDER BY created_at DESC LIMIT $1""",
            limit,
        )
        items = []
        for r in rows:
            d = dict(r)
            d["result"] = json.loads(d["result"]) if isinstance(d["result"], str) else d["result"]
            d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
            items.append(d)
        return items


async def get_ai_strategy_latest() -> Optional[dict]:
    items = await get_ai_strategy_history(limit=1)
    return items[0] if items else None
