from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.converter import avif_path, convert_to_avif, is_image
from core.rpa import iter_files, write_rpa
from core.script_patcher import is_rpy, is_rpyc, patch_rpy

if TYPE_CHECKING:
    from gui.wizard import Wizard

_BG = "#16213e"
_ACCENT = "#c0392b"


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class CompressPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=_BG, corner_radius=0)
        self._wizard = wizard
        self._cancel_event = threading.Event()
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            self, text="Compressing…",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#ffffff",
        ).grid(row=0, column=0, pady=(40, 4), padx=40, sticky="w")

        self._archive_label = ctk.CTkLabel(
            self, text="Preparing…",
            font=ctk.CTkFont(size=13),
            text_color="#c8d6e5",
        )
        self._archive_label.grid(row=1, column=0, pady=(0, 10), padx=40, sticky="w")

        # Overall progress
        ctk.CTkLabel(self, text="Overall progress", font=ctk.CTkFont(size=11),
                     text_color="#7f8c8d").grid(row=2, column=0, padx=40, sticky="w")
        self._overall_bar = ctk.CTkProgressBar(self, width=500)
        self._overall_bar.set(0)
        self._overall_bar.grid(row=3, column=0, padx=40, pady=(2, 10), sticky="w")

        # Current file progress
        self._file_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11),
                                         text_color="#7f8c8d")
        self._file_label.grid(row=4, column=0, padx=40, sticky="w")
        self._file_bar = ctk.CTkProgressBar(self, width=500)
        self._file_bar.set(0)
        self._file_bar.grid(row=5, column=0, padx=40, pady=(2, 0), sticky="nw")

        # Stats
        self._stats_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=12),
            text_color="#2ecc71",
        )
        self._stats_label.grid(row=6, column=0, padx=40, pady=(14, 0), sticky="w")

        self._error_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11),
            text_color="#e74c3c",
        )
        self._error_label.grid(row=7, column=0, padx=40, pady=(6, 0), sticky="w")

        # Cancel button — placed in footer area via wizard, but we add one inline too
        self._cancel_btn = ctk.CTkButton(
            self, text="Cancel", width=100,
            fg_color="#2c2c54", hover_color="#3d3d6b",
            command=self._cancel,
        )
        self._cancel_btn.grid(row=8, column=0, padx=40, pady=(20, 0), sticky="w")

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._cancel_event.clear()
        self._overall_bar.set(0)
        self._file_bar.set(0)
        self._stats_label.configure(text="")
        self._error_label.configure(text="")
        self._archive_label.configure(text="Preparing…")
        self._cancel_btn.configure(state="normal")
        threading.Thread(target=self._run_compression, daemon=True).start()

    def on_next(self) -> None:
        pass  # Next button is disabled during compression

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled", text="Cancelling…")

    # ------------------------------------------------------------------
    def _run_compression(self) -> None:
        results = self._wizard.app_state.get("scan_results", [])
        backup = self._wizard.app_state.get("backup", True)

        total_images = sum(r["images"] for r in results)
        processed_images = 0
        saved_bytes = 0
        compress_results = []

        for archive_idx, r in enumerate(results):
            if self._cancel_event.is_set():
                break

            rpa_path: Path = r["path"]
            orig_size = r["size"]

            self.after(0, self._archive_label.configure,
                       {"text": f"Processing {rpa_path.name}  ({archive_idx + 1}/{len(results)})"})

            if r["images"] == 0 and r["scripts"] == 0:
                compress_results.append({**r, "new_size": orig_size})
                continue

            new_files: dict[str, bytes] = {}
            file_list = list(iter_files(rpa_path))
            total_in_archive = len(file_list)

            for file_idx, (path, data) in enumerate(file_list):
                if self._cancel_event.is_set():
                    break

                # Per-file progress
                file_frac = file_idx / max(total_in_archive, 1)
                self.after(0, self._file_bar.set, file_frac)
                self.after(0, self._file_label.configure, {"text": f"  {path}"})

                if is_image(path):
                    try:
                        converted = convert_to_avif(data)
                    except Exception as e:
                        self.after(0, self._error_label.configure,
                                   {"text": f"Skipped {path}: {e}"})
                        new_files[path] = data
                        continue
                    new_path = avif_path(path)
                    new_files[new_path] = converted
                    processed_images += 1

                    # Update overall bar
                    overall_frac = processed_images / max(total_images, 1)
                    saved_so_far = saved_bytes + (len(data) - len(converted))
                    self.after(0, self._overall_bar.set, overall_frac)
                    self.after(0, self._stats_label.configure,
                               {"text": f"Saved {_fmt_size(max(0, saved_so_far))} so far"})

                elif is_rpy(path):
                    new_files[path] = patch_rpy(data)

                elif is_rpyc(path):
                    pass  # Drop .rpyc — Ren'Py will recompile from .rpy

                else:
                    new_files[path] = data

            if self._cancel_event.is_set():
                break

            # Write new archive
            tmp_path = rpa_path.with_suffix(".rpa.tmp")
            try:
                write_rpa(tmp_path, new_files)
                new_size = tmp_path.stat().st_size
                saved_bytes += orig_size - new_size

                if backup:
                    bak_path = rpa_path.with_suffix(".rpa.bak")
                    if bak_path.exists():
                        bak_path.unlink()
                    rpa_path.rename(bak_path)
                else:
                    rpa_path.unlink()

                tmp_path.rename(rpa_path)
                compress_results.append({**r, "new_size": new_size})

            except Exception as e:
                if tmp_path.exists():
                    tmp_path.unlink()
                self.after(0, self._error_label.configure,
                           {"text": f"Error writing {rpa_path.name}: {e}"})
                compress_results.append({**r, "new_size": orig_size})

        self._wizard.app_state["compress_results"] = compress_results
        self.after(0, self._on_done)

    def _on_done(self) -> None:
        self._file_bar.set(1)
        self._overall_bar.set(1)
        self._cancel_btn.configure(state="disabled")
        if not self._cancel_event.is_set():
            self._wizard.navigate_to("done")
        else:
            self._archive_label.configure(text="Cancelled.")
