"""DovShop API integration for product publishing"""

import os
import httpx
from typing import Optional, List, Dict, Any


class DovShopClient:
    """DovShop API client for product management"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("DOVSHOP_API_KEY", "")
        self.base_url = (base_url or os.getenv("DOVSHOP_API_URL", "http://localhost:3000/api")).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        """Check if DovShop API is properly configured"""
        return bool(self.api_key and self.base_url)

    async def health_check(self) -> dict:
        """Check DovShop API connection"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self.headers,
                    timeout=15.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_products(self) -> List[dict]:
        """Get all posters from DovShop"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/posters",
                headers=self.headers,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("posters", data.get("products", []))

    async def push_product(
        self,
        name: str,
        images: list[str],
        etsy_url: str = "",
        featured: bool = False,
        description: str = "",
        tags: list[str] | None = None,
        price: float = 0,
        external_id: str = "",
        preferred_mockup_url: str = "",
    ) -> dict:
        """Create a new poster/product on DovShop.

        Args:
            name: Product name
            images: List of image URLs/paths
            etsy_url: Etsy listing URL
            featured: Whether to feature the product
            description: Product description
            tags: Product tags
            price: Product price
            external_id: Printify product ID for cross-referencing

        Returns:
            Created product data with DovShop product ID
        """
        payload: dict = {
            "name": name,
            "images": images,
            "etsy_url": etsy_url,
            "featured": featured,
        }
        if description:
            payload["description"] = description
        if tags:
            payload["tags"] = tags
        if price:
            payload["price"] = price
        if external_id:
            payload["external_id"] = external_id
        if preferred_mockup_url:
            payload["preferred_mockup_url"] = preferred_mockup_url

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/posters",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def update_product(self, product_id: str, data: dict) -> dict:
        """Update an existing poster on DovShop

        Args:
            product_id: DovShop poster ID
            data: Updated poster data

        Returns:
            Updated poster data
        """
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/posters/{product_id}",
                headers=self.headers,
                json=data,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def delete_product(self, product_id: str) -> bool:
        """Delete a poster from DovShop

        Args:
            product_id: DovShop poster ID

        Returns:
            True if deletion was successful
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/posters/{product_id}",
                headers=self.headers,
                timeout=15.0,
            )
            response.raise_for_status()
            return True

    async def upload_image(self, image_url: str, filename: str) -> dict:
        """Upload image to DovShop

        Downloads image from provided URL and uploads it to DovShop.

        Args:
            image_url: URL of the image to upload
            filename: Filename for the uploaded image

        Returns:
            Upload response with DovShop image URL
        """
        # Step 1: Download image from URL
        async with httpx.AsyncClient() as client:
            download_response = await client.get(
                image_url,
                timeout=60.0,
                follow_redirects=True,
            )
            download_response.raise_for_status()
            image_content = download_response.content

        # Step 2: Upload to DovShop
        async with httpx.AsyncClient() as client:
            files = {"file": (filename, image_content, "image/png")}
            response = await client.post(
                f"{self.base_url}/upload",
                headers={"Authorization": f"Bearer {self.api_key}"},  # No Content-Type for multipart
                files=files,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_collections(self) -> List[dict]:
        """Get all collections from DovShop"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/collections",
                headers=self.headers,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("collections", [])

    async def create_collection(
        self,
        name: str,
        description: str = "",
        cover_url: str = "",
    ) -> dict:
        """Create a new collection on DovShop

        Args:
            name: Collection name
            description: Collection description
            cover_url: URL to cover image

        Returns:
            Created collection data with DovShop collection ID
        """
        payload = {
            "name": name,
            "description": description,
            "cover_url": cover_url,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/collections",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection from DovShop

        Args:
            collection_id: DovShop collection ID

        Returns:
            True if deletion was successful
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/collections/{collection_id}",
                headers=self.headers,
                timeout=15.0,
            )
            response.raise_for_status()
            return True

    async def get_categories(self) -> List[dict]:
        """Get all categories from DovShop"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/categories",
                headers=self.headers,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("categories", [])

    async def bulk_sync(self, posters: list[dict]) -> dict:
        """Bulk sync posters to DovShop.

        Args:
            posters: List of poster dicts with name, images, tags, categories, etc.

        Returns:
            Sync result with created/updated counts
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sync",
                headers=self.headers,
                json={"posters": posters},
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()
