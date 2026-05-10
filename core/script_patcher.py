import re
from pathlib import Path

_EXT_PATTERN = re.compile(rb"\.(png|webp|jpg|jpeg|bmp|tga)", re.IGNORECASE)


def is_rpy(path: str) -> bool:
    return Path(path).suffix.lower() == ".rpy"


def is_rpyc(path: str) -> bool:
    return Path(path).suffix.lower() == ".rpyc"


def patch_rpy(content: bytes) -> bytes:
    """Replace image extension references in a .rpy source file with .avif."""
    return _EXT_PATTERN.sub(b".avif", content)
