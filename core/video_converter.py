import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

VIDEO_EXTS = {".webm", ".mp4", ".ogv", ".avi", ".mkv", ".mov"}

# Extensions that must change container to .webm after AV1 re-encode.
# .webm and .mp4 keep their extension; legacy formats are promoted to .webm.
_REMAP_TO_WEBM = {".ogv", ".avi", ".mkv", ".mov"}


def is_video(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTS


def av1_path(path: str) -> str:
    """Return the output path — same extension for .webm/.mp4, else .webm."""
    p = Path(path)
    if p.suffix.lower() in _REMAP_TO_WEBM:
        return str(p.with_suffix(".webm"))
    return path


def _choose_encoder() -> str:
    """Pick the fastest available AV1 encoder."""
    for enc in ("libsvtav1", "librav1e", "libaom-av1"):
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True,
        )
        if enc in result.stdout:
            return enc
    return "libaom-av1"


_ENCODER: str | None = None


def _encoder() -> str:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = _choose_encoder()
    return _ENCODER


def convert_to_av1(data: bytes, src_ext: str) -> bytes:
    """Transcode video bytes to AV1/Opus in a WebM or MP4 container."""
    enc = _encoder()
    in_suffix = src_ext.lower()
    out_suffix = ".webm" if in_suffix in _REMAP_TO_WEBM or in_suffix == ".webm" else ".mp4"

    # CRF / preset vary by encoder
    if enc == "libsvtav1":
        video_args = ["-c:v", enc, "-crf", "35", "-preset", "8", "-svtav1-params", "tune=0"]
    elif enc == "librav1e":
        video_args = ["-c:v", enc, "-qp", "80", "-speed", "6"]
    else:  # libaom-av1
        video_args = ["-c:v", enc, "-crf", "35", "-b:v", "0", "-cpu-used", "4"]

    audio_args = ["-c:a", "libopus", "-b:a", "128k"]
    fmt = "webm" if out_suffix == ".webm" else "mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path  = os.path.join(tmpdir, f"input{in_suffix}")
        out_path = os.path.join(tmpdir, f"output{out_suffix}")

        with open(in_path, "wb") as f:
            f.write(data)

        cmd = (
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", in_path]
            + video_args
            + audio_args
            + ["-f", fmt, out_path]
        )
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed ({result.returncode}):\n"
                + result.stderr.decode(errors="replace")
            )

        with open(out_path, "rb") as f:
            return f.read()
