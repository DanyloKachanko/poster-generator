"""Pinterest API v5 client with OAuth 2.0 flow."""

import logging
import os
import time
import base64
import httpx
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

BASE_URL = "https://api.pinterest.com/v5"
AUTH_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = f"{BASE_URL}/oauth/token"

SCOPES = "boards:read,pins:read,pins:write,user_accounts:read"


@dataclass
class PinterestTokens:
    access_token: str
    refresh_token: str
    expires_at: int
    scope: str = ""


class PinterestAPI:
    """Pinterest API v5 client with OAuth 2.0."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("PINTEREST_APP_ID", "")
        self.app_secret = app_secret or os.getenv("PINTEREST_APP_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv(
            "PINTEREST_REDIRECT_URI", "https://design.dovshop.org/api/pinterest/callback"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    # --- OAuth2 ---

    def get_auth_url(self, state: str = "dovshop") -> str:
        """Generate Pinterest OAuth2 authorization URL."""
        return (
            f"{AUTH_URL}?"
            f"client_id={self.app_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&scope={SCOPES}"
            f"&state={state}"
        )

    def _basic_auth_header(self) -> str:
        credentials = base64.b64encode(
            f"{self.app_id}:{self.app_secret}".encode()
        ).decode()
        return f"Basic {credentials}"

    async def exchange_code(self, code: str) -> PinterestTokens:
        """Exchange authorization code for access + refresh tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers={
                    "Authorization": self._basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return PinterestTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", ""),
                expires_at=int(time.time()) + data.get("expires_in", 2592000),
                scope=data.get("scope", ""),
            )

    async def refresh_access_token(self, refresh_token: str) -> PinterestTokens:
        """Refresh an expired access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers={
                    "Authorization": self._basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return PinterestTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                expires_at=int(time.time()) + data.get("expires_in", 2592000),
                scope=data.get("scope", ""),
            )

    # --- API helpers ---

    async def _request(self, method: str, endpoint: str, access_token: str, **kwargs) -> dict:
        """Make authenticated Pinterest API request."""
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{BASE_URL}{endpoint}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
                **kwargs,
            )
            resp.raise_for_status()
            if resp.status_code == 204:
                return {}
            return resp.json()

    # --- User ---

    async def get_user_account(self, access_token: str) -> dict:
        """Get authenticated user's account info."""
        return await self._request("GET", "/user_account", access_token)

    # --- Boards ---

    async def get_boards(self, access_token: str) -> list:
        """Get all boards for authenticated user."""
        result = await self._request("GET", "/boards?page_size=100", access_token)
        return result.get("items", [])

    async def create_board(self, access_token: str, name: str, description: str = "") -> dict:
        """Create a new board."""
        return await self._request(
            "POST", "/boards", access_token,
            json={"name": name, "description": description, "privacy": "PUBLIC"},
        )

    # --- Pins ---

    async def create_pin(
        self,
        access_token: str,
        board_id: str,
        title: str,
        description: str,
        link: str,
        image_url: str,
        alt_text: str = "",
    ) -> dict:
        """Create a pin with an image URL."""
        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:500],
            "link": link,
            "media_source": {
                "source_type": "image_url",
                "url": image_url,
            },
        }
        if alt_text:
            payload["alt_text"] = alt_text[:500]
        return await self._request("POST", "/pins", access_token, json=payload)

    async def delete_pin(self, access_token: str, pin_id: str) -> dict:
        """Delete a pin."""
        return await self._request("DELETE", f"/pins/{pin_id}", access_token)

    async def get_pin(self, access_token: str, pin_id: str) -> dict:
        """Get pin details."""
        return await self._request("GET", f"/pins/{pin_id}", access_token)

    # --- Analytics ---

    async def get_pin_analytics(
        self,
        access_token: str,
        pin_id: str,
        start_date: str,
        end_date: str,
        metric_types: str = "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK",
    ) -> dict:
        """Get analytics for a specific pin."""
        endpoint = (
            f"/pins/{pin_id}/analytics"
            f"?start_date={start_date}"
            f"&end_date={end_date}"
            f"&metric_types={metric_types}"
            f"&app_types=ALL"
            f"&split_field=NO_SPLIT"
        )
        return await self._request("GET", endpoint, access_token)

    async def get_user_analytics(
        self,
        access_token: str,
        start_date: str,
        end_date: str,
        metric_types: str = "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK",
    ) -> dict:
        """Get account-level analytics."""
        endpoint = (
            f"/user_account/analytics"
            f"?start_date={start_date}"
            f"&end_date={end_date}"
            f"&metric_types={metric_types}"
        )
        return await self._request("GET", endpoint, access_token)
