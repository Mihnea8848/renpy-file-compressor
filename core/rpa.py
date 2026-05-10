import io
import os
import pickle
import zlib
from pathlib import Path
from typing import Generator

_RPA3_MAGIC = b"RPA-3.0 "
_INDEX_KEY = 0x42424242


def _parse_header(f: io.RawIOBase) -> tuple[int, int]:
    line = f.readline()
    if not line.startswith(_RPA3_MAGIC):
        raise ValueError(f"Not an RPA-3.0 archive (got: {line[:20]!r})")
    parts = line.split()
    offset = int(parts[1], 16)
    key = int(parts[2], 16)
    return offset, key


def _read_index(f: io.RawIOBase, offset: int, key: int) -> dict[str, list[tuple[int, int, bytes]]]:
    f.seek(offset)
    raw = f.read()
    index = pickle.loads(zlib.decompress(raw))
    result = {}
    for path, entries in index.items():
        decoded = []
        for entry in entries:
            o, l = entry[0] ^ key, entry[1] ^ key
            prefix = entry[2] if len(entry) > 2 else b""
            decoded.append((o, l, prefix))
        result[path] = decoded
    return result


def iter_files(rpa_path: str | Path) -> Generator[tuple[str, bytes], None, None]:
    """Yield (internal_path, file_bytes) for every entry in the archive."""
    with open(rpa_path, "rb") as f:
        offset, key = _parse_header(f)
        index = _read_index(f, offset, key)
        for path, entries in index.items():
            parts = []
            for o, l, prefix in entries:
                f.seek(o)
                parts.append(prefix + f.read(l - len(prefix)))
            yield path, b"".join(parts)


def get_index(rpa_path: str | Path) -> dict[str, list[tuple[int, int, bytes]]]:
    """Return the decoded index dict without reading file data."""
    with open(rpa_path, "rb") as f:
        offset, key = _parse_header(f)
        return _read_index(f, offset, key)


def write_rpa(output_path: str | Path, files: dict[str, bytes]) -> None:
    """Write a new RPA-3.0 archive from {internal_path: bytes}."""
    key = _INDEX_KEY
    header_placeholder = f"RPA-3.0 {'0' * 16} {key:08x}\n".encode()

    index: dict[str, list[tuple[int, int, bytes]]] = {}

    with open(output_path, "wb") as f:
        f.write(header_placeholder)
        for path, data in files.items():
            start = f.tell()
            f.write(data)
            length = len(data)
            index[path] = [(start ^ key, length ^ key, b"")]

        index_offset = f.tell()
        f.write(zlib.compress(pickle.dumps(index, protocol=2)))

        f.seek(0)
        f.write(f"RPA-3.0 {index_offset:016x} {key:08x}\n".encode())


def rpa_original_size(rpa_path: str | Path) -> int:
    return os.path.getsize(rpa_path)
