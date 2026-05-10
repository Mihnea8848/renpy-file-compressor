from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.converter import avif_path, convert_to_avif, is_image
from core.rpa import iter_files, write_rpa
from core.script_patcher import is_rpy, is_rpyc, patch_rpy
from core.video_converter import av1_path, convert_to_av1, is_video
from gui.wizard import C_ACCENT, C_BTN_SEC, C_BTN_SEC_H, C_FOOTER_SEP, C_TEXT, C_TEXT_SUB, C_WHITE

if TYPE_CHECKING:
    from gui.wizard import Wizard


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


class CompressPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, wizard: "Wizard") -> None:
        super().__init__(parent, fg_color=C_WHITE, corner_radius=0)
        self._wizard = wizard
        self._cancel_event = threading.Event()
        self._build()

    # ── Layout ─────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Blue header strip
        header = ctk.CTkFrame(self, fg_color="#003087", corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header, text="Compressing…",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff", anchor="w",
        ).place(x=28, y=14)
        self._header_sub = ctk.CTkLabel(
            header, text="Preparing…",
            font=ctk.CTkFont(size=12), text_color="#c8d6e5", anchor="w")
        self._header_sub.place(x=28, y=44)

        ctk.CTkFrame(self, height=1, fg_color="#d0d0d0", corner_radius=0).grid(
            row=1, column=0, sticky="ew")

        # Progress section
        prog = ctk.CTkFrame(self, fg_color=C_WHITE, corner_radius=0)
        prog.grid(row=2, column=0, sticky="ew", padx=28, pady=(16, 0))
        prog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(prog, text="Overall progress",
                     font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB,
                     anchor="w").grid(row=0, column=0, sticky="w")

        self._overall_bar = ctk.CTkProgressBar(
            prog, height=14, corner_radius=3,
            fg_color="#e8e8e8", progress_color=C_ACCENT)
        self._overall_bar.set(0)
        self._overall_bar.grid(row=1, column=0, sticky="ew", pady=(3, 8))

        self._overall_label = ctk.CTkLabel(
            prog, text="", font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB, anchor="w")
        self._overall_label.grid(row=2, column=0, sticky="w")

        ctk.CTkLabel(prog, text="Current file",
                     font=ctk.CTkFont(size=11), text_color=C_TEXT_SUB,
                     anchor="w").grid(row=3, column=0, sticky="w", pady=(8, 0))

        self._file_bar = ctk.CTkProgressBar(
            prog, height=8, corner_radius=2,
            fg_color="#e8e8e8", progress_color="#27ae60")
        self._file_bar.set(0)
        self._file_bar.grid(row=4, column=0, sticky="ew", pady=(3, 0))

        # Console log
        ctk.CTkLabel(self, text="Log",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_TEXT_SUB, anchor="w").grid(
            row=3, column=0, sticky="w", padx=28, pady=(14, 2))

        self._log = ctk.CTkTextbox(
            self,
            fg_color="#1e1e1e",
            text_color="#d4d4d4",
            font=ctk.CTkFont(family="Courier", size=11),
            corner_radius=4,
            border_width=1,
            border_color="#d0d0d0",
            state="disabled",
            wrap="word",
        )
        self._log.grid(row=5, column=0, sticky="nsew", padx=28, pady=(0, 10))

        # Cancel
        self._cancel_btn = ctk.CTkButton(
            self, text="Cancel", width=90, height=28,
            fg_color=C_BTN_SEC, hover_color=C_BTN_SEC_H,
            text_color=C_TEXT, font=ctk.CTkFont(size=11),
            border_width=1, border_color=C_FOOTER_SEP,
            corner_radius=2, command=self._cancel,
        )
        self._cancel_btn.grid(row=6, column=0, padx=28, pady=(0, 10), sticky="w")

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._cancel_event.clear()
        self._overall_bar.set(0)
        self._file_bar.set(0)
        self._overall_label.configure(text="")
        self._header_sub.configure(text="Preparing…")
        self._cancel_btn.configure(state="normal", text="Cancel")
        self._log_clear()
        threading.Thread(target=self._run, daemon=True).start()

    def on_next(self) -> None:
        pass  # disabled during compression

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled", text="Cancelling…")

    # ── Logging helpers ────────────────────────────────────────────────────
    def _log_clear(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _log_write(self, msg: str, color: str = "#d4d4d4") -> None:
        def _do():
            self._log.configure(state="normal")
            tag = f"col_{color.replace('#', '')}"
            self._log.tag_config(tag, foreground=color)
            self._log.insert("end", f"[{_ts()}] {msg}\n", tag)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _log_info(self, msg: str) -> None:
        self._log_write(msg, "#d4d4d4")

    def _log_ok(self, msg: str) -> None:
        self._log_write(msg, "#4ec9b0")

    def _log_warn(self, msg: str) -> None:
        self._log_write(msg, "#ce9178")

    def _log_error(self, msg: str) -> None:
        self._log_write(msg, "#f44747")

    # ── Main compression thread ────────────────────────────────────────────
    def _run(self) -> None:
        results  = self._wizard.app_state.get("scan_results", [])
        backup   = self._wizard.app_state.get("backup", True)
        game_dir = Path(self._wizard.app_state["game_folder"]) / "game"

        # --- Staging directory: originals are NEVER touched until all succeed ---
        stage_dir = game_dir / ".hhg_compress_stage"
        try:
            stage_dir.mkdir(exist_ok=True)
        except OSError as e:
            self._log_error(f"Cannot create staging directory: {e}")
            return

        staged: dict[Path, Path] = {}          # original → staged temp file
        compress_results: list[dict] = []
        total_items = sum(r["images"] + r["videos"] for r in results)
        processed = 0
        saved_bytes = 0

        try:
            for arch_idx, r in enumerate(results):
                if self._cancel_event.is_set():
                    raise InterruptedError("Cancelled by user.")

                rpa_path: Path = r["path"]
                staged_path = stage_dir / rpa_path.name

                self.after(0, self._header_sub.configure, {
                    "text": f"Archive {arch_idx + 1}/{len(results)}: {rpa_path.name}"
                })
                self._log_info(
                    f"Processing {rpa_path.name}  "
                    f"({_fmt_size(r['size'])}  •  "
                    f"{r['images']} images  •  {r['videos']} video(s))"
                )

                # Archives with nothing to do are copied as-is
                if r["images"] == 0 and r["videos"] == 0 and r["scripts"] == 0:
                    self._log_info(f"  No compressible content — skipping.")
                    compress_results.append({**r, "new_size": r["size"]})
                    continue

                new_files: dict[str, bytes] = {}
                file_list = list(iter_files(rpa_path))
                total_in_arch = len(file_list)

                for fi, (fpath, data) in enumerate(file_list):
                    if self._cancel_event.is_set():
                        raise InterruptedError("Cancelled by user.")

                    self.after(0, self._file_bar.set, fi / max(total_in_arch, 1))

                    if is_image(fpath):
                        self._log_info(f"  IMG  {fpath}")
                        try:
                            out = convert_to_avif(data)
                            new_path = avif_path(fpath)
                            new_files[new_path] = out
                            delta = len(data) - len(out)
                            saved_bytes += delta
                            self._log_ok(
                                f"       → {new_path.split('/')[-1]}  "
                                f"{_fmt_size(len(data))} → {_fmt_size(len(out))}  "
                                f"(-{delta / max(len(data), 1) * 100:.0f}%)"
                            )
                        except Exception as e:
                            self._log_warn(f"       SKIP (convert failed): {e}")
                            new_files[fpath] = data
                        processed += 1

                    elif is_video(fpath):
                        ext = Path(fpath).suffix
                        self._log_info(f"  VID  {fpath}")
                        try:
                            out = convert_to_av1(data, ext)
                            new_path = av1_path(fpath)
                            new_files[new_path] = out
                            delta = len(data) - len(out)
                            saved_bytes += delta
                            self._log_ok(
                                f"       → {Path(new_path).name}  "
                                f"{_fmt_size(len(data))} → {_fmt_size(len(out))}  "
                                f"(-{delta / max(len(data), 1) * 100:.0f}%)"
                            )
                        except Exception as e:
                            self._log_warn(f"       SKIP (encode failed): {e}")
                            new_files[fpath] = data
                        processed += 1

                    elif is_rpy(fpath):
                        self._log_info(f"  SCR  {fpath}  (patching extensions)")
                        new_files[fpath] = patch_rpy(data)

                    elif is_rpyc(fpath):
                        self._log_info(f"  BYT  {fpath}  (dropped — Ren'Py will recompile)")
                        # intentionally not added to new_files

                    else:
                        new_files[fpath] = data

                    # Update overall bar
                    overall_frac = processed / max(total_items, 1)
                    self.after(0, self._overall_bar.set, overall_frac)
                    self.after(0, self._overall_label.configure, {
                        "text": f"Saved {_fmt_size(max(0, saved_bytes))} so far  •  "
                                f"{processed}/{total_items} files"
                    })

                # Write the staged file
                self._log_info(f"  Writing staged archive…")
                write_rpa(staged_path, new_files)
                new_size = staged_path.stat().st_size
                staged[rpa_path] = staged_path
                compress_results.append({**r, "new_size": new_size})
                self._log_ok(
                    f"  Staged: {_fmt_size(r['size'])} → {_fmt_size(new_size)}"
                )

            # ── All archives staged successfully — now do the atomic swap ──
            if self._cancel_event.is_set():
                raise InterruptedError("Cancelled by user.")

            self._log_info("All archives processed. Applying changes…")
            for orig_path, s_path in staged.items():
                if backup:
                    bak = orig_path.with_suffix(".rpa.bak")
                    if bak.exists():
                        bak.unlink()
                    orig_path.rename(bak)
                    self._log_info(f"  Backup: {orig_path.name} → {bak.name}")
                else:
                    orig_path.unlink()
                s_path.rename(orig_path)
                self._log_ok(f"  Replaced: {orig_path.name}")

            shutil.rmtree(stage_dir, ignore_errors=True)
            self._wizard.app_state["compress_results"] = compress_results
            self.after(0, self._on_done, True)

        except InterruptedError as e:
            self._log_warn(f"Cancelled — cleaning up staging directory…")
            shutil.rmtree(stage_dir, ignore_errors=True)
            self._log_ok("Staging cleaned up. Original files are untouched.")
            self.after(0, self._on_done, False)

        except Exception as e:
            self._log_error(f"Unexpected error: {e}")
            shutil.rmtree(stage_dir, ignore_errors=True)
            self._log_warn("Staging cleaned up. Original files are untouched.")
            self.after(0, self._on_done, False)

    def _on_done(self, success: bool) -> None:
        self._file_bar.set(1 if success else 0)
        if success:
            self._overall_bar.set(1)
            self._header_sub.configure(text="Done — click Next to see results.")
            self._cancel_btn.configure(state="disabled")
            self._wizard.navigate_to("done")
        else:
            self._header_sub.configure(text="Cancelled. Original files are untouched.")
            self._cancel_btn.configure(state="disabled", text="Cancelled")
