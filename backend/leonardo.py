import httpx
import asyncio
from typing import Optional


class LeonardoAI:
    """Wrapper class for Leonardo AI API."""

    BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

    # Default model ID (Phoenix 1.0)
    DEFAULT_MODEL = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
    DEFAULT_NEGATIVE_PROMPT = "text, watermark, signature, blurry, low quality"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def create_generation(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1280,
        num_images: int = 4,
        model_id: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        ultra: bool = False,
    ) -> dict:
        """
        Start a new image generation.

        Args:
            prompt: The text prompt for image generation
            width: Image width in pixels
            height: Image height in pixels
            num_images: Number of images to generate (1-4)
            model_id: Leonardo model ID to use
            negative_prompt: Things to avoid in the image
            ultra: Enable Ultra mode (Phoenix only, ~5MP output, costs more credits)

        Returns:
            dict with generation_id and initial status
        """
        payload = {
            "prompt": prompt,
            "modelId": model_id or self.DEFAULT_MODEL,
            "width": width,
            "height": height,
            "num_images": min(max(num_images, 1), 2),  # Clamp between 1-2 (API limit)
            "negative_prompt": negative_prompt or self.DEFAULT_NEGATIVE_PROMPT,
            "public": False,
        }

        if ultra:
            payload["ultra"] = True

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/generations",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            generation_id = data.get("sdGenerationJob", {}).get("generationId")
            if not generation_id:
                raise ValueError("No generation ID returned from API")

            return {
                "generation_id": generation_id,
                "status": "PENDING",
            }

    async def get_generation(self, generation_id: str) -> dict:
        """
        Get the status and results of a generation.

        Args:
            generation_id: The ID of the generation to check

        Returns:
            dict with generation_id, status, images (if complete), and api_credit_cost
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/generations/{generation_id}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            generation = data.get("generations_by_pk", {})
            status = generation.get("status", "PENDING")
            api_credit_cost = generation.get("apiCreditCost", 0)

            images = []
            if status == "COMPLETE":
                for img in generation.get("generated_images", []):
                    images.append({
                        "id": img.get("id"),
                        "url": img.get("url"),
                    })

            return {
                "generation_id": generation_id,
                "status": status,
                "images": images,
                "api_credit_cost": api_credit_cost,
            }

    async def get_user_info(self) -> dict:
        """Get current user info including remaining API tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/me",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            user_details = data.get("user_details", [{}])[0]
            api_sub = user_details.get("apiSubscriptionTokens") or 0
            api_paid = user_details.get("apiPaidTokens") or 0
            sub_tokens = user_details.get("subscriptionTokens") or 0
            paid_tokens = user_details.get("paidTokens") or 0

            return {
                "api_subscription_tokens": api_sub,
                "api_paid_tokens": api_paid,
                "api_total_tokens": api_sub + api_paid,
                "subscription_tokens": sub_tokens,
                "paid_tokens": paid_tokens,
                "total_tokens": sub_tokens + paid_tokens,
                "token_renewal_date": user_details.get("tokenRenewalDate"),
                "api_token_renewal_date": user_details.get("apiPlanTokenRenewalDate"),
            }

    async def upscale_image(
        self,
        generated_image_id: str,
        multiplier: float = 2.0,
        style: str = "ARTISTIC",
        creativity: int = 3,
        detail_contrast: int = 7,
        similarity: int = 3,
    ) -> dict:
        """Upscale image using Universal Upscaler Ultra Mode."""
        payload = {
            "ultraUpscaleStyle": style,
            "creativityStrength": creativity,
            "detailContrast": detail_contrast,
            "similarity": similarity,
            "upscaleMultiplier": multiplier,
            "generatedImageId": generated_image_id,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/variations/universal-upscaler",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "variation_id": data["universalUpscaler"]["id"],
                "status": "PENDING",
            }

    async def get_variation(self, variation_id: str) -> dict:
        """Get variation status and URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/variations/{variation_id}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            variations = data.get("generated_image_variation_generic", [])
            if variations:
                var = variations[0]
                return {
                    "variation_id": variation_id,
                    "status": var.get("status", "PENDING"),
                    "url": var.get("url"),
                }

            return {
                "variation_id": variation_id,
                "status": "PENDING",
                "url": None,
            }

    async def wait_for_variation(
        self,
        variation_id: str,
        max_attempts: int = 60,
        delay: float = 3.0,
    ) -> dict:
        """Poll until variation is complete."""
        for _ in range(max_attempts):
            result = await self.get_variation(variation_id)
            if result["status"] == "COMPLETE":
                return result
            elif result["status"] == "FAILED":
                raise Exception("Upscale failed")
            await asyncio.sleep(delay)

        raise Exception("Upscale timeout")

    async def download_image(self, url: str) -> bytes:
        """Download image from URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=120.0, follow_redirects=True)
            response.raise_for_status()
            return response.content

    async def wait_for_generation(
        self,
        generation_id: str,
        poll_interval: float = 2.0,
        timeout: float = 60.0,
    ) -> dict:
        """
        Poll for generation completion.

        Args:
            generation_id: The ID of the generation to wait for
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait

        Returns:
            Final generation result
        """
        elapsed = 0.0
        while elapsed < timeout:
            result = await self.get_generation(generation_id)

            if result["status"] in ("COMPLETE", "FAILED"):
                return result

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {
            "generation_id": generation_id,
            "status": "TIMEOUT",
            "images": [],
        }
