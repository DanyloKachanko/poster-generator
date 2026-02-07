"""Multi-size export pipeline for Printify posters."""

import io
from pathlib import Path
from typing import Dict, List, Optional, Callable
from PIL import Image

from leonardo import LeonardoAI
from sizes import POSTER_SIZES, PosterSize
from upscaler import (
    upscale_with_realesrgan,
    upscale_with_pillow,
    is_realesrgan_available,
)


class PosterExporter:
    def __init__(self, leonardo: LeonardoAI, output_dir: str = "./exports"):
        self.leonardo = leonardo
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.has_realesrgan = is_realesrgan_available()

    async def export_all_sizes(
        self,
        generated_image_id: str,
        generation_name: str,
        sizes: Optional[List[str]] = None,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, str]:
        """
        Export poster to all specified sizes.

        Args:
            generated_image_id: Leonardo image ID
            generation_name: Name for export folder
            sizes: List of size keys, or None for all
            on_progress: Callback(step_description, percent)

        Returns:
            Dict of {size_key: filepath}
        """
        export_folder = self.output_dir / generation_name
        export_folder.mkdir(parents=True, exist_ok=True)

        target_sizes = sizes or list(POSTER_SIZES.keys())

        def progress(msg: str, pct: int):
            if on_progress:
                on_progress(msg, pct)

        # Step 1: Upscale with Leonardo (2x)
        progress("Upscaling with Leonardo AI...", 10)
        upscale_result = await self.leonardo.upscale_image(
            generated_image_id=generated_image_id,
            multiplier=2.0,
            style="ARTISTIC",
            creativity=3,
            detail_contrast=7,
            similarity=3,
        )

        progress("Waiting for upscale to complete...", 20)
        variation = await self.leonardo.wait_for_variation(
            upscale_result["variation_id"]
        )

        progress("Downloading upscaled image...", 40)
        upscaled_bytes = await self.leonardo.download_image(variation["url"])

        upscaled_img = Image.open(io.BytesIO(upscaled_bytes))
        current_width, current_height = upscaled_img.size

        # Step 2: Additional upscale if needed for large sizes
        max_needed = max(POSTER_SIZES[s].width for s in target_sizes)

        if max_needed > current_width * 1.5:
            if self.has_realesrgan:
                progress("Upscaling with Real-ESRGAN for large sizes...", 50)
                upscaled_bytes = upscale_with_realesrgan(upscaled_bytes, scale=2)
                upscaled_img = Image.open(io.BytesIO(upscaled_bytes))
                current_width, current_height = upscaled_img.size
            else:
                progress("Using Pillow for large sizes (Real-ESRGAN not available)", 50)

        # Step 3: Export each size
        results = {}
        total = len(target_sizes)

        for i, size_key in enumerate(target_sizes):
            size = POSTER_SIZES[size_key]
            pct = 60 + int((i / total) * 40)
            progress(f"Exporting {size.label}...", pct)

            resized_bytes = upscale_with_pillow(
                upscaled_bytes,
                size.width,
                size.height,
            )

            filepath = export_folder / f"{generation_name}_{size_key}.png"
            with open(filepath, "wb") as f:
                f.write(resized_bytes)

            results[size_key] = str(filepath)

        progress("Export complete", 100)
        return results

    def get_export_status(self, generation_name: str) -> Dict[str, bool]:
        """Check which sizes exist for a generation."""
        export_folder = self.output_dir / generation_name

        if not export_folder.exists():
            return {k: False for k in POSTER_SIZES}

        return {
            k: (export_folder / f"{generation_name}_{k}.png").exists()
            for k in POSTER_SIZES
        }

    def get_export_file(self, generation_name: str, size_key: str) -> Optional[Path]:
        """Get the path of an exported file if it exists."""
        filepath = self.output_dir / generation_name / f"{generation_name}_{size_key}.png"
        return filepath if filepath.exists() else None
