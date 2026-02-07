"""Local upscaling using Real-ESRGAN for sizes > 20MP, with Pillow fallback."""

import subprocess
import tempfile
from pathlib import Path
from PIL import Image
import io

REALESRGAN_PATH = "realesrgan-ncnn-vulkan"


def fit_image_to_ratio(
    image_bytes: bytes,
    target_ratio: float,
) -> bytes:
    """Center-crop image to match a target aspect ratio (w/h).

    If source is wider than target ratio: crops left/right.
    If source is narrower: crops top/bottom.
    Returns original bytes if ratio already matches (within 1% tolerance).
    """
    img = Image.open(io.BytesIO(image_bytes))
    src_w, src_h = img.size
    src_ratio = src_w / src_h

    if abs(src_ratio - target_ratio) < 0.01:
        return image_bytes

    if src_ratio > target_ratio:
        # Source wider → crop left/right
        new_w = round(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        # Source narrower → crop top/bottom
        new_h = round(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def is_realesrgan_available() -> bool:
    """Check if Real-ESRGAN CLI is installed."""
    try:
        result = subprocess.run(
            [REALESRGAN_PATH, "-h"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def upscale_with_realesrgan(
    image_bytes: bytes,
    scale: int = 2,
    model: str = "realesrgan-x4plus",
) -> bytes:
    """Upscale image using Real-ESRGAN CLI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.png"
        output_path = Path(tmpdir) / "output.png"

        with open(input_path, "wb") as f:
            f.write(image_bytes)

        cmd = [
            REALESRGAN_PATH,
            "-i", str(input_path),
            "-o", str(output_path),
            "-s", str(scale),
            "-n", model,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)

        if result.returncode != 0:
            raise Exception(f"Real-ESRGAN failed: {result.stderr.decode()}")

        with open(output_path, "rb") as f:
            return f.read()


def upscale_with_pillow(
    image_bytes: bytes,
    target_width: int,
    target_height: int,
) -> bytes:
    """High-quality resize using Pillow LANCZOS."""
    img = Image.open(io.BytesIO(image_bytes))
    resized = img.resize((target_width, target_height), Image.LANCZOS)

    output = io.BytesIO()
    resized.save(output, format="PNG", optimize=True)
    return output.getvalue()


class UpscaleService:
    """Unified upscaling service.

    Uses Real-ESRGAN (if binary available) for AI-quality integer-scale
    upscaling, then Pillow LANCZOS for precise final resize.
    Falls back to Pillow-only when Real-ESRGAN is absent.
    """

    MAX_SCALE_FACTOR = 4.0

    def __init__(self):
        self.has_realesrgan = is_realesrgan_available()

    def get_image_dimensions(self, image_bytes: bytes) -> tuple:
        """Return (width, height) of the image."""
        img = Image.open(io.BytesIO(image_bytes))
        return img.size

    def upscale_to_target(
        self,
        image_bytes: bytes,
        target_width: int,
        target_height: int,
    ) -> bytes:
        """Upscale image to exact target dimensions.

        Strategy:
        1. Calculate required scale factor
        2. If Real-ESRGAN available and factor > 1.5, use it for 2x passes
        3. Final Pillow LANCZOS resize to exact target
        4. If factor > MAX_SCALE_FACTOR, AI upscale is capped but Pillow
           still resizes to target (lower DPI but still sellable)
        """
        src_w, src_h = self.get_image_dimensions(image_bytes)
        factor = max(target_width / src_w, target_height / src_h)

        if factor <= 1.0:
            return upscale_with_pillow(image_bytes, target_width, target_height)

        working = image_bytes

        if self.has_realesrgan and factor > 1.5:
            # First Real-ESRGAN 2x pass
            working = upscale_with_realesrgan(working, scale=2)

            # Check if a second 2x pass is needed
            cur_w, cur_h = self.get_image_dimensions(working)
            remaining = max(target_width / cur_w, target_height / cur_h)
            if remaining > 1.5:
                working = upscale_with_realesrgan(working, scale=2)

        # Final precise resize
        return upscale_with_pillow(working, target_width, target_height)

    @property
    def backend_name(self) -> str:
        return "Real-ESRGAN + Pillow" if self.has_realesrgan else "Pillow LANCZOS"
