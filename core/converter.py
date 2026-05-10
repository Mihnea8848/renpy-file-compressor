import io
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()  # registers AVIF/HEIF support with Pillow globally

IMAGE_EXTS = {".png", ".webp", ".jpg", ".jpeg", ".bmp", ".tga"}


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def avif_path(path: str) -> str:
    """Return the same path with the extension replaced by .avif."""
    return str(Path(path).with_suffix(".avif"))


def convert_to_avif(data: bytes) -> bytes:
    """Convert any supported image format to high-quality AVIF and return the bytes."""
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if img.mode in ("P", "PA", "LA", "RGBX") else "RGB")
    out = io.BytesIO()
    try:
        img.save(out, format="AVIF", quality=85, speed=6, chroma="444")
    except Exception:
        out = io.BytesIO()
        img.save(out, format="AVIF", quality=85, speed=6)
    return out.getvalue()
