from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.converter import IMAGE_EXTS, is_image
from core.rpa import get_index
from core.script_patcher import is_rpy, is_rpyc
from core.video_converter import is_video
from gui.wizard import C_ACCENT, C_TEXT, C_TEXT_SUB, C_WHITE

if TYPE_CHECKING:
    from gui.wizard import Wizard

_RPA3_MAGIC = b"RPA-3.0 "


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _verify_renpy(path: Path) -> tuple[bool, str]:
    """Return (ok, error_message). Runs multiple checks."""
    if not (path / "game").is_dir():
        return False, "No /game/ directory found."
    if not (path / "renpy").is_dir():
        return False, "No /renpy/ directory found."

    # The renpy/common/ directory is only present in full Ren'Py engine bundles
    has_common = (path / "renpy" / "common").is_dir()
    has_config  = (path / "renpy" / "config.py").is_file()
    if not (has_common or has_config):
        return False, "No Ren'Py engine files found in /renpy/ (expected common/ or config.py)."

    game_dir = path / "game"

    # Look for RPA archives
    rpas = list(game_dir.glob("*.rpa"))
    if not rpas:
        return False, "No .rpa archive files found in /game/."

    # Verify at least one .rpa has a valid RPA-3.0 header
    valid_rpa = False
    for rpa in rpas:
        try:
            with open(rpa, "rb") as f:
                header = f.read(8)
            if header == _RPA3_MAGIC:
                valid_rpa = True
                break
        except OSError:
            continue
    if not valid_rpa:
        return False, "No valid RPA-3.0 archives found — this may not be a Ren'Py game."

    # Optional: check script_version.txt (Ren'Py 8 signature)
    # If it's absent we still pass; it only exists in 8+
    return True, ""


class ValidatePage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=C_WHITE, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color="#003087", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="Analysing Game",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#ffffff", anchor="w").place(x=28, y=14)
        self._header_sub = ctk.CTkLabel(
            header, text="Scanning archives…",
            font=ctk.CTkFont(size=12), text_color="#c8d6e5", anchor="w")
        self._header_sub.place(x=28, y=44)

        ctk.CTkFrame(self, height=1, fg_color="#d0d0d0", corner_radius=0).grid(
            row=1, column=0, sticky="ew")

        # Spinner
        self._spinner = ctk.CTkProgressBar(self, mode="indeterminate",
                                            height=4, corner_radius=0,
                                            fg_color="#e8e8e8", progress_color=C_ACCENT)
        self._spinner.grid(row=2, column=0, sticky="ew")
        self._spinner.start()

        # Scrollable results
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=C_WHITE, corner_radius=0,
            scrollbar_fg_color="#f0f0f0", scrollbar_button_color="#c0c0c0",
        )
        self._scroll.grid(row=3, column=0, sticky="nsew", padx=32, pady=(16, 8))
        self._scroll.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self._warn = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11),
            text_color="#c0392b", anchor="w", justify="left")
        self._warn.grid(row=4, column=0, padx=32, pady=(0, 8), sticky="w")

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._wizard.set_next_enabled(False)
        self._clear_table()
        self._spinner.grid()
        self._spinner.start()
        self._header_sub.configure(text="Verifying game and scanning archives…")
        self._warn.configure(text="")
        threading.Thread(target=self._scan, daemon=True).start()

    def on_next(self) -> None:
        self._wizard.navigate_to("compress")

    # ── Scan ───────────────────────────────────────────────────────────────
    def _scan(self) -> None:
        folder = Path(self._wizard.app_state["game_folder"])

        ok, err = _verify_renpy(folder)
        if not ok:
            self.after(0, self._show_error, err)
            return

        game_dir = folder / "game"
        rpas = sorted(game_dir.glob("*.rpa"))
        results = []
        warnings = []

        for rpa_path in rpas:
            try:
                index = get_index(rpa_path)
            except Exception as e:
                warnings.append(f"Could not read {rpa_path.name}: {e}")
                continue

            img_count   = sum(1 for p in index if is_image(p))
            vid_count   = sum(1 for p in index if is_video(p))
            rpy_count   = sum(1 for p in index if is_rpy(p))
            rpyc_count  = sum(1 for p in index if is_rpyc(p))
            size_bytes  = rpa_path.stat().st_size

            results.append({
                "name":     rpa_path.name,
                "size":     size_bytes,
                "images":   img_count,
                "videos":   vid_count,
                "scripts":  rpy_count,
                "bytecode": rpyc_count,
                "path":     rpa_path,
            })

        total_images = sum(r["images"] for r in results)
        total_videos = sum(r["videos"] for r in results)

        if not any(r["scripts"] for r in results):
            warnings.append(
                "No .rpy script files found — image/video paths in scripts won't be updated."
            )

        self._wizard.app_state["scan_results"] = results
        self.after(0, self._show_results, results, warnings, total_images, total_videos)

    def _clear_table(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()

    def _show_error(self, msg: str) -> None:
        self._spinner.stop()
        self._spinner.grid_remove()
        self._header_sub.configure(text="Validation failed.")
        self._warn.configure(text=f"⚠  {msg}")

    def _show_results(
        self, results: list, warnings: list, total_images: int, total_videos: int
    ) -> None:
        self._spinner.stop()
        self._spinner.grid_remove()

        total_size = sum(r["size"] for r in results)
        self._header_sub.configure(
            text=f"{len(results)} archive(s)  •  "
                 f"{total_images} images  •  "
                 f"{total_videos} video(s)  •  "
                 f"{_fmt_size(total_size)} total"
        )

        # Table header
        headers = ["Archive", "Size", "Images", "Videos", "Scripts (.rpy)"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(
                self._scroll, text=h,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=C_TEXT_SUB,
            ).grid(row=0, column=col, padx=(10, 4), pady=(4, 6), sticky="w")

        # Thin header underline
        sep = ctk.CTkFrame(self._scroll, height=1, fg_color="#d0d0d0", corner_radius=0)
        sep.grid(row=1, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 4))

        for i, r in enumerate(results):
            row_bg = "#f7f9fc" if i % 2 == 0 else C_WHITE
            row_vals = [
                r["name"],
                _fmt_size(r["size"]),
                str(r["images"]) if r["images"] else "—",
                str(r["videos"]) if r["videos"] else "—",
                str(r["scripts"]) if r["scripts"] else "—",
            ]
            for col, val in enumerate(row_vals):
                ctk.CTkLabel(
                    self._scroll, text=val,
                    font=ctk.CTkFont(size=11),
                    text_color=C_TEXT if col == 0 else C_TEXT_SUB,
                    fg_color=row_bg,
                ).grid(row=i + 2, column=col, padx=(10, 4), pady=3, sticky="w")

        if warnings:
            self._warn.configure(text="  •  ".join(warnings))

        can_compress = total_images > 0 or total_videos > 0
        if can_compress:
            self._wizard.set_next_enabled(True)
        else:
            self._warn.configure(
                text="No images or videos found in any archive — nothing to compress."
            )
