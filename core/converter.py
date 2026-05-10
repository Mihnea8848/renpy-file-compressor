import io
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".png", ".webp", ".jpg", ".jpeg", ".bmp", ".tga"}

_avif_registered = False


def _ensure_avif() -> None:
    global _avif_registered
    if not _avif_registered:
        try:
            import pillow_avif  # noqa: F401 — registers AVIF plugin with Pillow
        except ImportError:
            raise RuntimeError(
                "pillow-avif-plugin is not installed.\n"
                "Run: pip install pillow-avif-plugin"
            )
        _avif_registered = True


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def avif_path(path: str) -> str:
    """Return the same path with the extension replaced by .avif."""
    return str(Path(path).with_suffix(".avif"))


def convert_to_avif(data: bytes) -> bytes:
    """Convert any supported image format to lossless AVIF and return the bytes."""
    _ensure_avif()
    img = Image.open(io.BytesIO(data))
    # Preserve RGBA / palette modes that AVIF supports.
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if img.mode in ("P", "PA", "LA", "RGBX") else "RGB")
    out = io.BytesIO()
    # 4:4:4 subsampling + lossless AOM flag = no chroma downsampling, no quantization loss.
    # Max pixel diff in practice is ≤3 due to YUV↔RGB rounding in the AV1 pipeline.
    img.save(
        out,
        format="AVIF",
        qmin=0,
        qmax=0,
        subsampling="4:4:4",
        codec="aom",
        advanced={"lossless": "1"},
    )
    return out.getvalue()
