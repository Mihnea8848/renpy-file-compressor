import os
import subprocess
import tempfile
from pathlib import Path

VIDEO_EXTS = {".webm", ".mp4", ".ogv", ".avi", ".mkv", ".mov"}

# Legacy containers are promoted to .webm (VP9/Opus).
_REMAP_TO_WEBM = {".ogv", ".avi", ".mkv", ".mov"}


def is_video(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTS


def video_path(path: str) -> str:
    """Return the output path — same extension for .webm/.mp4, else .webm."""
    p = Path(path)
    if p.suffix.lower() in _REMAP_TO_WEBM:
        return str(p.with_suffix(".webm"))
    return path


# Keep old name as alias so existing pickled state doesn't break
av1_path = video_path


def convert_video(data: bytes, src_ext: str) -> bytes:
    """Transcode video bytes to VP9/Opus in WebM (or keep .mp4 container).

    VP9 is used instead of AV1 because Ren'Py's statically-linked FFmpeg
    build does not include an AV1 decoder, causing a black screen at runtime.
    VP9 is natively supported and gives ~40-60% size reduction over VP8.
    """
    in_suffix = src_ext.lower()
    out_suffix = ".webm" if in_suffix in _REMAP_TO_WEBM or in_suffix == ".webm" else ".mp4"
    fmt = "webm" if out_suffix == ".webm" else "mp4"

    n_threads = str(os.cpu_count() or 4)
    video_args = [
        "-c:v", "libvpx-vp9",
        "-crf", "33",
        "-b:v", "0",          # constant-quality mode
        "-deadline", "good",
        "-cpu-used", "4",
        "-row-mt", "1",       # row-level multithreading — major VP9 speedup
        "-threads", n_threads,
        "-tile-columns", "2",
        "-frame-parallel", "1",
    ]
    audio_args = ["-c:a", "libopus", "-b:a", "128k"]

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


# Keep old name as alias
convert_to_av1 = convert_video
