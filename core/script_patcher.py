import re
from pathlib import Path

# Image extensions → .avif
_IMG_PATTERN = re.compile(rb"\.(png|webp|jpg|jpeg|bmp|tga)", re.IGNORECASE)

# Video extensions that get re-mapped to .webm (ogv/avi/mkv/mov → webm)
_VID_REMAP_PATTERN = re.compile(rb"\.(ogv|avi|mkv|mov)", re.IGNORECASE)


def is_rpy(path: str) -> bool:
    return Path(path).suffix.lower() == ".rpy"


def is_rpyc(path: str) -> bool:
    return Path(path).suffix.lower() == ".rpyc"


def patch_rpy(content: bytes) -> bytes:
    """Replace image and remapped video extension references in a .rpy source file."""
    content = _IMG_PATTERN.sub(b".avif", content)
    content = _VID_REMAP_PATTERN.sub(b".webm", content)
    return content
