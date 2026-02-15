"""Etsy API v3 client with OAuth 2.0 PKCE flow"""

import os
import time
import secrets
import hashlib
import base64
import urllib.parse
import httpx
from typing import Optional
from dataclasses import dataclass


# Etsy color property IDs and values (standard across all taxonomies)
ETSY_PRIMARY_COLOR_PROPERTY_ID = 200
ETSY_SECONDARY_COLOR_PROPERTY_ID = 52047899002

ETSY_COLOR_VALUES: dict[str, int] = {
    "Beige": 1213,
    "Black": 1,
    "Blue": 2,
    "Bronze": 1216,
    "Brown": 3,
    "Clear": 1219,
    "Copper": 1218,
    "Gold": 1214,
    "Gray": 5,
    "Green": 4,
    "Orange": 6,
    "Pink": 7,
    "Purple": 8,
    "Rainbow": 1220,
    "Red": 9,
    "Rose gold": 1217,
    "Silver": 1215,
    "White": 10,
    "Yellow": 11,
}

VALID_ETSY_COLORS = set(ETSY_COLOR_VALUES.keys())


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

    def __init__(self, api_key: Optional[str] = None, shared_secret: Optional[str] = None, redirect_uri: Optional[str] = None):
        self.api_key = api_key or os.getenv("ETSY_API_KEY", "")
        self.shared_secret = shared_secret or os.getenv("ETSY_SHARED_SECRET", "")
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

    @property
    def _x_api_key(self) -> str:
        """Etsy V3 requires x-api-key as 'keystring:shared_secret'."""
        if self.shared_secret:
            return f"{self.api_key}:{self.shared_secret}"
        return self.api_key

    def _auth_headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "x-api-key": self._x_api_key,
        }

    def _public_headers(self) -> dict:
        """Headers for public Etsy API endpoints (no OAuth needed)."""
        return {"x-api-key": self._x_api_key}

    # === Public API (no OAuth, just API key) ===

    async def search_listings(self, keywords: str, limit: int = 25) -> dict:
        """Search active Etsy listings by keywords (public, no OAuth)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/listings/active",
                headers=self._public_headers(),
                params={"keywords": keywords, "limit": limit},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_shop_public(self, shop_id: str) -> dict:
        """Get shop info using only API key (no OAuth needed)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}",
                headers=self._public_headers(),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_shop_listings_public(self, shop_id: str) -> list[dict]:
        """Fetch ALL active listings for any shop (public, no OAuth)."""
        import asyncio

        all_listings = []
        limit = 100
        offset = 0

        while True:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/shops/{shop_id}/listings/active",
                    headers=self._public_headers(),
                    params={
                        "limit": limit,
                        "offset": offset,
                        "includes": "images",
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            all_listings.extend(results)

            count = data.get("count", 0)
            offset += limit

            if offset >= count or not results:
                break

            await asyncio.sleep(0.25)

        return all_listings

    # === Authenticated API Calls ===

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

    async def get_user_shops(self, access_token: str, user_id: str) -> dict:
        """Get shops for a user (alternative to get_me for finding shop_id)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/users/{user_id}/shops",
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

    async def get_all_listings(
        self, access_token: str, shop_id: str, state: str = "active"
    ) -> list[dict]:
        """Fetch ALL listings for a shop, handling pagination."""
        import asyncio

        all_listings = []
        limit = 100
        offset = 0

        while True:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/shops/{shop_id}/listings",
                    headers=self._auth_headers(access_token),
                    params={
                        "limit": limit,
                        "offset": offset,
                        "state": state,
                        "includes": "images",
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            all_listings.extend(results)

            count = data.get("count", 0)
            offset += limit

            if offset >= count or not results:
                break

            await asyncio.sleep(0.25)

        return all_listings

    async def get_shop_receipts(
        self,
        access_token: str,
        shop_id: str,
        min_created: Optional[int] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch all receipts (orders) for a shop, handling pagination."""
        import asyncio

        all_receipts = []
        offset = 0

        while True:
            params: dict = {"limit": limit, "offset": offset}
            if min_created:
                params["min_created"] = min_created

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/shops/{shop_id}/receipts",
                    headers=self._auth_headers(access_token),
                    params=params,
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            all_receipts.extend(results)

            count = data.get("count", 0)
            offset += limit

            if offset >= count or not results:
                break

            await asyncio.sleep(0.25)

        return all_receipts

    async def update_listing(
        self, access_token: str, shop_id: str, listing_id: str, data: dict
    ) -> dict:
        """Update a listing's title, tags, and/or description."""
        import urllib.parse

        # Etsy API v3 uses PATCH for updateListing (PUT is deprecated and returns 404)
        # Etsy expects list fields (tags, materials) as comma-separated strings
        form_data = {}
        for key, value in data.items():
            if isinstance(value, bool):
                form_data[key] = str(value).lower()
            elif isinstance(value, list):
                form_data[key] = ",".join(str(item) for item in value)
            elif value is not None:
                form_data[key] = str(value)
        encoded_body = urllib.parse.urlencode(form_data)
        print(f"[Etsy update_listing] PATCH listing {listing_id} body: {encoded_body[:500]}")

        async with httpx.AsyncClient() as client:
            headers = {
                **self._auth_headers(access_token),
                "Content-Type": "application/x-www-form-urlencoded",
            }
            response = await client.patch(
                f"{self.BASE_URL}/shops/{shop_id}/listings/{listing_id}",
                headers=headers,
                content=encoded_body.encode(),
                timeout=15.0,
            )
            if response.status_code >= 400:
                print(f"[Etsy update_listing] {response.status_code} for listing {listing_id}: {response.text}")
            else:
                resp_data = response.json()
                print(f"[Etsy update_listing] OK title={resp_data.get('title','?')[:60]} tags={len(resp_data.get('tags',[]))} materials={resp_data.get('materials',[])} ")
            response.raise_for_status()
            return response.json()

    async def get_shop_sections(self, access_token: str, shop_id: str) -> dict:
        """Get shop sections."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}/sections",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_shipping_profiles(self, access_token: str, shop_id: str) -> dict:
        """Get shipping profiles for the shop."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}/shipping-profiles",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    # === Listing Image Management ===

    async def get_listing_images(self, access_token: str, listing_id: str) -> dict:
        """Get all images for a listing."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/listings/{listing_id}/images",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def upload_listing_image(
        self,
        access_token: str,
        shop_id: str,
        listing_id: str,
        image_bytes: bytes,
        filename: str,
        rank: Optional[int] = None,
    ) -> dict:
        """Upload an image to a listing. rank=1 makes it primary."""
        headers = self._auth_headers(access_token)
        files = {"image": (filename, image_bytes, "image/jpeg")}
        data = {}
        if rank is not None:
            data["rank"] = str(rank)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/shops/{shop_id}/listings/{listing_id}/images",
                headers=headers,
                files=files,
                data=data,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def delete_listing_image(
        self,
        access_token: str,
        shop_id: str,
        listing_id: str,
        listing_image_id: str,
    ) -> None:
        """Delete an image from a listing."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/shops/{shop_id}/listings/{listing_id}/images/{listing_image_id}",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()

    # === Listing Properties (colors, etc.) ===

    async def get_listing_properties(self, access_token: str, shop_id: str, listing_id: str) -> list[dict]:
        """Get all properties for a listing (colors, dimensions, etc.)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}/listings/{listing_id}/properties",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

    async def update_listing_property(
        self,
        access_token: str,
        shop_id: str,
        listing_id: str,
        property_id: int,
        value_ids: list[int],
        values: list[str],
    ) -> dict:
        """Update a listing property (e.g., primary/secondary color)."""
        parts = []
        for vid in value_ids:
            parts.append(f"value_ids[]={vid}")
        for v in values:
            parts.append(f"values[]={urllib.parse.quote(v)}")
        encoded_body = "&".join(parts)

        async with httpx.AsyncClient() as client:
            headers = {
                **self._auth_headers(access_token),
                "Content-Type": "application/x-www-form-urlencoded",
            }
            response = await client.put(
                f"{self.BASE_URL}/shops/{shop_id}/listings/{listing_id}/properties/{property_id}",
                headers=headers,
                content=encoded_body.encode(),
                timeout=15.0,
            )
            if response.status_code >= 400:
                print(f"[Etsy update_property] {response.status_code} for listing {listing_id} prop {property_id}: {response.text}")
            response.raise_for_status()
            return response.json()

    # === Production Partners ===

    async def get_production_partners(self, access_token: str, shop_id: str) -> list[dict]:
        """Get production partners for the shop."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{shop_id}/production-partners",
                headers=self._auth_headers(access_token),
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

    # === Listing Image Alt Text ===

    async def set_image_alt_text(
        self,
        access_token: str,
        shop_id: str,
        listing_id: str,
        listing_image_id: str,
        image_url: str,
        alt_text: str,
        rank: int,
    ) -> dict:
        """Set alt text on an existing image by re-uploading it with alt_text."""
        # Etsy API has no PATCH for images — must re-upload with listing_image_id
        async with httpx.AsyncClient() as client:
            # Download existing image
            img_resp = await client.get(image_url, timeout=30.0, follow_redirects=True)
            img_resp.raise_for_status()
            image_bytes = img_resp.content

            # Re-upload with same listing_image_id to set alt_text
            headers = self._auth_headers(access_token)
            files = {"image": ("poster.jpg", image_bytes, "image/jpeg")}
            data = {
                "listing_image_id": str(listing_image_id),
                "alt_text": alt_text,
                "rank": str(rank),
            }
            response = await client.post(
                f"{self.BASE_URL}/shops/{shop_id}/listings/{listing_id}/images",
                headers=headers,
                files=files,
                data=data,
                timeout=60.0,
            )
            if response.status_code >= 400:
                print(f"[Etsy set_image_alt] {response.status_code} img {listing_image_id}: {response.text[:300]}")
            response.raise_for_status()
            return response.json()
