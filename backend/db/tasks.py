"""Background task persistence — survives server restarts."""

import json
from typing import Optional, Dict, Any
from db.connection import get_pool


async def create_background_task(
    task_id: str,
    task_type: str,
    total: int = 0,
) -> None:
    """Create a new background task record."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO background_tasks (task_id, task_type, total, progress_json)
               VALUES ($1, $2, $3, '{}')
               ON CONFLICT (task_id) DO UPDATE SET
                   task_type = EXCLUDED.task_type,
                   status = 'running',
                   total = EXCLUDED.total,
                   done = 0,
                   progress_json = '{}',
                   error = NULL,
                   updated_at = NOW()""",
            task_id, task_type, total,
        )


async def update_background_task(
    task_id: str,
    status: Optional[str] = None,
    done: Optional[int] = None,
    total: Optional[int] = None,
    progress_json: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    """Update a background task's progress."""
    pool = await get_pool()
    parts = ["updated_at = NOW()"]
    values = []
    idx = 2  # $1 is task_id
    if status is not None:
        parts.append(f"status = ${idx}")
        values.append(status)
        idx += 1
    if done is not None:
        parts.append(f"done = ${idx}")
        values.append(done)
        idx += 1
    if total is not None:
        parts.append(f"total = ${idx}")
        values.append(total)
        idx += 1
    if progress_json is not None:
        parts.append(f"progress_json = ${idx}")
        values.append(json.dumps(progress_json))
        idx += 1
    if error is not None:
        parts.append(f"error = ${idx}")
        values.append(error)
        idx += 1
    sql = f"UPDATE background_tasks SET {', '.join(parts)} WHERE task_id = $1"
    async with pool.acquire() as conn:
        await conn.execute(sql, task_id, *values)


async def get_background_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get a background task by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM background_tasks WHERE task_id = $1",
            task_id,
        )
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("progress_json"), str):
            d["progress_json"] = json.loads(d["progress_json"])
        return d


async def get_background_tasks_by_type(task_type: str, limit: int = 10) -> list[Dict[str, Any]]:
    """Get recent background tasks of a given type."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM background_tasks WHERE task_type = $1 ORDER BY created_at DESC LIMIT $2",
            task_type, limit,
        )
        results = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("progress_json"), str):
                d["progress_json"] = json.loads(d["progress_json"])
            results.append(d)
        return results
