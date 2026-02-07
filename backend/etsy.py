"""Etsy API v3 client with OAuth 2.0 PKCE flow"""

import os
import time
import secrets
import hashlib
import base64
import httpx
from typing import Optional
from dataclasses import dataclass


@dataclass
class EtsyTokens:
    access_token: str
    refresh_token: str
    expires_at: int
    etsy_user_id: Optional[str] = None
    shop_id: Optional[str] = None


class EtsyAPI:
    """Etsy API v3 client with OAuth 2.0 PKCE"""

    BASE_URL = "https://api.etsy.com/v3/application"
    OAUTH_URL = "https://www.etsy.com/oauth/connect"
    TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

    def __init__(self, api_key: Optional[str] = None, redirect_uri: Optional[str] = None):
        self.api_key = api_key or os.getenv("ETSY_API_KEY", "")
        self.redirect_uri = redirect_uri or os.getenv(
            "ETSY_REDIRECT_URI", "http://localhost:8001/etsy/callback"
        )
        # In-memory PKCE state (per auth flow)
        self._code_verifier: Optional[str] = None
        self._state: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    # === PKCE Helpers ===

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a random code verifier (43-128 chars)."""
        return secrets.token_urlsafe(64)[:96]

    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """SHA256 hash the verifier, base64url encode."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    # === OAuth Flow ===

    def get_auth_url(self, scopes: str = "listings_r transactions_r shops_r") -> dict:
        """Generate OAuth authorization URL with PKCE."""
        self._code_verifier = self._generate_code_verifier()
        self._state = secrets.token_urlsafe(16)
        code_challenge = self._generate_code_challenge(self._code_verifier)

        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "scope": scopes,
            "state": self._state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.OAUTH_URL}?{query}"

        return {
            "url": url,
            "state": self._state,
            "code_verifier": self._code_verifier,
        }

    async def exchange_code(self, code: str, code_verifier: str) -> EtsyTokens:
        """Exchange authorization code for access + refresh tokens."""
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

        expires_at = int(time.time()) + data["expires_in"]

        return EtsyTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )

    async def refresh_access_token(self, refresh_token: str) -> EtsyTokens:
        """Refresh an expired access token."""
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

        expires_at = int(time.time()) + data["expires_in"]

        return EtsyTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )

    # === API Calls ===

    def _auth_headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "x-api-key": self.api_key,
        }

    async def get_me(self, access_token: str) -> dict:
        """Get the authenticated user info (includes shop_id)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/users/me",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_shop(self, access_token: str, shop_id: str) -> dict:
        """Get shop info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_listing(self, access_token: str, listing_id: str) -> dict:
        """Get a single listing with views and num_favorers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/listings/{listing_id}",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_shop_listings(
        self, access_token: str, shop_id: str, limit: int = 25, offset: int = 0
    ) -> dict:
        """Get all active listings for a shop."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}/listings",
                headers=self._auth_headers(access_token),
                params={"limit": limit, "offset": offset, "state": "active"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
