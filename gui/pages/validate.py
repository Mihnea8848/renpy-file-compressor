from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.converter import IMAGE_EXTS, is_image
from core.rpa import get_index
from core.script_patcher import is_rpy, is_rpyc

if TYPE_CHECKING:
    from gui.wizard import Wizard

_BG = "#16213e"
_ACCENT = "#c0392b"
_ROW_ODD = "#1e2d45"
_ROW_EVEN = "#172338"


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class ValidatePage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=_BG, corner_radius=0)
        self._wizard = wizard
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self, text="Analysing Game",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#ffffff",
        ).grid(row=0, column=0, pady=(40, 4), padx=40, sticky="w")

        self._subtitle = ctk.CTkLabel(
            self, text="Scanning archives…",
            font=ctk.CTkFont(size=13),
            text_color="#c8d6e5",
        )
        self._subtitle.grid(row=1, column=0, pady=(0, 18), padx=40, sticky="w")

        self._spinner = ctk.CTkProgressBar(self, mode="indeterminate", width=400)
        self._spinner.grid(row=2, column=0, pady=(0, 16), padx=40, sticky="w")
        self._spinner.start()

        # Scrollable results table
        self._table_frame = ctk.CTkScrollableFrame(
            self, fg_color=_ROW_EVEN, corner_radius=6,
        )
        self._table_frame.grid(row=3, column=0, sticky="nsew", padx=40, pady=(0, 16))
        self._table_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._warning_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color="#f39c12",
        )
        self._warning_label.grid(row=4, column=0, padx=40, pady=(0, 8), sticky="w")

    def on_show(self) -> None:
        self._wizard.set_next_enabled(False)
        self._clear_table()
        self._spinner.grid()
        self._spinner.start()
        self._subtitle.configure(text="Scanning archives…")
        self._warning_label.configure(text="")
        threading.Thread(target=self._scan, daemon=True).start()

    def on_next(self) -> None:
        self._wizard.navigate_to("compress")

    # ------------------------------------------------------------------
    def _scan(self) -> None:
        folder = Path(self._wizard.app_state["game_folder"])
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

            image_count = sum(1 for p in index if is_image(p))
            rpy_count = sum(1 for p in index if is_rpy(p))
            rpyc_count = sum(1 for p in index if is_rpyc(p))
            size_bytes = rpa_path.stat().st_size

            results.append({
                "name": rpa_path.name,
                "size": size_bytes,
                "images": image_count,
                "scripts": rpy_count,
                "bytecode": rpyc_count,
                "path": rpa_path,
            })

        total_images = sum(r["images"] for r in results)
        has_scripts = any(r["scripts"] > 0 for r in results)

        if not has_scripts:
            warnings.append(
                "No .rpy script files found — image paths in scripts won't be updated."
            )

        self._wizard.app_state["scan_results"] = results
        self.after(0, self._show_results, results, warnings, total_images)

    def _clear_table(self) -> None:
        for w in self._table_frame.winfo_children():
            w.destroy()

    def _show_results(self, results: list, warnings: list, total_images: int) -> None:
        self._spinner.stop()
        self._spinner.grid_remove()

        total_size = sum(r["size"] for r in results)
        self._subtitle.configure(
            text=f"Found {len(results)} archive(s) — "
                 f"{total_images} images — "
                 f"{_fmt_size(total_size)} total"
        )

        # Table header
        headers = ["Archive", "Size", "Images", "Scripts (.rpy)"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(
                self._table_frame, text=h,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=_ACCENT,
            ).grid(row=0, column=col, padx=10, pady=6, sticky="w")

        for i, r in enumerate(results):
            bg = _ROW_ODD if i % 2 == 0 else _ROW_EVEN
            row_vals = [
                r["name"],
                _fmt_size(r["size"]),
                str(r["images"]) if r["images"] else "—",
                str(r["scripts"]) if r["scripts"] else "—",
            ]
            for col, val in enumerate(row_vals):
                ctk.CTkLabel(
                    self._table_frame, text=val,
                    font=ctk.CTkFont(size=12),
                    text_color="#dde3ea",
                ).grid(row=i + 1, column=col, padx=10, pady=4, sticky="w")

        if warnings:
            self._warning_label.configure(text="  ".join(warnings))

        if total_images > 0:
            self._wizard.set_next_enabled(True)
        else:
            self._warning_label.configure(
                text="No images found in any archive — nothing to compress."
            )
