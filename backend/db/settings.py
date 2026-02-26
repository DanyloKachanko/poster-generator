"""App settings, Etsy tokens, and default mockup template queries."""

from typing import Optional, Dict, Any
from db.connection import get_pool


# === Etsy Tokens ===

async def save_etsy_tokens(
    access_token: str,
    refresh_token: str,
    expires_at: int,
    etsy_user_id: Optional[str] = None,
    shop_id: Optional[str] = None,
) -> None:
    """Save or update Etsy OAuth tokens (single row, id=1)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO etsy_tokens (id, access_token, refresh_token, expires_at, etsy_user_id, shop_id, updated_at)
            VALUES (1, $1, $2, $3, $4, $5, NOW())
            ON CONFLICT(id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                etsy_user_id = COALESCE(EXCLUDED.etsy_user_id, etsy_tokens.etsy_user_id),
                shop_id = COALESCE(EXCLUDED.shop_id, etsy_tokens.shop_id),
                updated_at = NOW()
            """,
            access_token, refresh_token, expires_at, etsy_user_id, shop_id,
        )


async def get_etsy_tokens() -> Optional[Dict[str, Any]]:
    """Get stored Etsy tokens."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM etsy_tokens WHERE id = 1")
        return dict(row) if row else None


async def delete_etsy_tokens() -> None:
    """Remove Etsy tokens (disconnect)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM etsy_tokens")


# === App Settings ===

async def get_setting(key: str) -> Optional[str]:
    """Get a setting value by key."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM app_settings WHERE key = $1", key
        )
        return row["value"] if row else None


async def set_setting(key: str, value: str) -> None:
    """Set a setting value (upsert)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = $2, updated_at = NOW()
            """,
            key, value,
        )


async def get_default_mockup_template_id() -> Optional[int]:
    """Get the default mockup template ID."""
    val = await get_setting("default_mockup_template_id")
    return int(val) if val else None


async def set_default_mockup_template_id(template_id: int) -> None:
    """Set the default mockup template ID."""
    await set_setting("default_mockup_template_id", str(template_id))
