"""Printify API integration for automated product creation"""

import os
import base64
import httpx
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class PrintifyVariant:
    variant_id: int
    price: int  # in cents
    is_enabled: bool = True


@dataclass
class PrintifyProduct:
    id: str
    title: str
    status: str
    variants: List[dict]


@dataclass
class DesignGroup:
    """A group of variant IDs sharing the same image on Printify."""
    image_id: str
    variant_ids: List[int] = field(default_factory=list)


class PrintifyAPI:
    """Printify API client for product automation"""

    BASE_URL = "https://api.printify.com/v1"

    # Matte Vertical Posters blueprint ID (verify in catalog)
    MATTE_VERTICAL_BLUEPRINT_ID = 282

    # Print provider ID (Printify Choice = 99)
    PRINT_PROVIDER_ID = 99

    # Variant IDs per size (blueprint 282 + provider 99)
    SIZE_VARIANT_IDS = {
        "8x10": 114557,
        "11x14": 43135,
        "12x16": 101110,
        "16x20": 43141,
        "18x24": 43144,
        "24x36": 43150,
    }

    # Sizes safe to sell without upscaling (Leonardo generates ~1024x1280).
    # 16x20+ need Real-ESRGAN or similar 4x upscale first — re-enable after
    # adding the upscale step to the pipeline.
    ENABLED_SIZES = {"8x10", "11x14", "12x16"}

    def __init__(
        self,
        api_token: Optional[str] = None,
        shop_id: Optional[str] = None,
    ):
        self.api_token = api_token or os.getenv("PRINTIFY_API_TOKEN", "")
        self.shop_id = shop_id or os.getenv("PRINTIFY_SHOP_ID", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token and self.shop_id)

    async def get_shops(self) -> List[dict]:
        """Get list of shops."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops.json",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def upload_image(self, image_url: str, filename: str) -> dict:
        """Upload image to Printify from URL."""
        payload = {
            "file_name": filename,
            "url": image_url,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/uploads/images.json",
                headers=self.headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_blueprint_variants(
        self,
        blueprint_id: int = MATTE_VERTICAL_BLUEPRINT_ID,
        print_provider_id: int = PRINT_PROVIDER_ID,
    ) -> List[dict]:
        """Get available variants for a blueprint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json().get("variants", [])

    async def create_product(
        self,
        title: str,
        description: str,
        tags: List[str],
        image_id: str,
        variants: List[PrintifyVariant],
        blueprint_id: int = MATTE_VERTICAL_BLUEPRINT_ID,
        print_provider_id: int = PRINT_PROVIDER_ID,
    ) -> PrintifyProduct:
        """Create a new product in Printify."""
        variants_payload = [
            {
                "id": v.variant_id,
                "price": v.price,
                "is_enabled": v.is_enabled,
            }
            for v in variants
        ]

        from sizes import PRINTIFY_SCALE_DEFAULT
        print_areas = [
            {
                "variant_ids": [v.variant_id for v in variants],
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": image_id,
                                "x": 0.5,
                                "y": 0.5,
                                "scale": PRINTIFY_SCALE_DEFAULT,
                                "angle": 0,
                            }
                        ],
                    }
                ],
            }
        ]

        payload = {
            "title": title,
            "description": description,
            "tags": tags,
            "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id,
            "variants": variants_payload,
            "print_areas": print_areas,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/shops/{self.shop_id}/products.json",
                headers=self.headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            product_id = data["id"]

            # Printify ignores tags on POST create — set them via PUT
            if tags:
                await client.put(
                    f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json",
                    headers=self.headers,
                    json={"tags": tags},
                    timeout=30.0,
                )

            return PrintifyProduct(
                id=product_id,
                title=data["title"],
                status=data.get("status", "draft"),
                variants=data.get("variants", []),
            )

    async def publish_product(self, product_id: str) -> dict:
        """Publish product to connected store (Etsy)."""
        payload = {
            "title": True,
            "description": True,
            "images": True,
            "variants": True,
            "tags": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}/publish.json",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_product(self, product_id: str) -> dict:
        """Get product details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def list_products(self, page: int = 1, limit: int = 20) -> dict:
        """List products in shop (paginated)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/shops/{self.shop_id}/products.json",
                headers=self.headers,
                params={"page": page, "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product from Printify."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return True

    async def unpublish_product(self, product_id: str) -> dict:
        """Unpublish product from connected store."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}/unpublish.json",
                headers=self.headers,
                json={},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def update_product(
        self,
        product_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        variants: Optional[List[dict]] = None,
        print_areas: Optional[List[dict]] = None,
    ) -> dict:
        """Update an existing product. Only sends non-None fields."""
        payload = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if tags is not None:
            payload["tags"] = tags
        if variants is not None:
            payload["variants"] = variants
        if print_areas is not None:
            payload["print_areas"] = print_areas

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json",
                headers=self.headers,
                json=payload,
                timeout=60.0,
            )
            if response.status_code >= 400:
                raise Exception(
                    f"Printify update failed ({response.status_code}): {response.text[:1000]}"
                )
            return response.json()


    async def upload_image_base64(self, image_bytes: bytes, filename: str) -> dict:
        """Upload image to Printify from raw bytes (base64 encoded).

        Converts to JPEG before encoding to keep payload size manageable.
        """
        import io as _io
        from PIL import Image as _Image

        # Convert to JPEG to reduce size (PNG can be 10x larger)
        img = _Image.open(_io.BytesIO(image_bytes))
        if img.mode == "RGBA":
            img = img.convert("RGB")
        jpeg_buf = _io.BytesIO()
        img.save(jpeg_buf, format="JPEG", quality=95, optimize=True)
        jpeg_bytes = jpeg_buf.getvalue()

        b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
        jpg_filename = filename.rsplit(".", 1)[0] + ".jpg"
        payload = {
            "file_name": jpg_filename,
            "contents": b64,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/uploads/images.json",
                headers=self.headers,
                json=payload,
            )
            if response.status_code != 200:
                raise Exception(
                    f"Printify upload failed ({response.status_code}): {response.text[:500]}"
                )
            return response.json()

    async def create_product_multidesign(
        self,
        title: str,
        description: str,
        tags: List[str],
        design_groups: List[DesignGroup],
        variants: List[PrintifyVariant],
        blueprint_id: int = MATTE_VERTICAL_BLUEPRINT_ID,
        print_provider_id: int = PRINT_PROVIDER_ID,
    ) -> PrintifyProduct:
        """Create product with per-variant designs (different images per size group).

        Each DesignGroup maps a Printify image_id to a set of variant_ids,
        allowing different resolution images for different poster sizes.
        """
        variants_payload = [
            {"id": v.variant_id, "price": v.price, "is_enabled": v.is_enabled}
            for v in variants
        ]

        from sizes import PRINTIFY_SCALE, PRINTIFY_SCALE_DEFAULT
        vid_to_size = {vid: sk for sk, vid in self.SIZE_VARIANT_IDS.items()}
        print_areas = []
        for group in design_groups:
            size_key = vid_to_size.get(group.variant_ids[0]) if len(group.variant_ids) == 1 else None
            scale = PRINTIFY_SCALE.get(size_key, PRINTIFY_SCALE_DEFAULT) if size_key else PRINTIFY_SCALE_DEFAULT
            print_areas.append({
                "variant_ids": group.variant_ids,
                "placeholders": [{
                    "position": "front",
                    "images": [{
                        "id": group.image_id,
                        "x": 0.5,
                        "y": 0.5,
                        "scale": scale,
                        "angle": 0,
                    }],
                }],
            })

        payload = {
            "title": title,
            "description": description,
            "tags": tags,
            "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id,
            "variants": variants_payload,
            "print_areas": print_areas,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/shops/{self.shop_id}/products.json",
                headers=self.headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            product_id = data["id"]

            # Printify ignores tags on POST — set via PUT
            if tags:
                await client.put(
                    f"{self.BASE_URL}/shops/{self.shop_id}/products/{product_id}.json",
                    headers=self.headers,
                    json={"tags": tags},
                    timeout=30.0,
                )

            return PrintifyProduct(
                id=product_id,
                title=data["title"],
                status=data.get("status", "draft"),
                variants=data.get("variants", []),
            )

    async def disable_variants(
        self,
        product_id: str,
        variant_ids_to_disable: List[int],
    ) -> dict:
        """Disable specific variants on a product."""
        product = await self.get_product(product_id)
        updated_variants = []
        for v in product.get("variants", []):
            updated_variants.append({
                "id": v["id"],
                "price": v["price"],
                "is_enabled": v["id"] not in variant_ids_to_disable,
            })
        return await self.update_product(
            product_id=product_id,
            variants=updated_variants,
        )


def create_variants_from_prices(prices: dict, enabled_sizes: set = None) -> List[PrintifyVariant]:
    """Create PrintifyVariant list from pricing dict.

    Only enables sizes listed in ENABLED_SIZES to avoid selling
    blurry prints at sizes that exceed our source resolution.
    """
    variants = []

    if enabled_sizes is None:
        enabled_sizes = PrintifyAPI.ENABLED_SIZES

    for size, price_info in prices.items():
        variant_id = PrintifyAPI.SIZE_VARIANT_IDS.get(size)
        if variant_id:
            is_enabled = size in enabled_sizes
            price_cents = int(price_info["recommended_price"] * 100)
            variants.append(
                PrintifyVariant(
                    variant_id=variant_id,
                    price=price_cents,
                    is_enabled=is_enabled,
                )
            )

    return variants
